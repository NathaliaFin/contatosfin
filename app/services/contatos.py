"""Regras da ficha de contato: leitura do formulario, comparacao, gravacao,
historico, solicitacoes e aprovacoes.

Um "valores" e um dicionario {campo: valor} no formato interno:
- texto simples: str ou None
- empresa: nome da empresa (str) ou None
- grupos: lista ordenada de ids
"""

from sqlalchemy.exc import IntegrityError

from app import constants as c
from app.extensions import db
from app.models import Contato, Empresa, Grupo, Historico, Solicitacao, agora
from app.services import fotos
from app.services import validacao as v
from app.services.texto import letra_indice, limpar, normalizar


class ErroSolicitacao(ValueError):
    """Operacao impossivel, com texto pronto para a tela."""


# ---------------------------------------------------------------------------
# Leitura do formulario
# ---------------------------------------------------------------------------
def ler_formulario(form, incluir_restritos: bool) -> tuple[dict, dict]:
    """Le e confere os campos enviados. Devolve (valores, erros)."""
    valores: dict = {}
    erros: dict = {}

    for campo in c.CAMPOS:
        if campo.restrito and not incluir_restritos:
            continue

        if campo.tipo == "grupos":
            ids = {int(x) for x in form.getlist("grupos") if str(x).isdigit()}
            valores["grupos"] = (
                sorted(g.id for g in Grupo.query.filter(Grupo.id.in_(ids)).all()) if ids else []
            )
            continue

        bruto = form.get(campo.chave) or ""
        if campo.tipo == "textarea":
            valor = bruto.replace("\r\n", "\n").strip() or None
        else:
            valor = limpar(bruto)

        if valor:
            if campo.tipo != "textarea" and len(valor) > campo.tamanho:
                erros[campo.chave] = f"Use no máximo {campo.tamanho} caracteres."
            elif campo.tipo == "email":
                valor = valor.lower()
                if not v.email_valido(valor):
                    erros[campo.chave] = "E-mail em formato inválido."
            elif campo.tipo == "telefone":
                if not v.telefone_valido(valor):
                    erros[campo.chave] = "Telefone em formato inválido."
                else:
                    valor = v.formatar_telefone(valor)
            elif campo.tipo == "cpf":
                if not v.cpf_valido(valor):
                    erros[campo.chave] = "CPF inválido (confira os dígitos)."
                else:
                    valor = v.formatar_cpf(valor)
            elif campo.tipo == "cnpj":
                if not v.cnpj_valido(valor):
                    erros[campo.chave] = "CNPJ inválido (confira os dígitos)."
                else:
                    valor = v.formatar_cnpj(valor)

        valores[campo.chave] = valor

    return valores, erros


def valores_do_contato(contato: Contato | None, incluir_restritos: bool) -> dict:
    valores: dict = {}
    for campo in c.CAMPOS:
        if campo.restrito and not incluir_restritos:
            continue
        if contato is None:
            valores[campo.chave] = [] if campo.tipo == "grupos" else None
        elif campo.tipo == "empresa":
            valores["empresa"] = contato.empresa.nome if contato.empresa else None
        elif campo.tipo == "grupos":
            valores["grupos"] = sorted(g.id for g in contato.grupos)
        else:
            valores[campo.chave] = getattr(contato, campo.chave)
    return valores


# ---------------------------------------------------------------------------
# Comparacao e exibicao
# ---------------------------------------------------------------------------
def _iguais(chave: str, a, b) -> bool:
    if chave == "empresa":
        return normalizar(a) == normalizar(b)
    if chave == "grupos":
        return sorted(a or []) == sorted(b or [])
    return (a or None) == (b or None)


def texto(chave: str, valor) -> str:
    """Valor em texto legivel, para historico, e-mail e tela de aprovacao."""
    if chave == "grupos":
        if not valor:
            return ""
        nomes = {g.id: g.nome for g in Grupo.query.filter(Grupo.id.in_(valor)).all()}
        return "; ".join(nomes.get(i, f"(lista {i} removida)") for i in valor)
    return "" if valor is None else str(valor)


