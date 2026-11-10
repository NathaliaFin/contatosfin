"""Administracao: usuarios e perfis (administrador) e listas de trabalho
(gestor de dados e administrador)."""

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import func

from app import constants as c
from app.extensions import db
from app.models import Grupo, Usuario, contato_grupo, Contato
from app.services.permissoes import admin_requerido, gestao_requerida
from app.services.texto import limpar
from app.services.validacao import email_valido

bp = Blueprint("admin", __name__, url_prefix="/admin")

SENHA_MINIMA = 10


@bp.before_request
@login_required
def exigir_login():
    return None


# ---------------------------------------------------------------------------
# Usuarios
# ---------------------------------------------------------------------------
@bp.route("/usuarios")
@admin_requerido
def usuarios():
    q = (request.args.get("q") or "").strip().lower()
    perfil = request.args.get("perfil") if request.args.get("perfil") in c.PERFIS else ""
    consulta = Usuario.query
    if q:
        consulta = consulta.filter(
            func.lower(Usuario.nome).contains(q, autoescape=True) | Usuario.email.contains(q, autoescape=True)
        )
    if perfil:
        consulta = consulta.filter(Usuario.perfil == perfil)
    lista = consulta.order_by(Usuario.ativo.desc(), Usuario.nome).all()
    return render_template("admin/usuarios.html", usuarios=lista, q=q, perfil=perfil)


def _ler_usuario(form, usuario=None):
    dados = {
        "nome": limpar(form.get("nome")) or "",
        "email": (form.get("email") or "").strip().lower(),
        "perfil": form.get("perfil") if form.get("perfil") in c.PERFIS else c.PERFIL_USUARIO,
        "ativo": bool(form.get("ativo")),
        "senha": form.get("senha") or "",
        "remover_senha": bool(form.get("remover_senha")),
    }
    erros = {}
    if not dados["nome"]:
        erros["nome"] = "Informe o nome."
    if not email_valido(dados["email"]):
        erros["email"] = "E-mail inválido."
    else:
        outro = Usuario.query.filter_by(email=dados["email"]).first()
        if outro and (usuario is None or outro.id != usuario.id):
            erros["email"] = "Já existe um usuário com este e-mail."
    if dados["senha"] and len(dados["senha"]) < SENHA_MINIMA:
        erros["senha"] = f"A senha precisa de ao menos {SENHA_MINIMA} caracteres."
    if usuario is not None and usuario.id == current_user.id:
        # Ninguem tira o proprio acesso de administrador por engano.
        if dados["perfil"] != c.PERFIL_ADMIN:
            erros["perfil"] = "Você não pode tirar o seu próprio perfil de administrador."
        if not dados["ativo"]:
            erros["ativo"] = "Você não pode desativar o seu próprio acesso."
    return dados, erros


@bp.route("/usuarios/novo", methods=["GET", "POST"])
@admin_requerido
def usuario_novo():
    if request.method == "POST":
        dados, erros = _ler_usuario(request.form)
        if not erros:
            usuario = Usuario(nome=dados["nome"], email=dados["email"], perfil=dados["perfil"], ativo=dados["ativo"])
            usuario.definir_senha(dados["senha"] or None)
            db.session.add(usuario)
            db.session.commit()
            flash(f"Usuário {usuario.nome} cadastrado como {usuario.rotulo_perfil}.", "sucesso")
            return redirect(url_for("admin.usuarios"))
        return render_template("admin/usuario_form.html", usuario=None, dados=dados, erros=erros), 400

    dados = {"nome": "", "email": "", "perfil": c.PERFIL_USUARIO, "ativo": True}
    return render_template("admin/usuario_form.html", usuario=None, dados=dados, erros={})


@bp.route("/usuarios/<int:usuario_id>", methods=["GET", "POST"])
@admin_requerido
def usuario_editar(usuario_id):
    usuario = db.session.get(Usuario, usuario_id) or abort(404)
    if request.method == "POST":
        dados, erros = _ler_usuario(request.form, usuario)
        if not erros:
            usuario.nome = dados["nome"]
            usuario.email = dados["email"]
            usuario.perfil = dados["perfil"]
            usuario.ativo = dados["ativo"]
            if dados["senha"]:
                usuario.definir_senha(dados["senha"])
            elif dados["remover_senha"]:
                usuario.definir_senha(None)
            db.session.commit()
            flash("Usuário atualizado.", "sucesso")
            return redirect(url_for("admin.usuarios"))
        return render_template("admin/usuario_form.html", usuario=usuario, dados=dados, erros=erros), 400

    dados = {"nome": usuario.nome, "email": usuario.email, "perfil": usuario.perfil, "ativo": usuario.ativo}
    return render_template("admin/usuario_form.html", usuario=usuario, dados=dados, erros={})


# ---------------------------------------------------------------------------
# Listas de trabalho (no codigo e no banco: Grupo)
# ---------------------------------------------------------------------------
@bp.route("/grupos", methods=["GET", "POST"])
@gestao_requerida
def grupos():
    if request.method == "POST":
        acao = request.form.get("acao")
        nome = limpar(request.form.get("nome"))
        grupo = db.session.get(Grupo, request.form.get("grupo_id", type=int) or 0)

        if acao == "criar":
            if not nome:
                flash("Informe o nome da lista.", "erro")
            elif Grupo.query.filter(func.lower(Grupo.nome) == nome.lower()).first():
                flash("Já existe uma lista com esse nome.", "erro")
            else:
                maior = db.session.query(func.max(Grupo.ordem)).scalar() or 0
                db.session.add(Grupo(nome=nome[:120], ordem=maior + 1))
                db.session.commit()
                flash(f"Lista “{nome}” criada.", "sucesso")
        elif grupo is None:
            abort(404)
        elif acao == "renomear":
            repetido = Grupo.query.filter(func.lower(Grupo.nome) == (nome or "").lower(), Grupo.id != grupo.id).first()
            if not nome or repetido:
                flash("Nome vazio ou já usado por outra lista.", "erro")
            else:
                grupo.nome = nome[:120]
                db.session.commit()
                flash("Lista renomeada.", "sucesso")
        elif acao == "alternar":
            grupo.ativo = not grupo.ativo
            db.session.commit()
            flash(f"Lista “{grupo.nome}” {'reativada' if grupo.ativo else 'desativada'}.", "sucesso")
        elif acao in ("subir", "descer"):
            lista = Grupo.ordenados(apenas_ativos=False)
            i = lista.index(grupo)
            j = i - 1 if acao == "subir" else i + 1
            if 0 <= j < len(lista):
                lista[i], lista[j] = lista[j], lista[i]
                for ordem, item in enumerate(lista, start=1):
                    item.ordem = ordem
                db.session.commit()
        return redirect(url_for("admin.grupos"))

    contagem = dict(
        db.session.query(contato_grupo.c.grupo_id, func.count(contato_grupo.c.contato_id))
        .join(Contato, Contato.id == contato_grupo.c.contato_id)
        .filter(Contato.excluido_em.is_(None))
        .group_by(contato_grupo.c.grupo_id)
        .all()
    )
    return render_template("admin/grupos.html", grupos=Grupo.ordenados(apenas_ativos=False), contagem=contagem)
