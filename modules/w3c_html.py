import aiohttp
import asyncio

W3C_HTML_VALIDATOR_URL = "https://validator.w3.org/nu/"
CONCURRENCY_LIMIT = 3 
SEMAPHORE = asyncio.Semaphore(CONCURRENCY_LIMIT)


async def validate_w3c_html(url):
    base_url = url.strip('/')
    params = {'doc': base_url, 'out': 'json'}

    try:
        async with aiohttp.ClientSession() as session:
            async with SEMAPHORE:
                async with session.get(W3C_HTML_VALIDATOR_URL, params=params, timeout=45) as response:
                    if response.status >= 500:
                         return {
                            "module": "w3c_html_validation",
                            "result": "erro",
                            "details": f"API do W3C indisponível: HTTP {response.status}"
                        }
                    data = await response.json()

            messages = data.get('messages', [])
            errors = [m for m in messages if m.get('type') == 'error']
            warnings = [m for m in messages if m.get('type') == 'warning']
            
            num_errors = len(errors)
            num_warnings = len(warnings)
            
            # --- Determinação do Status ---
            if num_errors > 0:
                status = "reprovado"
                
                # NOVO FORMATO: URL DO ERRO + LINHA + MENSAGEM
                error_details = [
                    f"ERRO EM: {base_url} (Linha {e.get('lastLine')}) -> {e.get('message')}"
                    for e in errors[:5]
                ]
                details = {
                    "Total de Erros HTML": num_errors,
                    "Total de Avisos": num_warnings,
                    "Amostra dos Erros": error_details,
                    "Resultado Completo (W3C)": f"{W3C_HTML_VALIDATOR_URL}?doc={base_url}"
                }
            
            elif num_warnings > 0:
                status = "atencao"
                
                warning_details = [
                    f"AVISO EM: {base_url} (Linha {w.get('lastLine')}) -> {w.get('message')}"
                    for w in warnings[:5]
                ]
                details = {
                    "Total de Erros HTML": num_errors,
                    "Total de Avisos": num_warnings,
                    "Amostra dos Avisos": warning_details,
                    "Resultado Completo (W3C)": f"{W3C_HTML_VALIDATOR_URL}?doc={base_url}"
                }
            
            else:
                status = "aprovado"
                details = f"APROVADO: Nenhuma falha de sintaxe HTML encontrada. (0 Erros, 0 Avisos)"

            return {
                "module": "w3c_html_validation",
                "result": status,
                "details": details
            }

    except Exception as e:
        return {
            "module": "w3c_html_validation",
            "result": "erro",
            "details": f"Ocorreu um erro geral: {type(e).__name__}"
        }