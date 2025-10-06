import aiohttp
import asyncio

async def validate_http_status(url):
    """Verifica se a URL retorna um status HTTP 200 OK."""
    try:
        # Usa um ClientSession para gerenciar as conexões
        async with aiohttp.ClientSession() as session:
            # Faz uma requisição GET com um timeout de 5 segundos
            async with session.get(url, timeout=5) as response:
                status = response.status
                is_valid = status == 200
                return {
                    "module": "http_status",
                    "result": "aprovado" if is_valid else "reprovado",
                    "details": f"Status code: {status}"
                }
    except aiohttp.ClientError as e:
        # Captura erros de cliente (e.g., DNS falhou, URL inválida)
        return {
            "module": "http_status",
            "result": "reprovado",
            "details": f"Erro de conexão: {e}"
        }
    except asyncio.TimeoutError:
        # Captura o erro de timeout
        return {
            "module": "http_status",
            "result": "reprovado",
            "details": "Tempo limite de conexão esgotado."
        }
    except Exception as e:
        # Captura qualquer outro erro inesperado
        return {
            "module": "http_status",
            "result": "erro",
            "details": f"Ocorreu um erro inesperado: {e}"
        }