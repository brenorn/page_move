# ===================================================================
# ARQUIVO 1 de 4: run.py (VERSÃO À PROVA DE FALHAS)
# Funcao: Iniciar a aplicação de forma robusta, corrigindo
# problemas de ambiente em tempo de execução.
# ===================================================================

import sys
import os

# --- INÍCIO DA CORREÇÃO DE AMBIENTE ---
# Pega o caminho absoluto da pasta onde este arquivo (run.py) está.
project_root = os.path.dirname(os.path.abspath(__file__))

# Constrói o caminho exato para a pasta de bibliotecas (site-packages)
# dentro do seu ambiente virtual (venv).
# No Windows, o caminho é venv\Lib\site-packages.
venv_site_packages = os.path.join(project_root, 'venv', 'Lib', 'site-packages')

# Adiciona este caminho ao início da lista de locais onde o Python
# procura por bibliotecas. Isso força o Python a usar as ferramentas
# corretas do nosso projeto.
if venv_site_packages not in sys.path:
    sys.path.insert(0, venv_site_packages)
# --- FIM DA CORREÇÃO DE AMBIENTE ---


# Agora que o caminho está corrigido, a importação deve funcionar.
from flaskr import create_app

# Cria a instância da nossa aplicação Flask.
app = create_app()

# Bloco para executar a aplicação diretamente.
if __name__ == '__main__':
    # app.run() inicia o servidor de desenvolvimento do Flask.
    # debug=True permite ver os erros detalhados no navegador.
    # host='0.0.0.0' torna a aplicação visível na sua rede local.
    # port=5001 usa uma porta diferente para evitar conflitos.
    print("INFO: Iniciando o servidor de desenvolvimento em http://127.0.0.1:5001")
    app.run(host='0.0.0.0', port=5001, debug=True)
