"""Fichario de contatos: consulta, ficha, cadastro (gestor) e pedidos (usuario)."""

from flask import Blueprint, Response, abort, flash, redirect, render_template, request, send_file, url_for
from flask_login import current_user, login_required
from sqlalchemy import func
from sqlalchemy.orm import joinedload

from app import constants as c
from app.extensions import db
from app.models import Contato, Empresa, Grupo, Historico, Solicitacao, agora
from app.services import compartilhar
from app.services import contatos as servico
from app.services import duplicidade
from app.services import email as servico_email
from app.services import fotos
from app.services.permissoes import gestao_requerida
from app.services.texto import normalizar

bp = Blueprint("contatos", __name__)

POR_PAGINA = 24
LETRAS = [chr(x) for x in range(ord("A"), ord("Z") + 1)]


@bp.before_request
@login_required
def exigir_login():
    return None


def _contato_ou_404(contato_id: int) -> Contato:
    contato = db.session.get(Contato, contato_id)
    if contato is None or contato.excluido_em is not None:
        abort(404)
    return contato


def _grupos_do_formulario(selecionados=()):
    """Grupos ativos + inativos que ja estejam marcados na ficha, em ordem
    alfabetica (sem diferenca de acentos e maiusculas) para achar rapido."""
    grupos = Grupo.ordenados(apenas_ativos=False)
    marcados = set(selecionados or [])
    return sorted((g for g in grupos if g.ativo or g.id in marcados), key=lambda g: (normalizar(g.nome), g.id))


def _render_form(modo, valores, contato=None, erros=None, comentario="", status=200, repetidas=None):
    arquivo = request.files.get("foto") if request.method == "POST" else None
    return (
        render_template(
            "contatos/form.html",
            modo=modo,
            valores=valores,
            contato=contato,
            erros=erros or {},
            comentario=comentario,
            grupos=_grupos_do_formulario(valores.get("grupos")),
            incluir_restritos=current_user.pode_gerir,
            repetidas=repetidas or [],
            trava_repetida=duplicidade.trava(repetidas or []),
            foto_enviada=bool(arquivo and arquivo.filename),
        ),
        status,
    )


def _barrar_repetida(modo, valores, contato=None, anteriores=None, comentario=""):
    """Confere se a ficha ja existe. Devolve o formulario de volta, com o
    aviso, ou None para seguir gravando.

    E-mail repetido trava sempre. Nome ou celular repetido so passa depois
    que a pessoa confirma que e outra pessoa (botao do aviso).
    """
    repetidas = duplicidade.procurar(valores, ignorar_contato=contato, anteriores=anteriores)
    if not repetidas:
        return None
    if duplicidade.trava(repetidas):
        erros = {"email": duplicidade.erro_email(repetidas)}
        return _render_form(modo, valores, contato, erros, comentario, 409, repetidas)
    if request.form.get("confirmar_repetido"):
        return None
    return _render_form(modo, valores, contato, None, comentario, 409, repetidas)


# ---------------------------------------------------------------------------
# Consulta
# ---------------------------------------------------------------------------
@bp.route("/")
def inicio():
    return redirect(url_for("contatos.lista"))


@bp.route("/contatos")
def lista():
    q = (request.args.get("q") or "").strip()
    grupo_id = request.args.get("grupo", type=int)
    empresa_id = request.args.get("empresa", type=int)
    letra = (request.args.get("letra") or "").upper()[:1]
    so_pendentes = bool(request.args.get("pendentes"))
    pagina = request.args.get("pagina", 1, type=int)

    consulta = Contato.ativos()
    for termo in normalizar(q).split():
        consulta = consulta.filter(Contato.busca.contains(termo, autoescape=True))
    if grupo_id:
        consulta = consulta.filter(Contato.grupos.any(Grupo.id == grupo_id))
    if empresa_id:
        consulta = consulta.filter(Contato.empresa_id == empresa_id)
    if so_pendentes:
        consulta = consulta.filter(Contato.id.in_(servico.ids_com_pendencia() or {0}))

    # Letras com contato, considerando os demais filtros (as vazias ficam apagadas).
    contagem = dict(
        consulta.with_entities(Contato.letra, func.count(Contato.id)).group_by(Contato.letra).all()
    )
    if letra:
        consulta = consulta.filter(Contato.letra == letra)

    paginacao = consulta.order_by(Contato.busca, Contato.id).paginate(
        page=pagina, per_page=POR_PAGINA, error_out=False
    )
    pendentes = servico.ids_com_pendencia(item.id for item in paginacao.items)

    return render_template(
        "contatos/lista.html",
        paginacao=paginacao,
        contatos=paginacao.items,
        pendentes=pendentes,
        links_whats={item.id: compartilhar.link_compartilhar(item) for item in paginacao.items},
        letras=LETRAS,
        contagem=contagem,
        filtros={"q": q, "grupo": grupo_id, "empresa": empresa_id, "letra": letra, "pendentes": so_pendentes},
        grupos=Grupo.ordenados(),
        empresa_filtro=db.session.get(Empresa, empresa_id) if empresa_id else None,
        total=sum(contagem.values()),
    )


