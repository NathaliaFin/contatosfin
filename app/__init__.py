"""Fabrica da aplicacao Flask - Sistema Contatos Fin."""

from pathlib import Path

import click
from flask import Flask, render_template

from app.config import get_config
from app.extensions import csrf, db, login_manager, migrate


def create_app(config_class=None) -> Flask:
    app = Flask(__name__, instance_relative_config=True)

    config_class = config_class or get_config()
    app.config.from_object(config_class)
    app.config["SQLALCHEMY_DATABASE_URI"] = config_class.database_uri()
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        **config_class.SQLALCHEMY_ENGINE_OPTIONS,
        "connect_args": config_class.connect_args(),
    }

    if not app.debug and not app.config.get("CHAVE_DADOS_RESTRITOS"):
        raise RuntimeError(
            "CHAVE_DADOS_RESTRITOS ausente no .env: o sistema nao sobe em "
            "producao sem a chave que protege os dados restritos."
        )

    Path(app.config["UPLOAD_FOLDER"]).mkdir(parents=True, exist_ok=True)

    if app.config.get("ATRAS_DE_PROXY"):
        from werkzeug.middleware.proxy_fix import ProxyFix

        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

    db.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)
    login_manager.init_app(app)

    _registrar_login_manager()
    _registrar_blueprints(app)
    _registrar_versao_estaticos(app)
    _registrar_context_processors(app)
    _registrar_filtros(app)
    _registrar_handlers(app)
    _registrar_comandos(app)
    return app


def _registrar_login_manager() -> None:
    from app.models import Usuario

    @login_manager.user_loader
    def carregar_usuario(usuario_id: str):
        return db.session.get(Usuario, int(usuario_id))


def _registrar_blueprints(app: Flask) -> None:
    from app.routes import admin, auth, contatos, empresas, pwa, relatorios, solicitacoes

    for modulo in (auth, contatos, empresas, solicitacoes, relatorios, admin, pwa):
        app.register_blueprint(modulo.bp)


def _registrar_versao_estaticos(app: Flask) -> None:
    """Acrescenta ?v=<data do arquivo> nas URLs de /static (mesma tecnica do
    afin): o nginx guarda os estaticos por 30 dias, e sem isto uma mudanca de
    CSS so apareceria para quem limpasse o cache."""
    from flask import url_for as url_for_original

    estaticos = Path(app.root_path) / "static"
    cache: dict[str, int] = {}

    def versao(nome: str):
        if nome in cache:
            return cache[nome]
        try:
            marca = int((estaticos / nome).stat().st_mtime)
        except OSError:
            return None
        if not app.debug:
            cache[nome] = marca
        return marca

    def url_for_versionado(endpoint, **valores):
        if endpoint == "static" and valores.get("filename"):
            marca = versao(valores["filename"])
            if marca is not None:
                valores["v"] = marca
        return url_for_original(endpoint, **valores)

    @app.context_processor
    def injetar_url_for():
        return {"url_for": url_for_versionado}


def _registrar_context_processors(app: Flask) -> None:
    from flask_login import current_user

    from app import constants as c

    @app.context_processor
    def injetar_globais():
        pendentes = 0
        if current_user.is_authenticated and current_user.pode_gerir:
            from app.services.contatos import contar_pendentes

            pendentes = contar_pendentes()
        return {"c": c, "PERFIS": c.PERFIS, "pendentes_nav": pendentes}


def _registrar_filtros(app: Flask) -> None:
    from app.services.texto import iniciais

    @app.template_filter("data")
    def formatar_data(valor):
        return valor.strftime("%d/%m/%Y") if valor else "—"

    @app.template_filter("datahora")
    def formatar_datahora(valor):
        return valor.strftime("%d/%m/%Y às %H:%M") if valor else "—"

    @app.template_filter("iniciais")
    def filtro_iniciais(nome):
        return iniciais(nome)

    @app.template_filter("whatsapp_link")
    def whatsapp_link(valor):
        from app.services.compartilhar import link_conversa

        return link_conversa(valor)

    @app.template_global("compartilhamento")
    def compartilhamento(contato):
        """Texto e links do menu de compartilhar (cartao e ficha)."""
        from app.services import compartilhar

        return {
            "texto": compartilhar.texto_whatsapp(contato),
            "link": compartilhar.link_compartilhar(contato),
            "aplicativo": compartilhar.link_aplicativo(contato),
        }

    @app.template_filter("telefone_link")
    def telefone_link(valor):
        from app.services.validacao import digitos

        d = digitos(valor or "")
        return f"tel:+55{d}" if len(d) in (10, 11) else f"tel:{d}"


