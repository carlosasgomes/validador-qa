import aiohttp
import asyncio
import re
import json 
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

# Define o limite de requisições simultâneas
CONCURRENCY_LIMIT = 5
SEMAPHORE = asyncio.Semaphore(CONCURRENCY_LIMIT)

# --- Funções Auxiliares de Busca de Menu ---

def _is_valid_nav_link(a_tag):
    href = a_tag.get('href', '')
    if not href or href.startswith(('#', 'mailto:', 'tel:')):
        return False
    return True

def _find_top_menu_links(soup, base_url):
    """Encontra links do menu principal para serem as páginas de teste."""
    possible_menus = soup.find_all(['nav', 'ul'])
    best_menu_links = []
    
    for menu_tag in possible_menus:
        found_links = []
        for a_tag in menu_tag.find_all('a', href=True):
            if not _is_valid_nav_link(a_tag):
                continue
            parent_li = a_tag.find_parent('li')
            if not parent_li:
                continue
            if parent_li.parent == menu_tag: 
                href = a_tag.get('href')
                full_url = urljoin(base_url, href)
                # Garante que seja um link interno
                if urlparse(full_url).netloc == urlparse(base_url).netloc:
                    found_links.append(full_url)
        
        if len(found_links) > len(best_menu_links) and len(found_links) >= 2:
            best_menu_links = found_links
    
    unique_links = set(best_menu_links)
    unique_links.add(base_url) # Inclui a página inicial
    return list(unique_links)

# --- Lógica de Validação de Breadcrumbs ---

async def _check_link_status(session, link_url):
    """Verifica o status HTTP de um link do breadcrumb (sem retentativas)."""
    async with SEMAPHORE:
        try:
            # Usa HEAD para ser mais rápido, só checa o status
            async with session.head(link_url, allow_redirects=True, timeout=10) as response: 
                if response.status != 200:
                    return link_url, response.status
                return link_url, None # OK
        except (asyncio.TimeoutError, aiohttp.ClientError):
            return link_url, "Erro de Conexão"
        except Exception:
            return link_url, "Erro Inesperado"

def _extract_breadcrumb_links(soup, page_url, base_url):
    """
    Extrai todos os URLs da estrutura de breadcrumb. 
    Ignora a URL da página atual que está sendo testada (page_url).
    """
    links = []

    # Normalização da URL da página que está sendo testada para exclusão
    normalized_page_url = page_url.strip('/')

    # 1. Tenta extrair links do JSON-LD (Prioridade máxima para SEO)
    for script_tag in soup.find_all('script', {'type': 'application/ld+json'}):
        try:
            data = json.loads(script_tag.string)
            if not isinstance(data, list):
                data = [data]
            
            for item in data:
                if item.get('@type') == 'BreadcrumbList' and 'itemListElement' in item:
                    for element in item['itemListElement']:
                        target_item = element.get('item', {})
                        full_url = target_item.get('@id') or element.get('item', {}).get('url')
                        
                        if full_url:
                            # Verifica se o link é interno e NÃO é a página atual
                            parsed_url = urlparse(full_url)
                            if parsed_url.netloc == urlparse(base_url).netloc:
                                if full_url.strip('/') != normalized_page_url and full_url not in links:
                                    links.append(full_url)

                    # Se encontrarmos o JSON-LD e links válidos, paramos a busca JSON
                    if links:
                        return links
        except (json.JSONDecodeError, TypeError, AttributeError):
            continue
    
    # 2. Se não encontrou no JSON-LD, faz a busca agressiva por HTML
    
    # Seletores que buscam por palavras-chave comuns (breadcrumb, migalha, caminho) em classes ou IDs
    breadcrumb_tags = soup.find_all(
        ['ol', 'ul', 'nav', 'div'],
        {'class': re.compile(r'(breadcrumb|migalha|caminho)', re.IGNORECASE)}
    )
    
    if not breadcrumb_tags:
         breadcrumb_tags = soup.find_all(
            ['ol', 'ul', 'nav', 'div'],
            {'id': re.compile(r'(breadcrumb|migalha|caminho)', re.IGNORECASE)}
        )

    # Tenta um wrapper de navegação genérico com aria-label
    if not breadcrumb_tags:
        breadcrumb_tags = soup.find_all('nav', {'aria-label': re.compile(r'breadcrumb', re.IGNORECASE)})


    for target_tag in breadcrumb_tags:
        for a_tag in target_tag.find_all('a', href=True):
            href = a_tag.get('href')
            full_url = urljoin(base_url, href)
            
            # Checa se o link é o link da própria página ou uma âncora interna
            if full_url.strip('/') == normalized_page_url or a_tag.get('href').startswith('#'):
                continue
                
            # Apenas links internos
            if urlparse(full_url).netloc == urlparse(base_url).netloc:
                links.append(full_url)
    
    return list(set(links)) # Remove duplicatas

