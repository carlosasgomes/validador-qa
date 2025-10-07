import asyncio
from playwright.async_api import async_playwright

# Resoluções de tela para testes
SCREEN_RESOLUTIONS = {
    "desktop": {"width": 1920, "height": 1080},
    "tablet": {"width": 768, "height": 1024},
    "mobile": {"width": 375, "height": 667}
}

async def _check_scroll_for_size(page, name, size):
    """
    Função auxiliar para verificar o scroll lateral e encontrar o elemento causador.
    """
    await page.set_viewport_size(size)
    await page.goto(page.url)  # Recarrega a página com o novo tamanho
    
    # Script JavaScript para detectar scroll lateral e encontrar o elemento causador
    has_scroll_js = """
        (function() {
            var body = document.body;
            var html = document.documentElement;
            var content_width = Math.max(body.scrollWidth, body.offsetWidth, html.clientWidth, html.scrollWidth, html.offsetWidth);
            var viewport_width = html.clientWidth;
            
            if (content_width > viewport_width) {
                // Se houver scroll, tenta encontrar o elemento que o causa
                var allElements = document.querySelectorAll('body *');
                for (var i = 0; i < allElements.length; i++) {
                    var element = allElements[i];
                    if (element.offsetWidth > viewport_width) {
                        return element.tagName + (element.id ? '#' + element.id : '') + (element.className ? '.' + element.className.split(' ')[0] : '');
                    }
                }
                return 'unknown';
            }
            return null;
        })();
    """
    
    element_selector = await page.evaluate(has_scroll_js)
    
    if element_selector:
        return {
            "device": name,
            "status": "reprovado",
            "details": f"Scroll lateral detectado. Conteúdo excede a largura da tela. Possível elemento causador: <{element_selector}>."
        }
    else:
        return {
            "device": name,
            "status": "aprovado",
            "details": "Nenhum scroll lateral detectado."
        }

async def validate_lateral_scroll(url):
    """
    Valida a presença de scroll lateral em diferentes dispositivos, fornecendo o elemento causador.
    """
    results = []
    
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page()
            await page.goto(url)

            # Para cada resolução, verifique o scroll
            for name, size in SCREEN_RESOLUTIONS.items():
                result = await _check_scroll_for_size(page, name, size)
                results.append(result)
                
            await browser.close()
            
            # Formate o resultado final para o validador principal
            status = "aprovado"
            details_list = []
            
            for res in results:
                details_list.append(f"{res['device']}: {res['details']} ({res['status']})")
                if res['status'] == 'reprovado':
                    status = "reprovado"
                    
            return {
                "module": "lateral_scroll",
                "result": status,
                "details": ", ".join(details_list)
            }

    except Exception as e:
        return {
            "module": "lateral_scroll",
            "result": "erro",
            "details": f"Ocorreu um erro ao validar o scroll lateral: {e}"
        }