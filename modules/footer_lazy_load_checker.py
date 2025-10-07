import aiohttp
import asyncio
from bs4 import BeautifulSoup

# Limite de concorrência global
CONCURRENCY_LIMIT = 5
SEMAPHORE = asyncio.Semaphore(CONCURRENCY_LIMIT)


async def validate_footer_lazy_load(url: str):
    
    base_url = url.strip('/')
    
    try:
        async with aiohttp.ClientSession() as session:
            
            page_html = None
            async with SEMAPHORE:
                try:
                    async with session.get(base_url, timeout=20) as response:
                        if response.status != 200:
                             return {
                                "module": "footer_lazy_load_check",
                                "result": "erro",
                                "details": f"Erro ao acessar a URL: HTTP {response.status}"
                            }
                        page_html = await response.text()
                except (asyncio.TimeoutError, aiohttp.ClientError) as e:
                    return {
                        "module": "footer_lazy_load_check",
                        "result": "erro",
                        "details": f"Erro de conexão ao acessar a URL: {type(e).__name__}"
                    }

            if not page_html:
                return {"module": "footer_lazy_load_check", "result": "erro", "details": "Conteúdo da página não obtido."}

            soup = BeautifulSoup(page_html, 'html.parser')
            
            # 1. Tenta encontrar a tag <footer> principal
            footer_element = soup.find('footer')
            
            if not footer_element:
                # Se não houver tag <footer>, a validação é aprovada (não há o que validar)
                return {
                    "module": "footer_lazy_load_check",
                    "result": "aprovado",
                    "details": "APROVADO: A tag <footer> não foi encontrada. Nenhuma imagem no rodapé foi detectada para validação."
                }

            # 2. Busca por todas as imagens dentro do footer
            footer_images = footer_element.find_all('img')
            
            if not footer_images:
                 return {
                    "module": "footer_lazy_load_check",
                    "result": "aprovado",
                    "details": "APROVADO: A tag <footer> foi encontrada, mas não contém nenhuma imagem (<img>) ou iframe para checagem de lazy load."
                }

            # 3. Valida o atributo loading="lazy"
            missing_lazy_load = []
            
            for index, img in enumerate(footer_images):
                loading_attr = img.get('loading')
                
                # Se a imagem tiver um 'src' válido E não tiver o atributo loading="lazy"
                if img.get('src') and loading_attr != 'lazy':
                    # Pega o 'src' para identificar qual imagem está com problema
                    missing_lazy_load.append(f"Imagem #{index + 1} (src: {img.get('src')[:50]}...)")

            
            # 4. Gera o Relatório Final
            if missing_lazy_load:
                return {
                    "module": "footer_lazy_load_check",
                    "result": "reprovado",
                    "details": (
                        f"REPROVADO: {len(missing_lazy_load)} imagens no rodapé (<footer>) estão sem o atributo "
                        f"`loading=\"lazy\"`. Isso pode prejudicar o PageSpeed. "
                        f"Exemplos: {'; '.join(missing_lazy_load[:3])}"
                    )
                }
            else:
                return {
                    "module": "footer_lazy_load_check",
                    "result": "aprovado",
                    "details": f"APROVADO: Todas as {len(footer_images)} imagens no rodapé (<footer>) possuem o atributo `loading=\"lazy\"`."
                }

    except Exception as e:
        return {
            "module": "footer_lazy_load_check",
            "result": "erro",
            "details": f"Ocorreu um erro geral na validação de Lazy Load do Footer: {type(e).__name__}"
        }