"""Relatorios (gestor de dados e administrador): historico de alteracoes e
de solicitacoes, com filtros e exportacao para planilha (CSV)."""

import csv
import io
from datetime import datetime, timedelta

from flask import Blueprint, Response, render_template, request
from flask_login import login_required

from app import constants as c
from app.models import Historico, Solicitacao, Usuario
from app.services.permissoes import gestao_requerida

bp = Blueprint("relatorios", __name__, url_prefix="/relatorios")

POR_PAGINA = 50


@bp.before_request
@login_required
@gestao_requerida
def exigir_gestao():
    return None


def _data(nome):
    try:
        return datetime.strptime(request.args.get(nome, ""), "%Y-%m-%d")
    except ValueError:
        return None


def _filtros():
    return {
        "aba": request.args.get("aba") if request.args.get("aba") in ("historico", "solicitacoes") else "historico",
        "de": _data("de"),
        "ate": _data("ate"),
        "contato": (request.args.get("contato") or "").strip(),
        "usuario": request.args.get("usuario", type=int),
        "acao": request.args.get("acao") if request.args.get("acao") in c.ACOES else "",
        "origem": request.args.get("origem") if request.args.get("origem") in c.ORIGENS else "",
        "status": request.args.get("status") if request.args.get("status") in c.STATUS_SOLICITACAO else "",
        "tipo": request.args.get("tipo") if request.args.get("tipo") in c.TIPOS_SOLICITACAO else "",
    }


def _consulta_historico(f):
    consulta = Historico.query
    if f["de"]:
        consulta = consulta.filter(Historico.criado_em >= f["de"])
    if f["ate"]:
        consulta = consulta.filter(Historico.criado_em < f["ate"] + timedelta(days=1))
    if f["contato"]:
        consulta = consulta.filter(Historico.contato_nome.contains(f["contato"], autoescape=True))
    if f["usuario"]:
        consulta = consulta.filter(Historico.usuario_id == f["usuario"])
    if f["acao"]:
        consulta = consulta.filter(Historico.acao == f["acao"])
    if f["origem"]:
        consulta = consulta.filter(Historico.origem == f["origem"])
    return consulta.order_by(Historico.criado_em.desc(), Historico.id.desc())


def _consulta_solicitacoes(f):
    consulta = Solicitacao.query
    if f["de"]:
        consulta = consulta.filter(Solicitacao.criado_em >= f["de"])
    if f["ate"]:
        consulta = consulta.filter(Solicitacao.criado_em < f["ate"] + timedelta(days=1))
    if f["contato"]:
        consulta = consulta.filter(Solicitacao.contato_nome.contains(f["contato"], autoescape=True))
    if f["usuario"]:
        consulta = consulta.filter(
            (Solicitacao.solicitante_id == f["usuario"]) | (Solicitacao.decidido_por_id == f["usuario"])
        )
    if f["status"]:
        consulta = consulta.filter(Solicitacao.status == f["status"])
    if f["tipo"]:
        consulta = consulta.filter(Solicitacao.tipo == f["tipo"])
    return consulta.order_by(Solicitacao.criado_em.desc(), Solicitacao.id.desc())


@bp.route("/")
def index():
    f = _filtros()
    consulta = _consulta_historico(f) if f["aba"] == "historico" else _consulta_solicitacoes(f)
    paginacao = consulta.paginate(page=request.args.get("pagina", 1, type=int), per_page=POR_PAGINA, error_out=False)
    return render_template(
        "relatorios/index.html",
        f=f,
        paginacao=paginacao,
        usuarios=Usuario.query.order_by(Usuario.nome).all(),
        rotulos=c.ROTULOS,
    )


def _linhas_mudancas(mudancas: dict) -> str:
    return " | ".join(
        f"{c.ROTULOS.get(k, k)}: {(v[0] if isinstance(v, list) else v.get('de')) or '(vazio)'} → "
        f"{(v[1] if isinstance(v, list) else v.get('para')) or '(vazio)'}"
        for k, v in (mudancas or {}).items()
    )


@bp.route("/exportar")
def exportar():
    f = _filtros()
    saida = io.StringIO()
    escritor = csv.writer(saida, delimiter=";")
    fmt = "%d/%m/%Y %H:%M"

    if f["aba"] == "historico":
        escritor.writerow(["Data", "Contato", "Ficha nº", "Ação", "Origem", "Feita por", "Solicitação nº", "Mudanças"])
        for h in _consulta_historico(f).all():
            escritor.writerow([
                h.criado_em.strftime(fmt), h.contato_nome or "", h.contato_id or "",
                h.rotulo_acao, h.rotulo_origem, h.usuario.nome if h.usuario else "",
                h.solicitacao_id or "", _linhas_mudancas(h.mudancas),
            ])
    else:
        escritor.writerow([
            "Nº", "Data do pedido", "Tipo", "Contato", "Solicitante", "Situação",
            "Decidida por", "Data da decisão", "Motivo", "Comentário do solicitante", "Mudanças pedidas",
        ])
        for s in _consulta_solicitacoes(f).all():
            escritor.writerow([
                s.id, s.criado_em.strftime(fmt), s.rotulo_tipo, s.contato_nome or "",
                s.solicitante.nome, s.rotulo_status, s.decidido_por.nome if s.decidido_por else "",
                s.decidido_em.strftime(fmt) if s.decidido_em else "", s.motivo_decisao or "",
                s.comentario or "", _linhas_mudancas(s.mudancas),
            ])

    nome = f"contatos-{f['aba']}-{datetime.now():%Y%m%d-%H%M}.csv"
    # BOM UTF-8 para o Excel abrir os acentos corretamente.
    return Response(
        "﻿" + saida.getvalue(),
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{nome}"'},
    )
