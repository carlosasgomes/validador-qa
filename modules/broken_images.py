import aiohttp
import asyncio
from bs4 import BeautifulSoup
from urllib.parse import urljoin

async def _check_image_status(session, url):
    """
    Função auxiliar para verificar o status HTTP de uma única imagem.
    """
    try:
        async with session.head(url, timeout=5) as response:
            return response.status
    except aiohttp.ClientError:
        return None
    except asyncio.TimeoutError:
        return None
    except Exception:
        return None

async def validate_broken_images(url):
    """
    Verifica se o site tem imagens quebradas.
    """
    broken_images = []
    
    try:
        async with aiohttp.ClientSession() as session:
            # Primeiro, obtenha o HTML da página
            async with session.get(url, timeout=10) as response:
                if response.status != 200:
                    return {
                        "module": "broken_images",
                        "result": "erro",
                        "details": f"Não foi possível acessar a página para validar as imagens. Status: {response.status}"
                    }
                
                html = await response.text()
                soup = BeautifulSoup(html, 'html.parser')
                
                # Encontre todas as tags <img>
                image_tags = soup.find_all('img')
                
                # Crie uma lista de tarefas para verificar o status de cada imagem
                tasks = []
                for img in image_tags:
                    src = img.get('src')
                    if src:
                        # Converte URLs relativas em absolutas
                        absolute_url = urljoin(url, src)
                        tasks.append(_check_image_status(session, absolute_url))
                
                # Execute todas as tarefas de forma assíncrona
                statuses = await asyncio.gather(*tasks, return_exceptions=True)
                
                # Verifique os resultados
                for i, status in enumerate(statuses):
                    image_url = urljoin(url, image_tags[i].get('src'))
                    
                    if not status or status != 200:
                        broken_images.append(image_url)
                
                if broken_images:
                    return {
                        "module": "broken_images",
                        "result": "reprovado",
                        "details": f"Imagens quebradas encontradas: {', '.join(broken_images)}"
                    }
                else:
                    return {
                        "module": "broken_images",
                        "result": "aprovado",
                        "details": "Nenhuma imagem quebrada foi encontrada."
                    }
                        
    except Exception as e:
        return {
            "module": "broken_images",
            "result": "erro",
            "details": f"Ocorreu um erro ao validar as imagens quebradas: {e}"
        }