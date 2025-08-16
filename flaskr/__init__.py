# ===================================================================
# ARQUIVO 3 de 4: flaskr/__init__.py (VERSÃO FINAL LIMPA)
# Funcao: O coração da aplicação (Application Factory).
# Ele monta o "motor", conectando todas as peças e blueprints.
# ===================================================================

import os
from flask import Flask

def create_app(test_config=None):
    """
    Cria e configura uma instância da aplicação Flask.
    Esta é a função "fábrica" da nossa aplicação.
    """
    # Cria a aplicação Flask.
    # instance_relative_config=True informa que arquivos de configuração
    # podem estar na pasta 'instance', fora do código principal.
    app = Flask(__name__, instance_relative_config=True)

    # Define configurações padrão.
    app.config.from_mapping(
        # SECRET_KEY é essencial para a segurança das sessões.
        SECRET_KEY='dev', # Em produção, isso deve ser um valor secreto e aleatório.
    )

    if test_config is None:
        # Carrega configurações de um arquivo externo (config.py) se ele existir.
        # Útil para guardar chaves de API e outras informações sensíveis.
        app.config.from_pyfile('config.py', silent=True)
    else:
        # Carrega uma configuração de teste, se fornecida.
        app.config.from_mapping(test_config)

    # Garante que a pasta 'instance' exista.
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass

    # --- REGISTRO DOS BLUEPRINTS ---
    # Um blueprint é um conjunto de rotas. Aqui, importamos e registramos
    # o nosso blueprint principal que contém todas as páginas e APIs.
    from . import main
    app.register_blueprint(main.bp)

    # Retorna a aplicação pronta para ser executada.
    return app
