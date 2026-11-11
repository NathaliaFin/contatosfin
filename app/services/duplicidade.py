"""Trava contra fichas repetidas.

- E-mail: trava. Nao pode haver duas fichas ativas (nem uma ficha e um pedido
  de inclusao aguardando o gestor) com o mesmo e-mail.
- Nome e celular: so aviso. Homonimos existem; quem cadastra confere a ficha
  parecida e confirma que e outra pessoa.

So se confere o que mudou: uma ficha antiga que ja estivesse repetida continua
podendo ser editada nos outros campos.
"""

import re
from dataclasses import dataclass, field

from sqlalchemy import func

from app import constants as c
from app.models import Contato, Solicitacao
from app.services.texto import letra_indice, normalizar

ROTULOS = {"email": "mesmo e-mail", "nome": "mesmo nome", "celular": "mesmo celular"}


@dataclass
class Repetida:
    """Ficha (ou pedido de inclusao) parecida com a que se quer gravar."""

    contato: Contato | None = None
    solicitacao: Solicitacao | None = None
    motivos: list = field(default_factory=list)

    @property
    def trava(self) -> bool:
        return "email" in self.motivos

    @property
    def nome(self) -> str:
        if self.contato is not None:
            return self.contato.nome_exibicao
        return self.solicitacao.contato_nome or "(contato sem nome)"

    @property
    def rotulo_motivos(self) -> str:
        return ", ".join(ROTULOS[m] for m in self.motivos)


def _digitos(texto: str | None) -> str:
    return re.sub(r"\D", "", texto or "")


def _chave(campo: str, valor) -> str:
    if campo == "email":
        return (valor or "").strip().lower()
    if campo == "nome":
        return normalizar(valor)
    # celular: so os 8 ultimos digitos contam (com ou sem 55, DDD ou o 9 da frente)
    return _digitos(valor)[-8:]


def procurar(valores: dict, ignorar_contato=None, ignorar_solicitacao=None, anteriores=None) -> list[Repetida]:
    """Fichas e pedidos de inclusao pendentes parecidos com ``valores``.

    So os campos presentes em ``valores`` sao conferidos; com ``anteriores``,
    so os que mudaram em relacao a eles. As travas vem primeiro na lista.
    """
    chaves = {}
    for campo in ("email", "nome", "celular"):
        if campo not in valores:
            continue
        chave = _chave(campo, valores.get(campo))
        if not chave or (campo == "celular" and len(chave) < 8):
            continue
        if anteriores is not None and chave == _chave(campo, anteriores.get(campo)):
            continue
        chaves[campo] = chave
    if not chaves:
        return []

    achadas: dict = {}

    def anotar(chave_item, campo, contato=None, solicitacao=None):
        item = achadas.setdefault(chave_item, Repetida(contato=contato, solicitacao=solicitacao))
        if campo not in item.motivos:
            item.motivos.append(campo)

    ignorar_id = ignorar_contato.id if ignorar_contato is not None else None

    def fichas(consulta):
        if ignorar_id is not None:
            consulta = consulta.filter(Contato.id != ignorar_id)
        return consulta.all()

    if "email" in chaves:
        for ct in fichas(Contato.ativos().filter(func.lower(Contato.email) == chaves["email"])):
            anotar(("c", ct.id), "email", contato=ct)
    if "nome" in chaves:
        letra = letra_indice(valores.get("nome"))
        for ct in fichas(Contato.ativos().filter(Contato.letra == letra)):
            if normalizar(ct.nome) == chaves["nome"]:
                anotar(("c", ct.id), "nome", contato=ct)
    if "celular" in chaves:
        fim = chaves["celular"][-4:]
        for ct in fichas(Contato.ativos().filter(Contato.celular.like(f"%{fim}"))):
            if _chave("celular", ct.celular) == chaves["celular"]:
                anotar(("c", ct.id), "celular", contato=ct)

    pedidos = Solicitacao.query.filter_by(status=c.STATUS_PENDENTE, tipo=c.TIPO_INCLUSAO)
    if ignorar_solicitacao is not None and ignorar_solicitacao.id is not None:
        pedidos = pedidos.filter(Solicitacao.id != ignorar_solicitacao.id)
    for pedido in pedidos.order_by(Solicitacao.criado_em).all():
        dados = pedido.dados or {}
        for campo, chave in chaves.items():
            if _chave(campo, dados.get(campo)) == chave:
                anotar(("s", pedido.id), campo, solicitacao=pedido)

    ordem = {"email": 0, "nome": 1, "celular": 2}
    for item in achadas.values():
        item.motivos.sort(key=ordem.get)
    return sorted(achadas.values(), key=lambda r: (not r.trava, r.solicitacao is not None, r.nome))


def trava(repetidas: list[Repetida]) -> bool:
    return any(r.trava for r in repetidas)


def erro_email(repetidas: list[Repetida]) -> str | None:
    """Texto do erro no campo E-mail, quando ha trava."""
    travas = [r for r in repetidas if r.trava]
    if not travas:
        return None
    if any(r.contato is not None for r in travas):
        return "Já existe uma ficha com este e-mail."
    return "Já existe um pedido de inclusão com este e-mail aguardando o gestor de dados."


def descrever(r: Repetida) -> str:
    """Texto curto para mensagens (ex.: na aprovacao)."""
    if r.contato is not None:
        return f"{r.nome} (ficha nº {r.contato.numero})"
    return f"{r.nome} (pedido de inclusão nº {r.solicitacao.id:04d})"
