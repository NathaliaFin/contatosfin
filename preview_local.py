"""Copia de teste local, sem depender do MySQL do Azure.

Cria um banco SQLite descartavel (instance/preview.db) com usuarios e fichas
FICTICIAS de demonstracao e sobe o servidor em http://127.0.0.1:5000

    python preview_local.py

Usuarios de demonstracao (senha Fin@2026 para todos):

    admin@fin.org.br     Administrador
    gestor@fin.org.br    Gestor de dados
    usuario@fin.org.br   Usuario

Os e-mails nao sao enviados: ficam em instance/emails-nao-enviados.log.
Este arquivo e apenas para desenvolvimento -- em producao use wsgi.py.
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
INSTANCE = BASE_DIR / "instance"
INSTANCE.mkdir(exist_ok=True)

# A copia de teste nunca usa o banco nem o e-mail de producao.
os.environ["DATABASE_URL"] = f"sqlite:///{INSTANCE / 'preview.db'}"
os.environ["FLASK_ENV"] = "development"
os.environ["SECRET_KEY"] = "chave-de-desenvolvimento-local"
os.environ["CHAVE_DADOS_RESTRITOS"] = ""
os.environ["SMTP_PASSWORD"] = ""
os.environ["SSO_ENABLED"] = "false"
os.environ["APP_URL"] = "http://127.0.0.1:5000"
os.environ["ADMIN_EMAIL"] = "admin@fin.org.br"
os.environ["ADMIN_NOME"] = "Administração do Sistema"
os.environ["ADMIN_SENHA"] = "Fin@2026"

from app import constants as c  # noqa: E402
from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402
from app.models import Contato, Usuario  # noqa: E402
from app.services import demo, seed  # noqa: E402

app = create_app()


def popular():
    db.drop_all()
    db.create_all()
    seed.semear_tudo()

    gestor = Usuario(nome="Gestora de Dados (demo)", email="gestor@fin.org.br", perfil=c.PERFIL_GESTOR)
    usuario = Usuario(nome="Usuário Comum (demo)", email="usuario@fin.org.br", perfil=c.PERFIL_USUARIO)
    for u in (gestor, usuario):
        u.definir_senha("Fin@2026")
        db.session.add(u)
    db.session.flush()

    # As mesmas fichas ficticias do comando "flask demo" (app/services/demo.py).
    resumo = demo.criar(criador=gestor, solicitante=usuario)
    print(f"  {Contato.query.count()} fichas e {resumo['pedidos']} pedidos de demonstração criados.")


with app.app_context():
    popular()

if __name__ == "__main__":
    print("\n  Copia de teste em http://127.0.0.1:5000")
    print("  Entre com gestor@fin.org.br, usuario@fin.org.br ou admin@fin.org.br / Fin@2026\n")
    app.run(host="127.0.0.1", port=5000, debug=True, use_reloader=False)
