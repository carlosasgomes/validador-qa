import asyncio
import importlib
import os

class WebsiteValidator:
    def __init__(self):
        # Mapeia as funções de validação que são carregadas dinamicamente.
        self.modules = self._load_modules()

    def _load_modules(self):
        """
        Carrega dinamicamente as funções de validação dos arquivos
        na pasta 'modules' que começam com 'validate_'.
        """
        modules_list = []
        modules_dir = os.path.join(os.path.dirname(__file__), '..', 'modules')

        if not os.path.exists(modules_dir):
            print(f"Warning: Directory not found - {modules_dir}")
            return modules_list

        for filename in os.listdir(modules_dir):
            if filename.endswith(".py") and filename != "__init__.py":
                module_name = f"modules.{filename[:-3]}"
                try:
                    module = importlib.import_module(module_name)
                    
                    for attr_name in dir(module):
                        attr = getattr(module, attr_name)
                        if asyncio.iscoroutinefunction(attr) and attr_name.startswith("validate_"):
                            modules_list.append(attr)
                            print(f"Loaded validation function: {module_name}.{attr_name}")
                except Exception as e:
                    print(f"Failed to load module {module_name}: {e}")
        
        return modules_list

    async def validate_website(self, url, **kwargs):
        """
        Executa todas as validações carregadas para uma URL, passando argumentos extras.
        """
        if not self.modules:
            return {"url": url, "validations": [], "status": "no_modules_loaded"}

        tasks = []
        for module in self.modules:
            # Obtém os nomes dos parâmetros que a função de validação espera
            params = module.__code__.co_varnames[:module.__code__.co_argcount]

            # Constrói o dicionário de argumentos para cada módulo
            module_args = {}
            if 'url' in params:
                module_args['url'] = url
            if 'workspace_name' in params and 'workspace_name' in kwargs:
                module_args['workspace_name'] = kwargs['workspace_name']
            if 'repo_slug' in params and 'repo_slug' in kwargs:
                module_args['repo_slug'] = kwargs['repo_slug']

            # Se o módulo espera uma URL mas nenhuma foi fornecida, pula-o
            if 'url' in params and not url:
                continue
                
            tasks.append(module(**module_args))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        validation_results = []
        for result in results:
            if isinstance(result, Exception):
                validation_results.append({
                    "module": "unknown",
                    "result": "erro",
                    "details": f"Ocorreu um erro inesperado: {result}"
                })
            else:
                validation_results.append(result)

        return {
            "url": url,
            "validations": validation_results,
            "status": "completed"
        }