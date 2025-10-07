import aiohttp
import asyncio
import re
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

# Define o limite de requisições simultâneas para evitar sobrecarga
CONCURRENCY_LIMIT = 5
SEMAPHORE = asyncio.Semaphore(CONCURRENCY_LIMIT)

# --- Funções Auxiliares de Busca de Menu (Mantidas) ---

def _is_valid_nav_link(a_tag):
    href = a_tag.get('href', '')
    if not href or href.startswith(('#', 'mailto:', 'tel:')):
        return False
    return True

def _find_top_menu_links(soup, base_url):
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
                text = a_tag.get_text(strip=True).lower()
                href = a_tag.get('href')
                found_links.append((text, urljoin(base_url, href)))
        
        if len(found_links) > len(best_menu_links) and len(found_links) >= 2:
            best_menu_links = found_links
    
    unique_links = set(link for text, link in best_menu_links)
    return list(unique_links)

# --- Funções Auxiliares de Coerência URL/H1 ---

def _normalize_text(text):
    stop_words = r'\b(a|o|as|os|e|de|do|da|dos|das|em|no|na|nos|nas|para|por|com|um|uma|uns|umas|se|que|mas|mais|ou|é|são|oito|sete|seis|cinco|quatro|tres|dois|um|zero|etc)\b'

    normalized = text.lower()
    normalized = normalized.replace('ç', 'c').replace('á', 'a').replace('ã', 'a').replace('à', 'a').replace('â', 'a')
    normalized = normalized.replace('é', 'e').replace('ê', 'e')
    normalized = normalized.replace('í', 'i')
    normalized = normalized.replace('ó', 'o').replace('õ', 'o').replace('ô', 'o')
    normalized = normalized.replace('ú', 'u')
    
    normalized = re.sub(stop_words, ' ', normalized)
    
    normalized = re.sub(r'[^a-z0-9\s-]', ' ', normalized)
    normalized = re.sub(r'[\s-]+', '-', normalized).strip('-')
    
    return normalized

async def _check_page_coherence(session, page_url):
    """Função que tenta acessar a página, com retentativas em caso de Timeout."""
    
    # Tentativas de timeout: 15s (inicial), 20s, 40s, 60s
    timeouts = [15, 20, 40, 60] 
    last_error_type = None

    async with SEMAPHORE:
        for attempt, timeout_val in enumerate(timeouts):
            try:
                # 1. Tenta acessar a página
                async with session.get(page_url, timeout=timeout_val) as response:
                    
                    if response.status != 200:
                        # Falha HTTP não é timeout, tenta a próxima URL imediatamente
                        return page_url, f"Erro HTTP: {response.status}"
                    
                    # Se o acesso for bem-sucedido, processa a página
                    html = await response.text()
                    soup = BeautifulSoup(html, 'html.parser')

                    # Processamento de Coerência (Mantido)
                    h1_tag = soup.find('h1')
                    if not h1_tag or not h1_tag.get_text(strip=True):
                        return page_url, "Reprovado - Página sem tag H1 ou H1 vazio."
                    
                    h1_text = h1_tag.get_text(strip=True)

                    path = urlparse(page_url).path
                    path_segments = [s for s in path.strip('/').split('/') if s]
                    last_segment = path_segments[-1] if path_segments else ""
                    url_segment = last_segment.rsplit('.', 1)[0] 
                    
                    normalized_url = _normalize_text(url_segment)
                    normalized_h1 = _normalize_text(h1_text)

                    if normalized_url in normalized_h1 and normalized_url:
                        return page_url, "" # Aprovado
                    else:
                        details = (
                            f"Reprovado - Incoerência. "
                            f"URL Segmento (s/ stop words): **{normalized_url}**. "
                            f"H1 Normalizado (s/ stop words): **{normalized_h1}**. "
                            f"H1 Original: '{h1_text}'"
                        )
                        return page_url, details

            except asyncio.TimeoutError:
                last_error_type = "TimeoutError"
                if attempt < len(timeouts) - 1:
                    # Tenta novamente com um timeout maior
                    continue
                else:
                    # Se falhou na última tentativa (60s), sai do loop
                    break
            
            except aiohttp.ClientError as e:
                # Outros erros de conexão (DNS, SSL, etc.) não se beneficiam de mais tentativas
                return page_url, f"Erro ao acessar (Conexão): {type(e).__name__}"
            
            except Exception as e:
                return page_url, f"Erro inesperado ao acessar: {type(e).__name__}"

    # Retorna o erro de Timeout se todas as tentativas falharem
    return page_url, f"Erro ao acessar (Timeout/Conexão): {last_error_type} após {timeouts[-1]}s."