@bp.route("/contatos/<int:contato_id>")
def ficha(contato_id):
    contato = _contato_ou_404(contato_id)
    abertas = contato.solicitacoes.filter_by(status=c.STATUS_PENDENTE).order_by(Solicitacao.criado_em).all()
    if not current_user.pode_gerir:
        visiveis = [s for s in abertas if s.solicitante_id == current_user.id]
    else:
        visiveis = abertas
    historico = []
    if current_user.pode_gerir:
        historico = (
            Historico.query.filter_by(contato_id=contato.id)
            .order_by(Historico.criado_em.desc(), Historico.id.desc())
            .limit(8)
            .all()
        )
    return render_template(
        "contatos/ficha.html",
        contato=contato,
        whatsapp={
            "texto": compartilhar.texto_whatsapp(contato),
            "link": compartilhar.link_compartilhar(contato),
            "aplicativo": compartilhar.link_aplicativo(contato),
        },
        pendente=any(s.tipo in (c.TIPO_ALTERACAO, c.TIPO_EXCLUSAO) for s in abertas),
        solicitacoes=visiveis,
        historico=historico,
        mostrar_restritos=current_user.pode_gerir,
    )


@bp.route("/contatos/<int:contato_id>/foto")
def foto(contato_id):
    contato = _contato_ou_404(contato_id)
    if not contato.foto or not fotos.caminho(contato.foto).exists():
        abort(404)
    resposta = send_file(fotos.caminho(contato.foto), mimetype="image/jpeg", max_age=0)
    resposta.headers["Cache-Control"] = "private, max-age=300"
    return resposta


@bp.route("/contatos/<int:contato_id>/cartao.vcf")
def cartao(contato_id):
    contato = _contato_ou_404(contato_id)
    nome = compartilhar.nome_arquivo(contato)
    return Response(
        compartilhar.vcard(contato),
        mimetype="text/vcard",
        headers={"Content-Disposition": f'attachment; filename="{nome}"', "Cache-Control": "private, no-store"},
    )


# ---------------------------------------------------------------------------
# Listas de trabalho: participantes e impressao
# ---------------------------------------------------------------------------
MODOS_IMPRESSAO = {
    "dados": "Nomes e dados de contato",
    "nomes": "Só os nomes",
    "fotos": "Dados de contato com foto",
}


def _lista_ou_404(grupo_id: int) -> Grupo:
    grupo = db.session.get(Grupo, grupo_id)
    if grupo is None:
        abort(404)
    return grupo


def _participantes(grupo: Grupo):
    return (
        Contato.ativos()
        .filter(Contato.grupos.any(Grupo.id == grupo.id))
        .order_by(Contato.busca, Contato.id)
        .all()
    )


@bp.route("/listas/<int:grupo_id>")
def lista_trabalho(grupo_id):
    grupo = _lista_ou_404(grupo_id)
    participantes = _participantes(grupo)
    return render_template(
        "contatos/lista_trabalho.html",
        grupo=grupo,
        contatos=participantes,
        pendentes=servico.ids_com_pendencia(ct.id for ct in participantes),
        links_whats={ct.id: compartilhar.link_compartilhar(ct) for ct in participantes},
        modos=MODOS_IMPRESSAO,
    )


