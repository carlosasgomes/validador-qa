import ssl
import socket
import asyncio
from urllib.parse import urlparse

async def validate_ssl_certificate(url):
    """Verifica o certificado SSL de uma URL."""
    try:
        # Analisa a URL para obter o host e a porta (padrão 443 para HTTPS)
        parsed_url = urlparse(url)
        if parsed_url.scheme != 'https':
            return {
                "module": "ssl_certificate",
                "result": "nao_se_aplica",
                "details": "A validação de SSL não se aplica a URLs que não são HTTPS."
            }

        hostname = parsed_url.hostname
        port = 443
        
        # Cria um contexto SSL padrão
        context = ssl.create_default_context()
        
        # Usa asyncio para conectar-se ao servidor de forma não bloqueante
        reader, writer = await asyncio.open_connection(hostname, port, ssl=context)
        
        # Pega o certificado da conexão
        writer.close()
        await writer.wait_closed()
        
        # Se a conexão foi bem sucedida, o certificado existe e é válido
        return {
            "module": "ssl_certificate",
            "result": "aprovado",
            "details": "Certificado SSL válido encontrado."
        }
    except ssl.SSLError as e:
        # Erro de certificado (expirado, inválido, etc.)
        return {
            "module": "ssl_certificate",
            "result": "reprovado",
            "details": f"Erro no certificado SSL: {e}"
        }
    except (socket.gaierror, ConnectionRefusedError) as e:
        # Erros de conexão ou DNS
        return {
            "module": "ssl_certificate",
            "result": "reprovado",
            "details": f"Erro de conexão ao verificar SSL: {e}"
        }
    except Exception as e:
        # Qualquer outro erro
        return {
            "module": "ssl_certificate",
            "result": "erro",
            "details": f"Ocorreu um erro inesperado: {e}"
        }