import aiohttp
import asyncio

W3C_CSS_VALIDATOR_URL = "https://jigsaw.w3.org/css-validator/validator"
CONCURRENCY_LIMIT = 3
SEMAPHORE = asyncio.Semaphore(CONCURRENCY_LIMIT)


async def validate_w3c_css(url):
    base_url = url.strip('/')
    params = {'uri': base_url, 'profile': 'css3', 'output': 'json', 'medium': 'all'}

    try:
        async with aiohttp.ClientSession() as session:
            async with SEMAPHORE:
                async with session.get(W3C_CSS_VALIDATOR_URL, params=params, timeout=45) as response:
                    if response.status >= 500:
                         return {
                            "module": "w3c_css_validation",
                            "result": "erro",
                            "details": f"API do W3C CSS indisponível: HTTP {response.status}"
                        }
                    data = await response.json()

            validation_result = data.get('cssvalidation', {})
            errors = validation_result.get('errors', [])
            warnings = validation_result.get('warnings', [])
            
            num_errors = len(errors)
            num_warnings = len(warnings)
            
            # --- Determinação do Status ---
            if num_errors > 0:
                status = "reprovado"
                
                # NOVO FORMATO: URL DO ARQUIVO CSS + LINHA + MENSAGEM
                error_details = [
                    f"ERRO EM: {e.get('uri')} (Linha {e.get('line')}) -> {e.get('message')}"
                    for e in errors[:5]
                ]
                details = {
                    "Total de Erros CSS": num_errors,
                    "Total de Avisos": num_warnings,
                    "Amostra dos Erros": error_details,
                    "Resultado Completo (W3C)": f"{W3C_CSS_VALIDATOR_URL}?uri={base_url}"
                }
            
            elif num_warnings > 0:
                status = "atencao"
                
                warning_details = [
                    f"AVISO EM: {w.get('uri')} (Linha {w.get('line')}) -> {w.get('message')}"
                    for w in warnings[:5]
                ]
                details = {
                    "Total de Erros CSS": num_errors,
                    "Total de Avisos": num_warnings,
                    "Amostra dos Avisos": warning_details,
                    "Resultado Completo (W3C)": f"{W3C_CSS_VALIDATOR_URL}?uri={base_url}"
                }
            
            else:
                status = "aprovado"
                details = f"APROVADO: Nenhuma falha de sintaxe CSS encontrada. (0 Erros, 0 Avisos)"

            return {
                "module": "w3c_css_validation",
                "result": status,
                "details": details
            }

    except Exception as e:
        return {
            "module": "w3c_css_validation",
            "result": "erro",
            "details": f"Ocorreu um erro geral: {type(e).__name__}"
        }