@bp.route("/listas/<int:grupo_id>/participantes", methods=["GET", "POST"])
@gestao_requerida
def lista_participantes(grupo_id):
    """Marcar quem entra e quem sai da lista, sem abrir ficha por ficha.

    Cada ficha que muda ganha uma linha no historico, como numa edicao. So
    mexe nas fichas que estavam na tela (``vistos``): quem outra pessoa
    incluiu enquanto isso nao sai por engano.
    """
    grupo = _lista_ou_404(grupo_id)
    if request.method == "POST":
        vistos = {int(x) for x in request.form.getlist("vistos") if x.isdigit()}
        marcados = {int(x) for x in request.form.getlist("marcados") if x.isdigit()} & vistos
        entraram = sairam = 0
        fichas = Contato.ativos().filter(Contato.id.in_(vistos)).all() if vistos else []
        for ct in fichas:
            atuais = {g.id for g in ct.grupos}
            quer = ct.id in marcados
            if (grupo.id in atuais) == quer:
                continue
            novos = sorted(atuais | {grupo.id}) if quer else sorted(atuais - {grupo.id})
            servico.editar_contato(ct, {"grupos": novos}, current_user)
            entraram += quer
            sairam += not quer
        db.session.commit()
        if entraram or sairam:
            partes = []
            if entraram:
                partes.append(f"{entraram} contato{'s' if entraram > 1 else ''} entr{'aram' if entraram > 1 else 'ou'}")
            if sairam:
                partes.append(f"{sairam} sa{'íram' if sairam > 1 else 'iu'}")
            flash(f"Lista “{grupo.nome}” atualizada: " + " e ".join(partes) + ".", "sucesso")
        else:
            flash("Nenhuma mudança na lista.", "info")
        return redirect(url_for("contatos.lista_trabalho", grupo_id=grupo.id))

    contatos = Contato.ativos().options(joinedload(Contato.empresa)).order_by(Contato.busca, Contato.id).all()
    membros = {ct.id for ct in contatos if any(g.id == grupo.id for g in ct.grupos)}
    return render_template("contatos/lista_participantes.html", grupo=grupo, contatos=contatos, membros=membros)


@bp.route("/listas/<int:grupo_id>/imprimir")
def lista_imprimir(grupo_id):
    grupo = _lista_ou_404(grupo_id)
    modo = request.args.get("modo") if request.args.get("modo") in MODOS_IMPRESSAO else "dados"
    return render_template(
        "contatos/lista_impressao.html",
        grupo=grupo,
        contatos=_participantes(grupo),
        modo=modo,
        modos=MODOS_IMPRESSAO,
        gerada_em=agora(),
    )


# ---------------------------------------------------------------------------
# Gestor de dados / administrador: alteracao direta
# ---------------------------------------------------------------------------
@bp.route("/contatos/novo", methods=["GET", "POST"])
@gestao_requerida
def novo():
    if request.method == "GET":
        return _render_form("novo", servico.valores_do_contato(None, True))

    valores, erros = servico.ler_formulario(request.form, incluir_restritos=True)
    if erros:
        return _render_form("novo", valores, erros=erros, status=400)
    barrada = _barrar_repetida("novo", valores)
    if barrada:
        return barrada
    try:
        nome_foto = fotos.salvar_upload(request.files.get("foto"))
    except fotos.ErroFoto as erro:
        return _render_form("novo", valores, erros={"foto": str(erro)}, status=400)

    contato = servico.criar_contato(valores, current_user, foto=nome_foto)
    db.session.commit()
    flash("Ficha cadastrada.", "sucesso")
    return redirect(url_for("contatos.ficha", contato_id=contato.id))


@bp.route("/contatos/<int:contato_id>/editar", methods=["GET", "POST"])
@gestao_requerida
def editar(contato_id):
    contato = _contato_ou_404(contato_id)
    if request.method == "GET":
        return _render_form("editar", servico.valores_do_contato(contato, True), contato)

    valores, erros = servico.ler_formulario(request.form, incluir_restritos=True)
    if erros:
        return _render_form("editar", valores, contato, erros, status=400)
    barrada = _barrar_repetida("editar", valores, contato, servico.valores_do_contato(contato, True))
    if barrada:
        return barrada
    try:
        nome_foto = fotos.salvar_upload(request.files.get("foto"))
    except fotos.ErroFoto as erro:
        return _render_form("editar", valores, contato, {"foto": str(erro)}, status=400)

    mudancas = servico.editar_contato(
        contato, valores, current_user, foto=nome_foto, remover_foto=bool(request.form.get("remover_foto"))
    )
    db.session.commit()
    flash("Ficha atualizada." if mudancas else "Nenhum dado foi alterado.", "sucesso" if mudancas else "info")
    return redirect(url_for("contatos.ficha", contato_id=contato.id))