def diferencas(atual: dict, novo: dict, ocultar_restritos: bool = False) -> dict:
    """{campo: {"de": texto, "para": texto}} apenas do que mudou."""
    mudou = {}
    for chave, valor in novo.items():
        anterior = atual.get(chave)
        if _iguais(chave, anterior, valor):
            continue
        campo = c.CAMPOS_POR_CHAVE.get(chave)
        if ocultar_restritos and campo and campo.restrito:
            mudou[chave] = {
                "de": c.VALOR_RESTRITO if anterior else "",
                "para": c.VALOR_RESTRITO if valor else "",
            }
        else:
            mudou[chave] = {"de": texto(chave, anterior), "para": texto(chave, valor)}
    return mudou


# ---------------------------------------------------------------------------
# Empresas
# ---------------------------------------------------------------------------
def buscar_empresa(nome: str | None) -> Empresa | None:
    chave = normalizar(nome)[:255]
    return Empresa.query.filter_by(nome_normalizado=chave).first() if chave else None


def obter_ou_criar_empresa(nome: str | None, usuario) -> tuple[Empresa | None, bool]:
    """Devolve (empresa, criada_agora). "abel" encontra "ABEL"."""
    nome = limpar(nome)
    if not nome:
        return None, False
    existente = buscar_empresa(nome)
    if existente:
        return existente, False
    empresa = Empresa(criado_por=usuario)
    empresa.definir_nome(nome[:255])
    try:
        with db.session.begin_nested():
            db.session.add(empresa)
    except IntegrityError:
        # Outra pessoa cadastrou o mesmo nome no mesmo instante.
        return buscar_empresa(nome), False
    return empresa, True


# ---------------------------------------------------------------------------
# Gravacao
# ---------------------------------------------------------------------------
def atualizar_busca(contato: Contato) -> None:
    partes = [
        contato.nome, contato.cargo,
        contato.empresa.nome if contato.empresa else None,
        contato.email, contato.secretaria_nome, contato.secretaria_email,
        contato.celular, contato.telefone_comercial,
    ]
    contato.busca = normalizar(" | ".join(p for p in partes if p))
    contato.letra = letra_indice(contato.nome)


def _aplicar(contato: Contato, valores: dict, usuario) -> None:
    for chave, valor in valores.items():
        if chave == "empresa":
            contato.empresa = obter_ou_criar_empresa(valor, usuario)[0]
        elif chave == "grupos":
            contato.grupos = Grupo.query.filter(Grupo.id.in_(valor)).all() if valor else []
        elif chave in c.CAMPOS_TEXTO:
            setattr(contato, chave, valor)
    atualizar_busca(contato)


def _registrar(contato, acao, origem, usuario, mudancas, solicitacao=None) -> Historico:
    registro = Historico(
        contato=contato,
        contato_nome=(contato.nome_exibicao if contato else None),
        acao=acao,
        origem=origem,
        usuario=usuario,
        solicitacao=solicitacao,
        mudancas=mudancas,
        criado_em=agora(),
    )
    db.session.add(registro)
    return registro


def _mudanca_foto(contato: Contato, nova: str | None, remover: bool) -> dict:
    """Troca ou remove a foto e devolve a linha do historico."""
    if nova:
        antiga = contato.foto
        contato.foto = nova
        fotos.apagar(antiga)
        return {"foto": ["foto anterior" if antiga else "", "nova foto"]}
    if remover and contato.foto:
        fotos.apagar(contato.foto)
        contato.foto = None
        return {"foto": ["foto anterior", "(foto removida)"]}
    return {}


def _historico_de(mudancas: dict) -> dict:
    return {k: [m["de"], m["para"]] for k, m in mudancas.items()}


