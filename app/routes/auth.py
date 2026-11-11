"""Autenticacao: conta Microsoft (porta principal) e e-mail/senha
(acesso de emergencia do administrador)."""

import secrets
from urllib.parse import urlparse

from flask import Blueprint, current_app, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required, login_user, logout_user

from app import constants as c
from app.extensions import db
from app.models import Usuario, agora
from app.services import sso as servico_sso

bp = Blueprint("auth", __name__, url_prefix="/auth")


@bp.context_processor
def injetar_sso():
    return {"sso_disponivel": servico_sso.configurado()}


def _destino_seguro(destino: str | None) -> str:
    padrao = url_for("contatos.lista")
    if not destino:
        return padrao
    partes = urlparse(destino)
    if partes.netloc or partes.scheme or not destino.startswith("/"):
        return padrao
    return destino


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("contatos.lista"))

    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        senha = request.form.get("senha") or ""
        usuario = Usuario.query.filter_by(email=email).first()

        # Mensagem unica para nao revelar quais e-mails existem.
        if usuario is None or not usuario.checar_senha(senha):
            flash("E-mail ou senha incorretos.", "erro")
            return render_template("auth/login.html", email=email, abrir_cadeado=True), 401
        if not usuario.ativo:
            flash("Seu acesso está inativo. Procure o administrador do sistema.", "erro")
            return render_template("auth/login.html", email=email, abrir_cadeado=True), 403

        login_user(usuario, remember=bool(request.form.get("lembrar")))
        usuario.ultimo_acesso = agora()
        db.session.commit()
        return redirect(_destino_seguro(request.args.get("next")))

    return render_template("auth/login.html", email="", abrir_cadeado=False)


@bp.route("/sair", methods=["POST"])
@login_required
def sair():
    # Primeiro limpa a sessao e so depois chama o logout_user: e ele que marca
    # o cookie "manter conectado" para ser apagado. Na ordem inversa a marca
    # sumia junto com a sessao, o cookie ficava e a pessoa voltava logada.
    session.clear()
    logout_user()
    flash("Sessão encerrada.", "info")
    return redirect(url_for("auth.login"))


# ---------------------------------------------------------------------------
# SSO Microsoft (Entra ID) - mesmo fluxo do afin
# ---------------------------------------------------------------------------
def _sso_indisponivel():
    flash("A entrada com a conta Microsoft ainda não foi habilitada.", "aviso")
    return redirect(url_for("auth.login"))


@bp.route("/sso/entrar")
def sso_entrar():
    if not servico_sso.configurado():
        return _sso_indisponivel()

    estado = secrets.token_urlsafe(32)
    session["sso_estado"] = estado
    session["sso_destino"] = _destino_seguro(request.args.get("next"))
    try:
        return redirect(servico_sso.url_de_autorizacao(estado))
    except Exception:  # noqa: BLE001
        current_app.logger.exception("SSO Microsoft: falha ao montar a URL")
        flash("Não foi possível abrir a tela da Microsoft. Tente de novo em instantes.", "erro")
        return redirect(url_for("auth.login"))


@bp.route("/sso/callback")
def sso_callback():
    if not servico_sso.configurado():
        return _sso_indisponivel()

    estado_esperado = session.pop("sso_estado", None)
    destino = session.pop("sso_destino", None)

    if request.args.get("error"):
        current_app.logger.info(
            "SSO Microsoft recusado: %s",
            request.args.get("error_description") or request.args["error"],
        )
        flash("Entrada pela Microsoft cancelada.", "aviso")
        return redirect(url_for("auth.login"))

    if not estado_esperado or request.args.get("state") != estado_esperado:
        flash("A tentativa de entrada expirou. Clique de novo em “Entrar com a conta Microsoft”.", "erro")
        return redirect(url_for("auth.login"))

    codigo = request.args.get("code")
    if not codigo:
        flash("A Microsoft não enviou o código de entrada.", "erro")
        return redirect(url_for("auth.login"))

    try:
        identidade = servico_sso.identidade_do_codigo(codigo)
    except servico_sso.ErroSSO as erro:
        flash(str(erro), "erro")
        return redirect(url_for("auth.login"))

    usuario = Usuario.query.filter_by(azure_oid=identidade.oid).first()
    if usuario is None:
        usuario = Usuario.query.filter_by(email=identidade.email).first()

    if usuario is None:
        dominio = current_app.config["SSO_DOMINIO"]
        if not identidade.email.endswith("@" + dominio):
            current_app.logger.info("SSO: %s fora do dominio %s", identidade.email, dominio)
            flash(
                "Esta conta Microsoft não tem acesso ao sistema. "
                "Peça ao administrador para cadastrá-la.",
                "erro",
            )
            return redirect(url_for("auth.login"))
        # Conta da Fin: entra sozinha, com o perfil de usuario comum.
        usuario = Usuario(
            nome=identidade.nome,
            email=identidade.email,
            perfil=c.PERFIL_USUARIO,
            azure_oid=identidade.oid,
            ativo=True,
        )
        db.session.add(usuario)

    elif usuario.azure_oid and usuario.azure_oid != identidade.oid:
        current_app.logger.warning("SSO: %s ja vinculado a outra conta do Entra.", usuario.email)
        flash("Este e-mail já está vinculado a outra conta Microsoft. Procure a TI.", "erro")
        return redirect(url_for("auth.login"))

    if not usuario.ativo:
        db.session.rollback()
        flash("Seu acesso está inativo. Procure o administrador do sistema.", "erro")
        return redirect(url_for("auth.login"))

    if not usuario.azure_oid:
        # Primeiro acesso pela Microsoft de quem o administrador ja cadastrou.
        usuario.azure_oid = identidade.oid
        usuario.nome = identidade.nome or usuario.nome

    usuario.ultimo_acesso = agora()
    db.session.commit()
    login_user(usuario, remember=True)
    return redirect(destino or url_for("contatos.lista"))
