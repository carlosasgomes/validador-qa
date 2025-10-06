import aiohttp
import asyncio
from bs4 import BeautifulSoup

# Limite de concorrência global
CONCURRENCY_LIMIT = 5
SEMAPHORE = asyncio.Semaphore(CONCURRENCY_LIMIT)


async def validate_viewport_meta_tag(url: str):
    
    base_url = url.strip('/')
    
    try:
        async with aiohttp.ClientSession() as session:
            
            page_html = None
            async with SEMAPHORE:
                try:
                    async with session.get(base_url, timeout=20) as response:
                        if response.status != 200:
                             return {
                                "module": "viewport_check",
                                "result": "erro",
                                "details": f"Erro ao acessar a URL: HTTP {response.status}"
                            }
                        page_html = await response.text()
                except (asyncio.TimeoutError, aiohttp.ClientError) as e:
                    return {
                        "module": "viewport_check",
                        "result": "erro",
                        "details": f"Erro de conexão ao acessar a URL: {type(e).__name__}"
                    }

            if not page_html:
                return {"module": "viewport_check", "result": "erro", "details": "Conteúdo da página não obtido."}

            soup = BeautifulSoup(page_html, 'html.parser')
            
            # Procura pela tag meta viewport
            viewport_tag = soup.find('meta', attrs={'name': 'viewport'})
            
            # --- 1. Verificação de Existência ---
            if not viewport_tag:
                return {
                    "module": "viewport_check",
                    "result": "reprovado",
                    "details": "REPROVADO: A tag `<meta name=\"viewport\">` está **faltando** no `<head>` da página."
                }
            
            content_attr = viewport_tag.get('content', '')
            
            # Converte o conteúdo para uma lista de atributos para facilitar a verificação
            attributes = {attr.strip().split('=')[0]: attr.strip().split('=')[1] 
                          for attr in content_attr.split(',') if '=' in attr}

            # --- 2. Validação dos Atributos Essenciais ---
            if 'width' not in attributes or attributes['width'] != 'device-width':
                return {
                    "module": "viewport_check",
                    "result": "reprovado",
                    "details": f"REPROVADO: O atributo `width=device-width` está **faltando ou incorreto** na tag viewport. Conteúdo atual: '{content_attr}'."
                }
            
            if 'initial-scale' not in attributes or attributes['initial-scale'] != '1.0':
                 return {
                    "module": "viewport_check",
                    "result": "reprovado",
                    "details": f"REPROVADO: O atributo `initial-scale=1.0` está **faltando ou incorreto** na tag viewport. Conteúdo atual: '{content_attr}'."
                }

            # Se tudo passou
            return {
                "module": "viewport_check",
                "result": "aprovado",
                "details": "APROVADO: A tag `meta viewport` está configurada corretamente."
            }

    except Exception as e:
        return {
            "module": "viewport_check",
            "result": "erro",
            "details": f"Ocorreu um erro geral na validação de viewport: {type(e).__name__}"
        }