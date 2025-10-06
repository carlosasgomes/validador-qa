import aiohttp
import asyncio
import re

async def validate_fontawesome(url):
    """
    Verifica se o site carrega a biblioteca Font Awesome, buscando
    por qualquer link ou script que contenha "fontawesome".
    """
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=5) as response:
                if response.status != 200:
                    return {
                        "module": "fontawesome",
                        "result": "reprovado",
                        "details": f"Não foi possível acessar a página para validar o Font Awesome. Status: {response.status}"
                    }
                
                html = await response.text()
                
                # A nova expressão regular vai direto ao ponto: procura a palavra "fontawesome"
                # em qualquer tag <link> ou <script>
                pattern = re.compile(
                    r'<link[^>]*href=["\'][^"\']*(?:fontawesome|fa)[^"\']*["\'][^>]*>|'
                    r'<script[^>]*src=["\'][^"\']*(?:fontawesome|fa)[^"\']*["\'][^>]*>',
                    re.IGNORECASE
                )
                
                if pattern.search(html):
                    return {
                        "module": "fontawesome",
                        "result": "aprovado",
                        "details": "A biblioteca Font Awesome foi encontrada no código-fonte."
                    }
                else:
                    return {
                        "module": "fontawesome",
                        "result": "reprovado",
                        "details": "A biblioteca Font Awesome não foi encontrada no código-fonte."
                    }

    except Exception as e:
        return {
            "module": "fontawesome",
            "result": "erro",
            "details": f"Ocorreu um erro ao validar o Font Awesome: {e}"
        }