import aiohttp
import asyncio
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

# Limite de concorrência global
CONCURRENCY_LIMIT = 5
SEMAPHORE = asyncio.Semaphore(CONCURRENCY_LIMIT)

# Padrões de links que DEVEM ser EXCLUÍDOS (Páginas Institucionais/Genéricas)
EXCLUDED_PATTERNS = [
    '/servicos',
    '/contato',
    '/blog',
    '/empresa',
    '/quem-somos',
    '/sobre', # Adicionando 'sobre' como padrão comum
]

# Classes CSS comuns para banners (Podem ser ajustadas conforme o seu padrão de site)
BANNER_SELECTORS = [
    '#banner-principal',
    '#main-hero',
    '.hero-section',
    '.main-slider',
    '.banner-area',
    '.header-banner-container'
]

async def validate_banner_links(url: str):
    
    base_url = url.strip('/')
    
    try:
        async with aiohttp.ClientSession() as session:
            
            page_html = None
            async with SEMAPHORE:
                try:
                    async with session.get(base_url, timeout=20) as response:
                        if response.status != 200:
                             return {
                                "module": "banner_link_checker",
                                "result": "erro",
                                "details": f"Erro ao acessar a URL: HTTP {response.status}"
                            }
                        page_html = await response.text()
                except (asyncio.TimeoutError, aiohttp.ClientError) as e:
                    return {
                        "module": "banner_link_checker",
                        "result": "erro",
                        "details": f"Erro de conexão ao acessar a URL: {type(e).__name__}"
                    }

            if not page_html:
                return {"module": "banner_link_checker", "result": "erro", "details": "Conteúdo da página não obtido."}

            soup = BeautifulSoup(page_html, 'html.parser')
            
            # 1. Tenta encontrar o contêiner do banner
            banner_container = None
            for selector in BANNER_SELECTORS:
                banner_container = soup.select_one(selector)
                if banner_container:
                    break
            
            if not banner_container:
                return {
                    "module": "banner_link_checker",
                    "result": "atencao",
                    "details": f"ATENÇÃO: Não foi possível identificar o contêiner do banner usando os seletores configurados ({', '.join(BANNER_SELECTORS)}). O teste não pode ser executado."
                }

            # 2. Busca todos os links (<a>) dentro do banner
            all_links_in_banner = banner_container.find_all('a', href=True)
            
            if not all_links_in_banner:
                 return {
                    "module": "banner_link_checker",
                    "result": "aprovado",
                    "details": "APROVADO: O contêiner do banner foi encontrado, mas não possui links."
                }

            # 3. Filtra os links de acordo com as regras
            mpi_links = []
            
            for link_tag in all_links_in_banner:
                raw_href = link_tag['href']
                
                # Resolve links relativos para facilitar a checagem
                absolute_url = urljoin(base_url + '/', raw_href)
                
                # Pega apenas o caminho do link (ex: /produto/x)
                path = urlparse(absolute_url).path.lower()
                
                # Checa se o link deve ser excluído (é um link institucional)
                is_excluded = any(path.startswith(pattern) for pattern in EXCLUDED_PATTERNS)
                
                # Se o link não estiver na lista de exclusão E não for link de âncora interna (#)
                if not is_excluded and not raw_href.startswith('#'):
                    # Adiciona o link como uma possível MPI
                    mpi_links.append(absolute_url)

            
            # 4. Gera o Relatório Final
            if mpi_links:
                unique_mpi_links = list(set(mpi_links))
                return {
                    "module": "banner_link_checker",
                    "result": "aprovado",
                    "details": {
                        "status": f"APROVADO: Foram encontrados {len(unique_mpi_links)} link(s) no banner que não são institucionais (potenciais MPIs).",
                        "links_encontrados": unique_mpi_links
                    }
                }
            else:
                return {
                    "module": "banner_link_checker",
                    "result": "reprovado",
                    "details": (
                        f"REPROVADO: Nenhum link de destino no banner é considerado uma MPI. "
                        f"Todos os links encontrados levam a páginas institucionais ou foram excluídos pelo filtro."
                    )
                }

    except Exception as e:
        return {
            "module": "banner_link_checker",
            "result": "erro",
            "details": f"Ocorreu um erro geral na validação de links do Banner: {type(e).__name__}"
        }