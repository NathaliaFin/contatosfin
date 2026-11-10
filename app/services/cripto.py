"""Cifragem dos dados restritos (CPF, RG, CNPJ...) antes de irem ao banco.

Usa Fernet (AES-128 em modo CBC + HMAC-SHA256, da biblioteca cryptography).
Quem le o banco direto -- um backup vazado, por exemplo -- ve apenas texto
cifrado. A chave fica so no .env (CHAVE_DADOS_RESTRITOS).
"""

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken
from flask import current_app
from sqlalchemy.types import Text, TypeDecorator

_cache: dict[str, Fernet] = {}


class ChaveAusente(RuntimeError):
    pass


def _fernet() -> Fernet:
    chave = current_app.config.get("CHAVE_DADOS_RESTRITOS") or ""
    if not chave:
        if not current_app.debug:
            raise ChaveAusente(
                "CHAVE_DADOS_RESTRITOS nao esta definida no .env. "
                "Sem ela os dados restritos nao podem ser gravados nem lidos."
            )
        # Apenas para a copia de teste local: chave derivada e previsivel.
        chave = base64.urlsafe_b64encode(
            hashlib.sha256(b"contatos-fin-desenvolvimento").digest()
        ).decode()
    if chave not in _cache:
        _cache[chave] = Fernet(chave.encode())
    return _cache[chave]


def cifrar(texto: str | None) -> str | None:
    if texto in (None, ""):
        return None
    return _fernet().encrypt(texto.encode("utf-8")).decode("ascii")


def decifrar(cifrado: str | None) -> str | None:
    if not cifrado:
        return None
    try:
        return _fernet().decrypt(cifrado.encode("ascii")).decode("utf-8")
    except InvalidToken:
        current_app.logger.error(
            "Dado restrito ilegivel: a CHAVE_DADOS_RESTRITOS do .env nao e a "
            "mesma usada quando o dado foi gravado."
        )
        return "(ilegível — chave de criptografia diferente)"


class TextoCifrado(TypeDecorator):
    """Coluna TEXT cujo conteudo e cifrado ao gravar e decifrado ao ler."""

    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        return cifrar(value)

    def process_result_value(self, value, dialect):
        return decifrar(value)