def criar_contato(valores, usuario, foto=None, origem=c.ORIGEM_DIRETA, solicitacao=None) -> Contato:
    contato = Contato(criado_por=usuario, criado_em=agora())
    db.session.add(contato)
    _aplicar(contato, valores, usuario)
    mudancas = _historico_de(diferencas(valores_do_contato(None, True), valores, ocultar_restritos=True))
    mudancas.update(_mudanca_foto(contato, foto, False))
    db.session.flush()
    _registrar(contato, c.ACAO_INCLUSAO, origem, usuario, mudancas, solicitacao)
    return contato


def editar_contato(contato, valores, usuario, foto=None, remover_foto=False,
                   origem=c.ORIGEM_DIRETA, solicitacao=None) -> dict:
    """Aplica so o que mudou. Devolve as mudancas (vazio = nada mudou)."""
    atual = valores_do_contato(contato, incluir_restritos=True)
    mudou = diferencas(atual, valores)
    _aplicar(contato, {k: valores[k] for k in mudou}, usuario)

    mudancas = _historico_de(diferencas(atual, valores, ocultar_restritos=True))
    mudancas.update(_mudanca_foto(contato, foto, remover_foto))
    if not mudancas:
        return {}

    contato.atualizado_em = agora()
    contato.atualizado_por = usuario
    _registrar(contato, c.ACAO_ALTERACAO, origem, usuario, mudancas, solicitacao)
    return mudancas


def excluir_contato(contato, usuario, origem=c.ORIGEM_DIRETA, solicitacao=None) -> None:
    contato.excluido_em = agora()
    contato.excluido_por_id = usuario.id
    _registrar(contato, c.ACAO_EXCLUSAO, origem, usuario, {}, solicitacao)
    # Pedidos em aberto sobre uma ficha que deixou de existir nao fazem sentido.
    for pendente in contato.solicitacoes.filter_by(status=c.STATUS_PENDENTE):
        if solicitacao is not None and pendente.id == solicitacao.id:
            continue
        pendente.status = c.STATUS_CANCELADA
        pendente.decidido_em = agora()
        pendente.decidido_por = usuario
        pendente.motivo_decisao = "Cancelada automaticamente: o contato foi excluído."
        fotos.apagar(pendente.foto_proposta)


# ---------------------------------------------------------------------------
# Pendencias
# ---------------------------------------------------------------------------
def ids_com_pendencia(ids=None) -> set[int]:
    consulta = db.session.query(Solicitacao.contato_id).filter(
        Solicitacao.status == c.STATUS_PENDENTE,
        Solicitacao.tipo.in_((c.TIPO_ALTERACAO, c.TIPO_EXCLUSAO)),
        Solicitacao.contato_id.isnot(None),
    )
    if ids is not None:
        ids = list(ids)
        if not ids:
            return set()
        consulta = consulta.filter(Solicitacao.contato_id.in_(ids))
    return {linha[0] for linha in consulta.distinct()}


def contar_pendentes() -> int:
    return Solicitacao.query.filter_by(status=c.STATUS_PENDENTE).count()


# ---------------------------------------------------------------------------
# Solicitacoes (usuario comum)
# ---------------------------------------------------------------------------
def solicitar_alteracao(contato, valores, usuario, comentario, foto=None, remover_foto=False):
    atual = valores_do_contato(contato, incluir_restritos=False)
    mudou = diferencas(atual, valores)
    if foto:
        mudou["foto"] = {"de": "foto atual" if contato.foto else "", "para": "nova foto"}
    elif remover_foto and contato.foto:
        mudou["foto"] = {"de": "foto atual", "para": "(remover foto)"}
    if not mudou:
        return None
    solicitacao = Solicitacao(
        tipo=c.TIPO_ALTERACAO,
        contato=contato,
        contato_nome=contato.nome_exibicao,
        dados={k: valores[k] for k in mudou if k != "foto"},
        mudancas=mudou,
        foto_proposta=foto,
        remover_foto=bool(remover_foto and not foto and contato.foto),
        comentario=limpar(comentario),
        solicitante=usuario,
        criado_em=agora(),
    )
    db.session.add(solicitacao)
    return solicitacao


