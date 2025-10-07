import aiohttp
import asyncio
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

# Limites de concorrência
CONCURRENCY_LIMIT = 20
SEMAPHORE = asyncio.Semaphore(CONCURRENCY_LIMIT)

# Status HTTP que indicam um link quebrado (erros de cliente ou servidor)
BROKEN_STATUSES = list(range(400, 600))

# Status HTTP que indicam que o link deve ser retestado (erros temporários)
RETRY_STATUSES = [408, 429, 500, 502, 503, 504]

# Domínios a serem ignorados (W3C e outros validadores/serviços comuns de ferramentas)
DOMAINS_TO_EXCLUDE = [
    'validator.w3.org',
    'jigsaw.w3.org',
    'w3.org',
    # Adicione outros domínios de ferramentas ou serviços que você queira ignorar
]


def _get_links_from_html(html, base_url):
    """Extrai todos os links (hrefs) internos e externos, excluindo domínios específicos."""
    soup = BeautifulSoup(html, 'html.parser')
    links = set()
    
    for a_tag in soup.find_all('a', href=True):
        href = a_tag['href'].strip()
        
        # 1. Ignora links vazios, âncoras internas, JS
        if not href or href.startswith(('#', 'mailto:', 'tel:', 'javascript:')):
            continue

        # 2. Resolve links relativos
        full_url = urljoin(base_url, href)
        
        # 3. Filtra URLs que não são HTTP/HTTPS
        if not full_url.startswith(('http://', 'https://')):
            continue

        # 4. Normaliza e checa o domínio
        parsed_url = urlparse(full_url)
        normalized_url = parsed_url._replace(fragment="").geturl()
        
        # ** NOVO FILTRO: IGNORA DOMÍNIOS ESPECÍFICOS (W3C) **
        if any(domain in parsed_url.netloc for domain in DOMAINS_TO_EXCLUDE):
            continue
        
        links.add(normalized_url)
            
    return list(links)


async def _check_link_status(session, url, max_retries=1):
    """Verifica o status HTTP de uma URL com retentativas em caso de erro temporário."""
    
    for attempt in range(max_retries + 1):
        async with SEMAPHORE:
            try:
                # Usa HEAD para ser rápido
                method = 'HEAD' if attempt == 0 else 'GET'
                
                async with session.request(method, url, timeout=15, allow_redirects=True) as response:
                    status = response.status
                    
                    if status not in RETRY_STATUSES:
                        return url, status
                    
                    # Se for um status de retentativa, espera um pouco e tenta novamente
                    if attempt < max_retries:
                        await asyncio.sleep(1) 
                        
            except (asyncio.TimeoutError, aiohttp.ClientError):
                return url, 0 # 0 para indicar erro de conexão/timeout
            except Exception:
                return url, 0
                
    return url, status if 'status' in locals() else 0


async def validate_broken_links(url):
    
    base_url = url.strip('/')
    
    try:
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False)) as session:
            
            # 1. Acessa a página principal para extrair todos os links
            page_html = None
            async with SEMAPHORE:
                try:
                    async with session.get(base_url, timeout=20) as response:
                        if response.status != 200:
                             return {
                                "module": "broken_links",
                                "result": "erro",
                                "details": f"Erro ao acessar a URL base ({base_url}) para começar a rastrear: HTTP {response.status}"
                            }
                        page_html = await response.text()
                except (asyncio.TimeoutError, aiohttp.ClientError) as e:
                    return {
                        "module": "broken_links",
                        "result": "erro",
                        "details": f"Erro de conexão ao acessar a URL base: {type(e).__name__}"
                    }

            # 2. Extrai, normaliza e FILTRA (W3C) todos os links encontrados
            all_links = _get_links_from_html(page_html, base_url)
            
            if not all_links:
                return {
                    "module": "broken_links",
                    "result": "aprovado",
                    "details": "Nenhum link foi encontrado para ser testado nesta página."
                }

            # 3. Cria uma lista de tarefas assíncronas para checar o status de cada link
            tasks = [_check_link_status(session, link) for link in all_links]
            
            # Executa todas as tarefas concorrentemente
            link_results = await asyncio.gather(*tasks)

            # 4. Processa os resultados para identificar links quebrados
            broken_links = {}
            
            for link, status in link_results:
                if status in BROKEN_STATUSES:
                    # Link quebrado (4xx ou 5xx)
                    broken_links[link] = status
                elif status == 0:
                    # Erro de conexão/timeout
                    broken_links[link] = "TIMEOUT/CONEXÃO"

            # 5. Gera o relatório final
            num_total = len(all_links)
            num_broken = len(broken_links)
            
            if num_broken > 0:
                status = "reprovado"
                
                # Prepara os detalhes dos links quebrados
                broken_details = [f"[{status_code}] -> {link}" for link, status_code in broken_links.items()]
                
                details = {
                    "Total de Links Encontrados (exceto W3C)": num_total,
                    "Total de Links Quebrados": num_broken,
                    "Links Quebrados (URL e Status)": broken_details
                }
            else:
                status = "aprovado"
                details = f"APROVADO: {num_total} links testados nesta página. Nenhum link quebrado encontrado."


            return {
                "module": "broken_links",
                "result": status,
                "details": details
            }

    except Exception as e:
        return {
            "module": "broken_links",
            "result": "erro",
            "details": f"Ocorreu um erro geral na validação de links quebrados: {type(e).__name__}"
        }