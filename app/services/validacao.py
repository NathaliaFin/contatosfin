"""Conferencia e formatacao de e-mail, telefone, CPF e CNPJ.

Nenhum campo e obrigatorio: as regras so valem quando o campo e preenchido.
"""

import re

_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]{2,}$")
_NAO_DIGITO = re.compile(r"\D")


def digitos(texto: str) -> str:
    return _NAO_DIGITO.sub("", texto or "")


def email_valido(texto: str) -> bool:
    return bool(_EMAIL.match(texto))


def formatar_telefone(texto: str) -> str:
    """(11) 99971-9434 ou (11) 3333-4444. Fora desses formatos (ramal,
    numero internacional) fica como foi digitado."""
    d = digitos(texto)
    if len(d) in (12, 13) and d.startswith("55"):
        d = d[2:]
    if len(d) == 11:
        return f"({d[:2]}) {d[2:7]}-{d[7:]}"
    if len(d) == 10:
        return f"({d[:2]}) {d[2:6]}-{d[6:]}"
    return texto.strip()


def telefone_valido(texto: str) -> bool:
    return bool(re.fullmatch(r"[\d\s()+\-./]+(\s*(ramal|r\.)\s*\d+)?", texto.strip(), re.I)) and len(digitos(texto)) >= 8


def _dv_cpf(d: str) -> bool:
    if len(d) != 11 or d == d[0] * 11:
        return False
    for tamanho in (9, 10):
        soma = sum(int(d[i]) * (tamanho + 1 - i) for i in range(tamanho))
        dv = (soma * 10) % 11 % 10
        if dv != int(d[tamanho]):
            return False
    return True


def _dv_cnpj(d: str) -> bool:
    if len(d) != 14 or d == d[0] * 14:
        return False
    pesos1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    pesos2 = [6] + pesos1
    for pesos, pos in ((pesos1, 12), (pesos2, 13)):
        soma = sum(int(d[i]) * pesos[i] for i in range(pos))
        resto = soma % 11
        dv = 0 if resto < 2 else 11 - resto
        if dv != int(d[pos]):
            return False
    return True


def cpf_valido(texto: str) -> bool:
    return _dv_cpf(digitos(texto))


def cnpj_valido(texto: str) -> bool:
    return _dv_cnpj(digitos(texto))


def formatar_cpf(texto: str) -> str:
    d = digitos(texto)
    return f"{d[:3]}.{d[3:6]}.{d[6:9]}-{d[9:]}" if len(d) == 11 else texto


def formatar_cnpj(texto: str) -> str:
    d = digitos(texto)
    return f"{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:]}" if len(d) == 14 else texto
