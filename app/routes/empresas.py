"""Organizacoes (no codigo e no banco: Empresa): qualquer pessoa cadastra, a qualquer momento, sem aprovacao.

"ABEL", "abel" e "Abel" sao a mesma empresa: o nome normalizado (sem
acentos, minusculo) e unico no banco.
"""

from flask import Blueprint, abort, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import func

from app.extensions import db
from app.models import Contato, Empresa
from app.services import contatos as servico
from app.services.permissoes import gestao_requerida
from app.services.texto import limpar, normalizar

bp = Blueprint("empresas", __name__, url_prefix="/empresas")


@bp.before_request
@login_required
def exigir_login():
    return None


def _contagem_por_empresa() -> dict:
    return dict(
        db.session.query(Contato.empresa_id, func.count(Contato.id))
        .filter(Contato.excluido_em.is_(None), Contato.empresa_id.isnot(None))
        .group_by(Contato.empresa_id)
        .all()
    )


@bp.route("/", methods=["GET", "POST"])
def lista():
    if request.method == "POST":
        nome = limpar(request.form.get("nome"))
        if not nome:
            flash("Informe o nome da organização.", "erro")
        else:
            empresa, criada = servico.obter_ou_criar_empresa(nome, current_user)
            db.session.commit()
            if criada:
                flash(f"Organização “{empresa.nome}” cadastrada.", "sucesso")
            else:
                flash(f"A organização já existia como “{empresa.nome}”.", "info")
        return redirect(url_for("empresas.lista", q=request.args.get("q", "")))

    q = (request.args.get("q") or "").strip()
    consulta = Empresa.query
    for termo in normalizar(q).split():
        consulta = consulta.filter(Empresa.nome_normalizado.contains(termo, autoescape=True))
    empresas = consulta.order_by(Empresa.nome_normalizado).all()
    return render_template("empresas/lista.html", empresas=empresas, q=q, contagem=_contagem_por_empresa())


@bp.route("/buscar")
def buscar():
    """Sugestoes para o campo Empresa da ficha (autocompletar)."""
    termos = normalizar(request.args.get("q")).split()
    if not termos:
        return jsonify([])
    consulta = Empresa.query
    for termo in termos:
        consulta = consulta.filter(Empresa.nome_normalizado.contains(termo, autoescape=True))
    empresas = consulta.order_by(Empresa.nome_normalizado).limit(10).all()
    return jsonify([{"id": e.id, "nome": e.nome} for e in empresas])


@bp.route("/criar", methods=["POST"])
def criar():
    """Cadastro rapido direto do campo Empresa da ficha."""
    dados = request.get_json(silent=True) or {}
    nome = limpar(dados.get("nome"))
    if not nome:
        return jsonify({"erro": "Informe o nome da organização."}), 400
    empresa, criada = servico.obter_ou_criar_empresa(nome[:255], current_user)
    db.session.commit()
    return jsonify({"id": empresa.id, "nome": empresa.nome, "criada": criada})


@bp.route("/<int:empresa_id>/renomear", methods=["POST"])
@gestao_requerida
def renomear(empresa_id):
    empresa = db.session.get(Empresa, empresa_id) or abort(404)
    nome = limpar(request.form.get("nome"))
    if not nome:
        flash("Informe o novo nome.", "erro")
        return redirect(url_for("empresas.lista"))
    outra = servico.buscar_empresa(nome)
    if outra and outra.id != empresa.id:
        flash(f"Já existe a organização “{outra.nome}”.", "erro")
        return redirect(url_for("empresas.lista"))
    empresa.definir_nome(nome[:255])
    for contato in empresa.contatos:
        servico.atualizar_busca(contato)
    db.session.commit()
    flash("Nome da organização atualizado.", "sucesso")
    return redirect(url_for("empresas.lista"))


@bp.route("/<int:empresa_id>/excluir", methods=["POST"])
@gestao_requerida
def excluir(empresa_id):
    empresa = db.session.get(Empresa, empresa_id) or abort(404)
    ativos = empresa.contatos.filter(Contato.excluido_em.is_(None)).count()
    if ativos:
        flash(f"“{empresa.nome}” tem {ativos} contato(s) e não pode ser excluída.", "erro")
        return redirect(url_for("empresas.lista"))
    for contato in empresa.contatos:  # fichas ja excluidas
        contato.empresa = None
    db.session.delete(empresa)
    db.session.commit()
    flash("Organização excluída.", "sucesso")
    return redirect(url_for("empresas.lista"))
