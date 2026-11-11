"""Exportacao de todos os contatos para planilha do Excel (.xlsx).

As colunas seguem constants.CAMPOS, entao um campo novo na ficha entra na
planilha sem mexer aqui. Dados restritos so entram quando pedidos.
"""

import io

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from app import constants as c
from app.models import Contato

KLEIN = "0028E6"
LARGURAS = {"textarea": 45, "email": 32, "telefone": 18, "empresa": 34, "grupos": 30}


def _valor(contato, campo) -> str:
    if campo.tipo == "empresa":
        return contato.empresa.nome if contato.empresa else ""
    if campo.tipo == "grupos":
        return ", ".join(g.nome for g in sorted(contato.grupos, key=lambda g: g.nome.lower()))
    return getattr(contato, campo.chave) or ""


def planilha(incluir_restritos: bool, pendentes: set[int]) -> tuple[bytes, int]:
    """Devolve (conteudo do .xlsx, numero de fichas)."""
    campos = [cp for cp in c.CAMPOS if incluir_restritos or not cp.restrito]
    contatos = Contato.ativos().order_by(Contato.busca, Contato.id).all()

    wb = Workbook()
    ws = wb.active
    ws.title = "Contatos"

    cabecalho = ["Ficha nº"] + [c.ROTULOS[cp.chave] for cp in campos] + [
        "Alteração pendente", "Cadastrada em", "Última alteração em",
    ]
    ws.append(cabecalho)

    fmt = "%d/%m/%Y %H:%M"
    for ct in contatos:
        linha = [ct.numero] + [_valor(ct, cp) for cp in campos] + [
            "Sim" if ct.id in pendentes else "Não",
            ct.criado_em.strftime(fmt) if ct.criado_em else "",
            ct.atualizado_em.strftime(fmt) if ct.atualizado_em else "",
        ]
        ws.append(linha)

    # Tudo como texto: telefone nao vira numero e nada que comece com "="
    # e interpretado como formula pelo Excel.
    for linha in ws.iter_rows(min_row=2):
        for celula in linha:
            celula.data_type = "s"
            celula.alignment = Alignment(vertical="top", wrap_text=True)

    borda = Border(bottom=Side(style="medium", color="0000A0"))
    for celula in ws[1]:
        celula.font = Font(bold=True, color="FFFFFF")
        celula.fill = PatternFill("solid", fgColor=KLEIN)
        celula.alignment = Alignment(vertical="center", wrap_text=True)
        celula.border = borda
    ws.row_dimensions[1].height = 32

    larguras = [10] + [LARGURAS.get(cp.tipo, 26) for cp in campos] + [12, 17, 17]
    larguras[1] = 34  # nome
    for i, largura in enumerate(larguras, start=1):
        ws.column_dimensions[get_column_letter(i)].width = largura

    ws.freeze_panes = "C2"
    ws.auto_filter.ref = ws.dimensions

    saida = io.BytesIO()
    wb.save(saida)
    return saida.getvalue(), len(contatos)
