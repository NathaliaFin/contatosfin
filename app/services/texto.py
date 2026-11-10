"""Normalizacao de texto para busca e comparacao.

"ABEL", "abel", "Abel" e "abeL" viram "abel"; "Associação" vira "associacao".
E o que permite achar a empresa ou o contato sem se preocupar com maiusculas
e acentos, e impedir que a mesma empresa seja cadastrada duas vezes.
"""

import re
import unicodedata

_ESPACOS = re.compile(r"\s+")


def normalizar(texto: str | None) -> str:
    if not texto:
        return ""
    sem_acento = "".join(
        ch for ch in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(ch)
    )
    return _ESPACOS.sub(" ", sem_acento).strip().lower()


def limpar(texto: str | None) -> str | None:
    """Tira espacos sobrando; texto vazio vira None."""
    if texto is None:
        return None
    texto = _ESPACOS.sub(" ", texto).strip() if "\n" not in texto else texto.strip()
    return texto or None


def iniciais(nome: str | None) -> str:
    partes = [p for p in (nome or "").split() if p[:1].isalpha()]
    if not partes:
        return "?"
    if len(partes) == 1:
        return partes[0][:2].upper()
    return (partes[0][0] + partes[-1][0]).upper()


def letra_indice(nome: str | None) -> str:
    """Letra do fichario (A-Z) em que o contato fica arquivado."""
    inicial = normalizar(nome)[:1].upper()
    return inicial if "A" <= inicial <= "Z" else "#"
