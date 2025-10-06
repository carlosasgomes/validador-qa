# Arquivo: core/report_generator.py
import os
from xhtml2pdf import pisa  # Você precisará instalar: pip install xhtml2pdf
from datetime import datetime

def generate_html_report(results: dict) -> str:
    """
    Cria o conteúdo HTML do relatório a partir dos resultados da auditoria.
    """
    url = results.get('url', 'URL Desconhecida')
    timestamp = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Relatório de Auditoria QA</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20mm; }}
            h1 {{ color: #2C3E50; border-bottom: 2px solid #3498DB; padding-bottom: 5px; }}
            h2 {{ color: #3498DB; margin-top: 20px; }}
            .header {{ text-align: center; margin-bottom: 30px; }}
            .status-aprovado {{ color: green; font-weight: bold; }}
            .status-reprovado {{ color: red; font-weight: bold; }}
            .status-atencao {{ color: orange; font-weight: bold; }}
            .validation-box {{ border: 1px solid #ECF0F1; padding: 10px; margin-bottom: 15px; border-radius: 5px; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>Relatório de Auditoria de Qualidade e SEO</h1>
            <p><strong>Site Auditado:</strong> {url}</p>
            <p><strong>Data da Análise:</strong> {timestamp}</p>
        </div>
    """
    
    for validation in results.get('validations', []):
        module = validation.get('module', 'Módulo Desconhecido')
        result_status = validation.get('result', 'erro').lower()
        details = validation.get('details', 'Sem detalhes')

        # Determina a classe CSS para a cor
        status_class = f"status-{result_status}"
        
        # Converte detalhes complexos (como listas e dicionários) para string formatada
        if isinstance(details, dict):
             details_str = ""
             for key, value in details.items():
                 details_str += f"<strong>{key.replace('_', ' ').title()}:</strong> {value}<br>"
        else:
            details_str = str(details)

        html_content += f"""
        <div class="validation-box">
            <h2>{module.replace('_', ' ').title()}</h2>
            <p>Status: <span class="{status_class}">{result_status.upper()}</span></p>
            <p>Detalhes:</p>
            <p>{details_str}</p>
        </div>
        """
        
    html_content += "</body></html>"
    return html_content

def convert_html_to_pdf(source_html: str, output_filename: str):
    """
    Converte o HTML fornecido em um arquivo PDF.
    """
    result_file = open(output_filename, "w+b")
    pisa_status = pisa.CreatePDF(
        source_html,
        dest=result_file
    )
    result_file.close()
    return pisa_status.err

def generate_pdf_report(results: dict, output_dir: str = 'reports'):
    """Função principal para gerar o relatório PDF."""
    
    # 1. Certifica-se de que a pasta de relatórios exista
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    # 2. Gera o conteúdo HTML
    html_content = generate_html_report(results)
    
    # 3. Define o nome do arquivo (limpando a URL para o nome do arquivo)
    safe_url_name = results.get('url', 'report').replace('https://', '').replace('http://', '').replace('/', '_').replace('.', '-')
    output_filename = os.path.join(output_dir, f"relatorio_{safe_url_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf")
    
    # 4. Converte e salva o PDF
    error = convert_html_to_pdf(html_content, output_filename)
    
    if not error:
        return f"Sucesso! Relatório PDF gerado em: {output_filename}"
    else:
        return f"Erro ao gerar o PDF: {error}"