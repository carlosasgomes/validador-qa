import aiohttp
import asyncio
from io import BytesIO
from PIL import Image
from urllib.parse import urljoin
import re

async def _find_favicon_url(session, url):
    """
    Função auxiliar para encontrar a URL do favicon, buscando por várias convenções.
    """
    try:
        # Tenta pegar a URL do HTML
        async with session.get(url, timeout=5) as response:
            html = await response.text()
            
            # Padrão mais abrangente para a tag <link rel="...">
            # Procura por "icon" e "shortcut icon" em qualquer ordem
            match = re.search(r'<link.*?rel="(?:icon|shortcut icon)".*?href="(.*?)".*?>', html, re.IGNORECASE)
            if match:
                favicon_url = urljoin(url, match.group(1))
                return favicon_url

        # Se não encontrar no HTML, tenta as localizações padrão
        async with session.head(urljoin(url, '/favicon.ico'), timeout=5) as response:
            if response.status == 200:
                return urljoin(url, '/favicon.ico')
        
        async with session.head(urljoin(url, '/apple-touch-icon.png'), timeout=5) as response:
            if response.status == 200:
                return urljoin(url, '/apple-touch-icon.png')

    except Exception:
        return None

    return None

async def validate_favicon(url):
    """
    Verifica se o site tem um favicon e se ele tem o tamanho 32x32.
    """
    # A biblioteca Pillow, que lida com imagens, pode ter problemas com certas imagens.
    # Usado 'try-except' para tratar qualquer erro que possa ocorrer.
    try:
        async with aiohttp.ClientSession() as session:
            favicon_url = await _find_favicon_url(session, url)

            if not favicon_url:
                return {
                    "module": "favicon",
                    "result": "reprovado",
                    "details": "Nenhum favicon encontrado."
                }

            async with session.get(favicon_url, timeout=5) as response:
                if response.status != 200:
                    return {
                        "module": "favicon",
                        "result": "reprovado",
                        "details": f"Favicon encontrado, mas falhou ao baixar: Status {response.status}."
                    }
                
                image_data = await response.read()
                image = Image.open(BytesIO(image_data))
                width, height = image.size
                
                if width == 32 and height == 32:
                    return {
                        "module": "favicon",
                        "result": "aprovado",
                        "details": f"Favicon encontrado e tem o tamanho correto de {width}x{height}."
                    }
                else:
                    return {
                        "module": "favicon",
                        "result": "reprovado",
                        "details": f"Favicon encontrado, mas tem o tamanho incorreto de {width}x{height}. Esperado: 32x32."
                    }

    except Exception as e:
        return {
            "module": "favicon",
            "result": "reprovado",
            "details": f"Erro ao processar o favicon: {e}"
        }