def _registrar_handlers(app: Flask) -> None:
    from flask import redirect, request, url_for

    def pagina(codigo, titulo, texto):
        return render_template("erros/erro.html", codigo=codigo, titulo=titulo, texto=texto), codigo

    @app.errorhandler(401)
    def nao_autenticado(_erro):
        return redirect(url_for("auth.login", next=request.full_path))

    @app.errorhandler(403)
    def acesso_negado(_erro):
        return pagina(403, "Acesso restrito", "Seu perfil não tem permissão para abrir esta página.")

    @app.errorhandler(404)
    def nao_encontrado(_erro):
        return pagina(404, "Ficha não encontrada", "O endereço não existe ou o registro foi excluído.")

    @app.errorhandler(413)
    def arquivo_grande(_erro):
        return pagina(413, "Arquivo grande demais", f"A foto deve ter no máximo {app.config['FOTO_MAX_MB']} MB.")

    @app.errorhandler(500)
    def erro_interno(_erro):
        db.session.rollback()
        return pagina(500, "Algo deu errado", "O erro foi registrado. Tente de novo; se persistir, procure a TI.")

    from flask_wtf.csrf import CSRFError

    @app.errorhandler(CSRFError)
    def csrf_expirado(_erro):
        return pagina(400, "Formulário expirado", "A página ficou aberta por muito tempo. Volte, recarregue e tente de novo.")


def _registrar_comandos(app: Flask) -> None:
    from app.services import seed as servico_seed

    @app.cli.command("testar-banco")
    def testar_banco():
        """Verifica a conexao com o banco de dados (sem mostrar a senha)."""
        from sqlalchemy import text

        try:
            with db.engine.connect() as conexao:
                if app.config["SQLALCHEMY_DATABASE_URI"].startswith("mysql"):
                    detalhe = "MySQL " + conexao.execute(text("SELECT VERSION()")).scalar()
                else:
                    conexao.execute(text("SELECT 1"))
                    detalhe = "banco local (SQLite)"
            click.secho(f"Conexao bem-sucedida: {detalhe}.", fg="green")
        except Exception as erro:  # noqa: BLE001
            click.secho(f"Nao foi possivel conectar ao banco: {erro}", fg="red")
            raise SystemExit(1)

    @app.cli.command("seed")
    def seed():
        """Cria as listas de trabalho iniciais e o administrador."""
        resumo = servico_seed.semear_tudo()
        click.secho(f"Listas novas: {resumo['grupos']} | Administrador: {resumo['admin']}", fg="green")

    @app.cli.command("demo")
    @click.option("--remover", is_flag=True, help="Apaga tudo o que a demonstracao criou.")
    @click.option("--sim", is_flag=True, help="Nao pede confirmacao ao remover.")
    @click.option("--refazer-fotos", is_flag=True, help="Redesenha as silhuetas que ninguem trocou.")
    def demo(remover, sim, refazer_fotos):
        """Cria (ou remove) fichas FICTICIAS de demonstracao."""
        from app.services import demo as servico_demo

        if refazer_fotos:
            click.secho(f"Fotos ficticias redesenhadas: {servico_demo.refazer_fotos()}", fg="green")
            return
        if remover:
            if not sim:
                click.confirm("Apagar todas as fichas, pedidos e empresas da demonstracao?", abort=True)
            r = servico_demo.remover()
            click.secho(
                f"Removidos: {r['fichas']} ficha(s), {r['pedidos']} pedido(s), {r['empresas']} empresa(s).",
                fg="green",
            )
            return
        if servico_demo.existe():
            click.secho("A demonstracao ja existe. Use --remover antes de criar de novo.", fg="yellow")
            return
        r = servico_demo.criar()
        click.secho(
            f"Criadas {r['fichas']} fichas ficticias e {r['pedidos']} pedidos pendentes. "
            "Para apagar: flask demo --remover",
            fg="green",
        )

    @app.cli.command("criar-usuario")
    @click.option("--nome", prompt=True)
    @click.option("--email", prompt=True)
    @click.option("--perfil", type=click.Choice(["admin", "gestor", "usuario"]), prompt=True)
    def criar_usuario(nome, email, perfil):
        """Cria (ou atualiza o perfil de) um usuario pela linha de comando."""
        from app.models import Usuario

        email = email.strip().lower()
        usuario = Usuario.query.filter_by(email=email).first()
        if usuario:
            usuario.perfil = perfil
            click.secho(f"Perfil de {email} atualizado para {perfil}.", fg="yellow")
        else:
            db.session.add(Usuario(nome=nome, email=email, perfil=perfil))
            click.secho(f"Usuario {email} criado como {perfil}.", fg="green")
        db.session.commit()