@bp.route("/contatos/<int:contato_id>/excluir", methods=["POST"])
@gestao_requerida
def excluir(contato_id):
    contato = _contato_ou_404(contato_id)
    servico.excluir_contato(contato, current_user)
    db.session.commit()
    flash(f"A ficha de {contato.nome_exibicao} foi excluída.", "sucesso")
    return redirect(url_for("contatos.lista"))


# ---------------------------------------------------------------------------
# Usuario comum: solicitacoes ao gestor de dados
# ---------------------------------------------------------------------------
def _avisar_gestores(solicitacao) -> None:
    enviado = servico_email.notificar_nova_solicitacao(solicitacao)
    solicitacao.email_enviado = enviado
    db.session.commit()
    if enviado:
        flash("Solicitação enviada. O gestor de dados foi avisado por e-mail.", "sucesso")
    else:
        flash(
            "Solicitação registrada e aguardando o gestor de dados. "
            "O aviso por e-mail não pôde ser enviado agora.",
            "aviso",
        )


@bp.route("/contatos/<int:contato_id>/solicitar-alteracao", methods=["GET", "POST"])
def solicitar_alteracao(contato_id):
    contato = _contato_ou_404(contato_id)
    if current_user.pode_gerir:
        return redirect(url_for("contatos.editar", contato_id=contato.id))

    if request.method == "GET":
        return _render_form("solicitar", servico.valores_do_contato(contato, False), contato)

    comentario = request.form.get("comentario") or ""
    valores, erros = servico.ler_formulario(request.form, incluir_restritos=False)
    if erros:
        return _render_form("solicitar", valores, contato, erros, comentario, 400)
    barrada = _barrar_repetida("solicitar", valores, contato, servico.valores_do_contato(contato, False), comentario)
    if barrada:
        return barrada
    try:
        nome_foto = fotos.salvar_upload(request.files.get("foto"))
    except fotos.ErroFoto as erro:
        return _render_form("solicitar", valores, contato, {"foto": str(erro)}, comentario, 400)

    solicitacao = servico.solicitar_alteracao(
        contato, valores, current_user, comentario,
        foto=nome_foto, remover_foto=bool(request.form.get("remover_foto")),
    )
    if solicitacao is None:
        flash("Nenhum dado foi alterado — não há o que solicitar.", "aviso")
        return _render_form("solicitar", valores, contato, comentario=comentario, status=400)

    db.session.commit()
    _avisar_gestores(solicitacao)
    return redirect(url_for("contatos.ficha", contato_id=contato.id))


@bp.route("/contatos/<int:contato_id>/solicitar-exclusao", methods=["POST"])
def solicitar_exclusao(contato_id):
    contato = _contato_ou_404(contato_id)
    if current_user.pode_gerir:
        abort(400)
    solicitacao = servico.solicitar_exclusao(contato, current_user, request.form.get("comentario"))
    db.session.commit()
    _avisar_gestores(solicitacao)
    return redirect(url_for("contatos.ficha", contato_id=contato.id))


@bp.route("/contatos/solicitar-inclusao", methods=["GET", "POST"])
def solicitar_inclusao():
    if current_user.pode_gerir:
        return redirect(url_for("contatos.novo"))

    if request.method == "GET":
        return _render_form("incluir", servico.valores_do_contato(None, False))

    comentario = request.form.get("comentario") or ""
    valores, erros = servico.ler_formulario(request.form, incluir_restritos=False)
    if erros:
        return _render_form("incluir", valores, erros=erros, comentario=comentario, status=400)
    barrada = _barrar_repetida("incluir", valores, comentario=comentario)
    if barrada:
        return barrada
    try:
        nome_foto = fotos.salvar_upload(request.files.get("foto"))
    except fotos.ErroFoto as erro:
        return _render_form("incluir", valores, erros={"foto": str(erro)}, comentario=comentario, status=400)

    solicitacao = servico.solicitar_inclusao(valores, current_user, comentario, foto=nome_foto)
    if solicitacao is None:
        flash("Preencha ao menos um dado da ficha.", "aviso")
        return _render_form("incluir", valores, comentario=comentario, status=400)

    db.session.commit()
    _avisar_gestores(solicitacao)
    return redirect(url_for("solicitacoes.detalhe", solicitacao_id=solicitacao.id))
