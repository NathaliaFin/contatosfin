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
from app.models import Contato, Grupo, Usuario  # noqa: E402
from app.services import contatos as servico  # noqa: E402
from app.services import seed  # noqa: E402

app = create_app()

FICHAS = [
    # Pessoas e dados FICTICIOS, apenas para demonstracao.
    dict(nome="Helena Duarte Vasconcelos", cargo="Presidente", empresa="ABEL - Associação Brasileira das Empresas de Leasing",
         email="helena.vasconcelos@exemplo.org.br", celular="(11) 98888-1001", secretaria_nome="Paula Ramos",
         secretaria_email="secretaria@exemplo.org.br", secretaria_celular="(11) 97777-2002",
         grupos=["Conselho", "Diretoria", "RI", "Associadas", "Rep. classe 3"], inicio_mandato="Março de 2024",
         horario_trabalho="9h às 18h", ramal="2101", preferencias="Prefere contato por e-mail; reuniões pela manhã.",
         nacionalidade="brasileira", estado_civil="casada", qualificacao="dirigente de entidade de classe"),
    dict(nome="Ricardo Almeida Prado", cargo="Diretor-executivo", empresa="ABECIP",
         email="ricardo.prado@exemplo.com.br", telefone_comercial="(11) 3333-4040", grupos=["Diretoria", "Associadas"]),
    dict(nome="Beatriz Nogueira Lins", cargo="Superintendente de Relações Institucionais", empresa="ABBC",
         email="beatriz.lins@exemplo.com.br", celular="(61) 99123-4567", grupos=["RI"]),
    dict(nome="Carlos Eduardo Menezes", cargo="Vice-presidente", empresa="abel - associação brasileira das empresas de leasing",
         celular="(11) 99555-0101", grupos=["Conselho"]),
    dict(nome="Daniela Freitas Rocha", cargo="Gerente jurídica", empresa="ABBI", email="daniela.rocha@exemplo.com.br",
         grupos=["Associadas"]),
    dict(nome="Eduardo Siqueira Campos", cargo="Conselheiro", empresa="ACREFI", grupos=["Conselho", "Rep. classe 3"]),
    dict(nome="Fernanda Torres Bastos", cargo="Assessora parlamentar", empresa="Fin",
         email="fernanda.bastos@exemplo.org.br", celular="(61) 98100-2233", grupos=["RI"]),
    dict(nome="Gustavo Henrique Lobo", cargo="Presidente do conselho", empresa="ABECS", grupos=["Conselho", "Diretoria"]),
    dict(nome="Isabela Moura Pacheco", cargo="Coordenadora de eventos", empresa="ABECIP", email="isabela.pacheco@exemplo.com.br"),
    dict(nome="Jorge Luiz Antunes", cargo="Diretor financeiro", empresa="ANEPS", telefone_comercial="(11) 3030-5050",
         grupos=["Associadas"]),
    dict(nome="Ângela Ribeiro Coutinho", cargo="Secretária-geral", empresa="ABBC", grupos=["Diretoria"]),
    dict(nome="Otávio Martins Leal", cargo="Consultor", empresa="Leal Consultoria", celular="(21) 99876-5432"),
]


def popular():
    db.drop_all()
    db.create_all()
    seed.semear_tudo()

    admin = Usuario.query.filter_by(email="admin@fin.org.br").first()
    gestor = Usuario(nome="Gestora de Dados (demo)", email="gestor@fin.org.br", perfil=c.PERFIL_GESTOR)
    usuario = Usuario(nome="Usuário Comum (demo)", email="usuario@fin.org.br", perfil=c.PERFIL_USUARIO)
    for u in (gestor, usuario):
        u.definir_senha("Fin@2026")
        db.session.add(u)
    db.session.flush()

    grupos = {g.nome: g.id for g in Grupo.query.all()}
    contatos = []
    for dados in FICHAS:
        valores = {k: v for k, v in dados.items() if k != "grupos"}
        valores["grupos"] = sorted(grupos[n] for n in dados.get("grupos", []))
        contatos.append(servico.criar_contato(valores, gestor))
    db.session.commit()

    # Um pedido em aberto, para ver o carimbo "Alteracao pendente".
    alvo = contatos[1]
    valores = servico.valores_do_contato(alvo, incluir_restritos=False)
    valores["celular"] = "(11) 97654-3210"
    valores["cargo"] = "Presidente"
    servico.solicitar_alteracao(alvo, valores, usuario, "Mudou de cargo em novembro.")
    db.session.commit()
    print(f"  {Contato.query.count()} fichas de demonstração criadas (admin: {admin.email}).")


with app.app_context():
    popular()

if __name__ == "__main__":
    print("\n  Copia de teste em http://127.0.0.1:5000")
    print("  Entre com gestor@fin.org.br, usuario@fin.org.br ou admin@fin.org.br / Fin@2026\n")
    app.run(host="127.0.0.1", port=5000, debug=True, use_reloader=False)
