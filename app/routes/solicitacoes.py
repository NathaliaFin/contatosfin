"""Solicitacoes: fila do gestor de dados e "minhas solicitacoes" do usuario."""

from flask import Blueprint, abort, flash, redirect, render_template, request, send_file, url_for
from flask_login import current_user, login_required

from app import constants as c
from app.extensions import db
from app.models import Solicitacao
from app.services import contatos as servico
from app.services import email as servico_email
from app.services import fotos
from app.services.permissoes import gestao_requerida

bp = Blueprint("solicitacoes", __name__, url_prefix="/solicitacoes")


@bp.before_request
@login_required
def exigir_login():
    return None


def _solicitacao_visivel(solicitacao_id: int) -> Solicitacao:
    solicitacao = db.session.get(Solicitacao, solicitacao_id)
    if solicitacao is None:
        abort(404)
    if not current_user.pode_gerir and solicitacao.solicitante_id != current_user.id:
        abort(403)
    return solicitacao


@bp.route("/")
def lista():
    if current_user.pode_gerir:
        pendentes = (
            Solicitacao.query.filter_by(status=c.STATUS_PENDENTE)
            .order_by(Solicitacao.criado_em).all()
        )
        decididas = (
            Solicitacao.query.filter(Solicitacao.status != c.STATUS_PENDENTE)
            .order_by(Solicitacao.decidido_em.desc()).limit(30).all()
        )
        return render_template("solicitacoes/lista.html", pendentes=pendentes, decididas=decididas, minhas=None)

    minhas = (
        Solicitacao.query.filter_by(solicitante_id=current_user.id)
        .order_by(Solicitacao.criado_em.desc()).all()
    )
    return render_template("solicitacoes/lista.html", pendentes=None, decididas=None, minhas=minhas)


@bp.route("/<int:solicitacao_id>")
def detalhe(solicitacao_id):
    solicitacao = _solicitacao_visivel(solicitacao_id)
    return render_template(
        "solicitacoes/detalhe.html",
        s=solicitacao,
        atual=servico.situacao_atual(solicitacao) if solicitacao.pendente else {},
        rotulos=c.ROTULOS,
        repetidas=servico.repetidas_do_pedido(solicitacao) if current_user.pode_gerir else [],
    )


@bp.route("/<int:solicitacao_id>/foto")
def foto(solicitacao_id):
    solicitacao = _solicitacao_visivel(solicitacao_id)
    if not solicitacao.foto_proposta or not fotos.caminho(solicitacao.foto_proposta).exists():
        abort(404)
    resposta = send_file(fotos.caminho(solicitacao.foto_proposta), mimetype="image/jpeg", max_age=0)
    resposta.headers["Cache-Control"] = "private, no-store"
    return resposta


def _comunicar_decisao(solicitacao, mensagem):
    enviado = servico_email.notificar_decisao(solicitacao)
    flash(mensagem + (" O solicitante foi avisado por e-mail." if enviado else ""), "sucesso")


@bp.route("/<int:solicitacao_id>/aprovar", methods=["POST"])
@gestao_requerida
def aprovar(solicitacao_id):
    solicitacao = _solicitacao_visivel(solicitacao_id)
    try:
        servico.aprovar(solicitacao, current_user, request.form.get("motivo"))
    except servico.ErroSolicitacao as erro:
        db.session.rollback()
        flash(str(erro), "erro")
        return redirect(url_for("solicitacoes.detalhe", solicitacao_id=solicitacao_id))
    db.session.commit()
    _comunicar_decisao(solicitacao, "Solicitação aprovada e aplicada à ficha.")
    return redirect(url_for("solicitacoes.lista"))


@bp.route("/<int:solicitacao_id>/recusar", methods=["POST"])
@gestao_requerida
def recusar(solicitacao_id):
    solicitacao = _solicitacao_visivel(solicitacao_id)
    try:
        servico.recusar(solicitacao, current_user, request.form.get("motivo"))
    except servico.ErroSolicitacao as erro:
        flash(str(erro), "erro")
        return redirect(url_for("solicitacoes.detalhe", solicitacao_id=solicitacao_id))
    db.session.commit()
    _comunicar_decisao(solicitacao, "Solicitação recusada.")
    return redirect(url_for("solicitacoes.lista"))


@bp.route("/<int:solicitacao_id>/cancelar", methods=["POST"])
def cancelar(solicitacao_id):
    solicitacao = _solicitacao_visivel(solicitacao_id)
    try:
        servico.cancelar(solicitacao, current_user)
    except servico.ErroSolicitacao as erro:
        flash(str(erro), "erro")
        return redirect(url_for("solicitacoes.detalhe", solicitacao_id=solicitacao_id))
    db.session.commit()
    flash("Solicitação cancelada.", "sucesso")
    return redirect(url_for("solicitacoes.lista"))