def solicitar_inclusao(valores, usuario, comentario, foto=None):
    mudou = diferencas(valores_do_contato(None, incluir_restritos=False), valores)
    if foto:
        mudou["foto"] = {"de": "", "para": "nova foto"}
    if not mudou:
        return None
    solicitacao = Solicitacao(
        tipo=c.TIPO_INCLUSAO,
        contato_nome=valores.get("nome") or "(contato sem nome)",
        dados={k: valores[k] for k in mudou if k != "foto"},
        mudancas=mudou,
        foto_proposta=foto,
        comentario=limpar(comentario),
        solicitante=usuario,
        criado_em=agora(),
    )
    db.session.add(solicitacao)
    return solicitacao


def solicitar_exclusao(contato, usuario, comentario):
    solicitacao = Solicitacao(
        tipo=c.TIPO_EXCLUSAO,
        contato=contato,
        contato_nome=contato.nome_exibicao,
        dados={},
        mudancas={},
        comentario=limpar(comentario),
        solicitante=usuario,
        criado_em=agora(),
    )
    db.session.add(solicitacao)
    return solicitacao


# ---------------------------------------------------------------------------
# Decisao (gestor de dados / administrador)
# ---------------------------------------------------------------------------
def _decidir(solicitacao, status, gestor, motivo):
    if not solicitacao.pendente:
        raise ErroSolicitacao("Esta solicitação já foi decidida.")
    solicitacao.status = status
    solicitacao.decidido_por = gestor
    solicitacao.decidido_em = agora()
    solicitacao.motivo_decisao = limpar(motivo)


def aprovar(solicitacao, gestor, motivo=None) -> None:
    if not solicitacao.pendente:
        raise ErroSolicitacao("Esta solicitação já foi decidida.")

    if solicitacao.tipo == c.TIPO_INCLUSAO:
        novo = criar_contato(
            solicitacao.dados, gestor, foto=solicitacao.foto_proposta,
            origem=c.ORIGEM_SOLICITACAO, solicitacao=solicitacao,
        )
        solicitacao.contato = novo
    else:
        contato = solicitacao.contato
        if contato is None or contato.excluido_em is not None:
            raise ErroSolicitacao("O contato desta solicitação foi excluído.")
        if solicitacao.tipo == c.TIPO_ALTERACAO:
            editar_contato(
                contato, solicitacao.dados, gestor,
                foto=solicitacao.foto_proposta, remover_foto=solicitacao.remover_foto,
                origem=c.ORIGEM_SOLICITACAO, solicitacao=solicitacao,
            )
        elif solicitacao.tipo == c.TIPO_EXCLUSAO:
            excluir_contato(contato, gestor, origem=c.ORIGEM_SOLICITACAO, solicitacao=solicitacao)

    _decidir(solicitacao, c.STATUS_APROVADA, gestor, motivo)


def recusar(solicitacao, gestor, motivo=None) -> None:
    _decidir(solicitacao, c.STATUS_RECUSADA, gestor, motivo)
    fotos.apagar(solicitacao.foto_proposta)


def cancelar(solicitacao, usuario) -> None:
    if solicitacao.solicitante_id != usuario.id:
        raise ErroSolicitacao("Só quem fez a solicitação pode cancelá-la.")
    _decidir(solicitacao, c.STATUS_CANCELADA, usuario, "Cancelada pelo solicitante.")
    fotos.apagar(solicitacao.foto_proposta)


def situacao_atual(solicitacao) -> dict:
    """Valor de hoje de cada campo pedido, para o gestor ver se algo mudou
    entre o pedido e a decisao."""
    contato = solicitacao.contato
    if solicitacao.tipo != c.TIPO_ALTERACAO or contato is None:
        return {}
    atual = valores_do_contato(contato, incluir_restritos=False)
    return {k: texto(k, atual.get(k)) for k in solicitacao.dados}
