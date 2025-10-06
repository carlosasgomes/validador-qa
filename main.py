# SEU ARQUIVO main.py (VERSÃO SIMPLIFICADA PARA VALIDAÇÕES ONLINE)

import asyncio
from urllib.parse import urlparse
from core.validator import WebsiteValidator
from core.report_generator import generate_pdf_report 
# O import de core.clone_repository foi removido!

# --- VARIÁVEIS FIXAS (Removidas: BITBUCKET_WORKSPACE, CLONE_DIR, BITBUCKET_API_TOKEN) ---

def get_repo_name_from_url(url: str) -> str:
    """Extrai o nome do repositório a partir da URL do site (função mantida por segurança)."""
    parsed_url = urlparse(url)
    repo_name = parsed_url.netloc
    if repo_name.startswith('www.'):
        repo_name = repo_name[4:]
    return repo_name

async def run_validation():
    print("--- Validador de Site Assíncrono ---")
    url = input("Por favor, digite a URL do site (ex: https://www.google.com): ")
    
    if not url:
        print("Nenhuma URL fornecida. Saindo...")
        return

    # 1. Instancia e Executa a Validação
    validator = WebsiteValidator()

    print(f"\nValidando site: {url}...")
    
    # Chamada do validador simplificada, sem argumentos extras!
    result = await validator.validate_website(url) 

    # 2. Imprime os resultados no Console
    print(f"\n--- Resultados da Validação para: {result['url']} ---")
    if not result['validations']:
        print("Nenhum módulo de validação foi carregado.")
        return

    for validation in result["validations"]:
        print(f"- Módulo: {validation.get('module', 'Desconhecido')}")
        print(f"  Status: {validation.get('result', 'N/A')}")
        print(f"  Detalhes: {validation.get('details', 'Sem detalhes')}")
    
    # 3. GERA O RELATÓRIO PDF
    print("\n" + "="*40)
    print("  INICIANDO GERAÇÃO DO RELATÓRIO PDF")
    print("="*40)
    pdf_status = generate_pdf_report(result)
    print(pdf_status)


if __name__ == "__main__":
    try:
        asyncio.run(run_validation())
    except Exception as e:
        print(f"\nOcorreu um erro fatal: {e}")