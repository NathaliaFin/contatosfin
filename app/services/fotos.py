"""Fotos dos contatos.

Toda foto enviada e convertida para JPEG 3x4 (450 x 600 px), cortada no
centro. Isso padroniza o "retrato grampeado" da ficha, remove metadados da
camera (localizacao GPS, por exemplo) e impede que um arquivo disfarcado de
imagem seja guardado no servidor.
"""

import uuid
from pathlib import Path

from flask import current_app
from PIL import Image, ImageOps, UnidentifiedImageError

LARGURA, ALTURA = 450, 600
FORMATOS_ACEITOS = {"JPEG", "PNG", "WEBP"}


class ErroFoto(ValueError):
    """Problema na foto enviada, com texto pronto para a tela."""


def pasta() -> Path:
    destino = Path(current_app.config["UPLOAD_FOLDER"]) / "fotos"
    destino.mkdir(parents=True, exist_ok=True)
    return destino


def caminho(nome: str) -> Path:
    # O nome e sempre gerado por nos (uuid + .jpg); o Path().name impede
    # que algo como "../../" escape da pasta.
    return pasta() / Path(nome).name


def salvar_upload(arquivo) -> str | None:
    """Recebe o arquivo do formulario e devolve o nome gravado (ou None)."""
    if arquivo is None or not getattr(arquivo, "filename", ""):
        return None

    limite = current_app.config["FOTO_MAX_MB"] * 1024 * 1024
    arquivo.stream.seek(0, 2)
    tamanho = arquivo.stream.tell()
    arquivo.stream.seek(0)
    if tamanho > limite:
        raise ErroFoto(f"A foto passa de {current_app.config['FOTO_MAX_MB']} MB. Envie uma imagem menor.")

    try:
        imagem = Image.open(arquivo.stream)
        formato = imagem.format
        imagem.load()
    except (UnidentifiedImageError, OSError):
        raise ErroFoto("O arquivo enviado não é uma imagem válida. Use JPG, PNG ou WEBP.")

    if formato not in FORMATOS_ACEITOS:
        raise ErroFoto("Formato de imagem não aceito. Use JPG, PNG ou WEBP.")

    imagem = ImageOps.exif_transpose(imagem)
    if imagem.mode != "RGB":
        fundo = Image.new("RGB", imagem.size, (255, 255, 255))
        if imagem.mode in ("RGBA", "LA", "P"):
            imagem = imagem.convert("RGBA")
            fundo.paste(imagem, mask=imagem.split()[-1])
        else:
            fundo.paste(imagem.convert("RGB"))
        imagem = fundo

    imagem = ImageOps.fit(imagem, (LARGURA, ALTURA), Image.LANCZOS, centering=(0.5, 0.35))

    nome = f"{uuid.uuid4().hex}.jpg"
    imagem.save(caminho(nome), "JPEG", quality=85, optimize=True)
    return nome


def apagar(nome: str | None) -> None:
    if not nome:
        return
    try:
        caminho(nome).unlink(missing_ok=True)
    except OSError:
        current_app.logger.warning("Nao foi possivel apagar a foto %s", nome)