async def validate_url_h1_coherence(url):
    """
    Valida a coerência URL/H1, com retentativa para Timeouts e tolerância final a erros de acesso.
    """
    fail_results = {}
    has_content_failure = False # Flag para rastrear se houve falha de conteúdo/coerência
    
    try:
        global SEMAPHORE
        SEMAPHORE = asyncio.Semaphore(CONCURRENCY_LIMIT)

        async with aiohttp.ClientSession() as session:
            # Acesso à home
            async with session.get(url, timeout=15) as response:
                if response.status != 200:
                    return {
                        "module": "url_h1_coherence",
                        "result": "erro",
                        "details": f"Não foi possível acessar a home. Status: {response.status}"
                    }
                
                html = await response.text()
                soup = BeautifulSoup(html, 'html.parser')
                internal_links = _find_top_menu_links(soup, url)
                total_links = len(internal_links)

                if not internal_links:
                    return {
                        "module": "url_h1_coherence",
                        "result": "reprovado",
                        "details": "Não foram encontrados links válidos no menu de navegação principal para validação."
                    }

            tasks = [_check_page_coherence(session, link) for link in internal_links]
            page_results = await asyncio.gather(*tasks)

            # Contadores
            unreachable_links = 0
            
            for page_url, detail in page_results:
                if detail: 
                    fail_results[page_url] = detail
                    
                    if detail.startswith("Reprovado"):
                        has_content_failure = True
                    elif "Erro ao acessar" in detail or "Erro HTTP" in detail:
                        unreachable_links += 1

            # 1. Determina o Status Final
            
            # Limite de tolerância de 30% de links inacessíveis
            MAX_ERROR_PERCENT = 30
            error_percentage = (unreachable_links / total_links) * 100 if total_links > 0 else 0

            if has_content_failure:
                # Prioridade 1: Reprovado se houver falha de coerência, não importa os erros de conexão.
                final_status = "reprovado"
            elif error_percentage > MAX_ERROR_PERCENT:
                # Prioridade 2: Se muitos links falharam, reporta um erro (não aprovado, nem reprovado por conteúdo).
                final_status = "erro"
            else:
                # Prioridade 3: Se não houve falhas de conteúdo E os erros de conexão são toleráveis (abaixo de 30%)
                final_status = "aprovado"

            # 2. Define os detalhes finais
            if final_status == "aprovado":
                links_checked = total_links - unreachable_links
                final_details = f"Aprovado! Coerência URL/H1 verificada em {links_checked} páginas. ({unreachable_links} erros de acesso ignorados, erro total: {error_percentage:.1f}%)."
            else:
                final_details = fail_results
                if final_status == "erro":
                    final_details["_Resumo"] = f"ERRO GERAL: Não foi possível acessar {unreachable_links} de {total_links} links. (Erro: {error_percentage:.1f}%). Limite de tolerância excedido (30%)."
                
            return {
                "module": "url_h1_coherence",
                "result": final_status,
                "details": final_details
            }
    
    except Exception as e:
        return {
            "module": "url_h1_coherence",
            "result": "erro",
            "details": f"Ocorreu um erro geral na validação: {type(e).__name__}"
        }