async def _check_page_breadcrumbs(session, page_url, base_url):
    """Acessa a página com retentativa, extrai links e checa o status deles."""
    
    # Sequência de timeouts para retentativa: 15s (inicial), 20s, 40s, 60s
    timeouts = [15, 20, 40, 60] 
    
    async with SEMAPHORE:
        page_html = None
        for attempt, timeout_val in enumerate(timeouts):
            try:
                # 1. Tenta obter o conteúdo da página (com retentativa em caso de Timeout)
                async with session.get(page_url, timeout=timeout_val) as response:
                    if response.status != 200:
                        # Falha HTTP não é timeout, reporta imediatamente
                        return page_url, f"Erro ao acessar a página de teste: HTTP {response.status}", False 
                    
                    page_html = await response.text()
                    break 
            
            except asyncio.TimeoutError:
                if attempt < len(timeouts) - 1:
                    continue # Tenta de novo com timeout maior
                else:
                    return page_url, f"Erro ao acessar a página de teste (Timeout): {timeout_val}s.", False
            
            except aiohttp.ClientError as e:
                # Outros erros de conexão
                return page_url, f"Erro ao acessar a página de teste (Conexão): {type(e).__name__}", False
            
            except Exception as e:
                return page_url, f"Erro inesperado ao acessar: {type(e).__name__}", False

    if not page_html:
        return page_url, "Erro interno: Conteúdo da página não obtido.", False

    # 2. Extrai os links do breadcrumb (usando a URL da página atual para exclusão)
    soup = BeautifulSoup(page_html, 'html.parser')
    breadcrumb_links = _extract_breadcrumb_links(soup, page_url, base_url) # Alteração aqui!

    # 3. Verifica se a página interna deveria ter um breadcrumb
    is_internal_page = urlparse(page_url).path.strip('/') != ''
    if not breadcrumb_links and is_internal_page:
        return page_url, "Reprovado - Página interna sem estrutura de breadcrumb (ou não encontrada pelo parser).", True 
    elif not breadcrumb_links:
        return page_url, None, False # Home page ignorada

    # 4. Verifica o status de cada link do breadcrumb
    link_check_tasks = [_check_link_status(session, link) for link in breadcrumb_links]
    link_results = await asyncio.gather(*link_check_tasks)
    
    broken_links = [link for link, status in link_results if status is not None]

    if broken_links:
        # Reprovado por conteúdo: links quebrados
        details = (
            f"Reprovado - Links quebrados encontrados no breadcrumb: "
            f"{', '.join(broken_links)}"
        )
        return page_url, details, True
    else:
        # Aprovado
        return page_url, None, False


async def validate_breadcrumbs(url):
    
    fail_results = {}
    has_structure_failure = False 
    unreachable_links = 0
    total_links_to_check = 0
    
    try:
        global SEMAPHORE
        SEMAPHORE = asyncio.Semaphore(CONCURRENCY_LIMIT)

        async with aiohttp.ClientSession() as session:
            # Encontra links para testar
            async with session.get(url, timeout=15) as response:
                if response.status != 200:
                    return {
                        "module": "breadcrumbs",
                        "result": "erro",
                        "details": f"Não foi possível acessar a home. Status: {response.status}"
                    }
                
                html = await response.text()
                soup = BeautifulSoup(html, 'html.parser')
                internal_links = _find_top_menu_links(soup, url)
                total_links_to_check = len(internal_links)

                if total_links_to_check == 0:
                     return {
                        "module": "breadcrumbs",
                        "result": "reprovado",
                        "details": "Não foram encontrados links válidos no menu de navegação principal para testar."
                    }

            # Executa a validação em todas as páginas
            tasks = [_check_page_breadcrumbs(session, link, url) for link in internal_links]
            page_results = await asyncio.gather(*tasks)

            # Processa os resultados
            for page_url, detail, is_structure_failure in page_results:
                if detail: 
                    fail_results[page_url] = detail
                    
                    if is_structure_failure:
                        has_structure_failure = True
                    elif "Erro ao acessar a página de teste" in detail:
                        unreachable_links += 1

            # Determina o Status Final
            MAX_ERROR_PERCENT = 30
            error_percentage = (unreachable_links / total_links_to_check) * 100 if total_links_to_check > 0 else 0

            if has_structure_failure:
                final_status = "reprovado"
            elif error_percentage > MAX_ERROR_PERCENT:
                final_status = "erro"
            else:
                final_status = "aprovado"

            # Define os detalhes finais
            if final_status == "aprovado":
                links_checked = total_links_to_check - unreachable_links
                final_details = f"Aprovado! Breadcrumbs verificados em {links_checked} páginas. ({unreachable_links} erros de acesso à página de teste ignorados, erro total: {error_percentage:.1f}%)."
            else:
                final_details = fail_results
                if final_status == "erro":
                    final_details["_Resumo"] = f"ERRO GERAL: Não foi possível acessar {unreachable_links} de {total_links_to_check} links do menu. (Erro: {error_percentage:.1f}%). Limite de tolerância excedido (30%)."
                
            return {
                "module": "breadcrumbs",
                "result": final_status,
                "details": final_details
            }
    
    except Exception as e:
        return {
            "module": "breadcrumbs",
            "result": "erro",
            "details": f"Ocorreu um erro geral na validação: {type(e).__name__}"
        }