"""Compartilhamento de uma ficha para fora do sistema (WhatsApp, cartao .vcf).

So saem os dados de contato profissional. Dados restritos, secretaria e
observacoes internas nunca entram, qualquer que seja o perfil de quem compartilha.
"""

import base64
from urllib.parse import quote

from app.services import fotos
from app.services.validacao import digitos


def _numero_internacional(telefone: str | None) -> str:
    """'(61) 99999-0000' -> '5561999990000'. Vazio se nao parecer um numero BR."""
    d = digitos(telefone or "")
    if len(d) in (10, 11):
        return "55" + d
    if len(d) in (12, 13) and d.startswith("55"):
        return d
    return ""


def texto_whatsapp(contato) -> str:
    linhas = [f"*{contato.nome_exibicao}*"]
    funcao = " · ".join(x for x in (contato.cargo, contato.empresa.nome if contato.empresa else None) if x)
    if funcao:
        linhas.append(funcao)
    linhas.append("")
    for rotulo, valor in (
        ("Celular", contato.celular),
        ("Telefone", contato.telefone_comercial),
        ("E-mail", contato.email),
        ("Endereço", contato.endereco_comercial),
    ):
        if valor:
            linhas.append(f"{rotulo}: {' '.join(valor.split())}")
    return "\n".join(linhas).strip()


def link_compartilhar(contato) -> str:
    """Abre o WhatsApp (aplicativo ou Web) com a mensagem pronta; a pessoa escolhe o destino."""
    return "https://api.whatsapp.com/send?text=" + quote(texto_whatsapp(contato))


def link_aplicativo(contato) -> str:
    """Abre direto o aplicativo instalado no computador, sem passar pelo site."""
    return "whatsapp://send?text=" + quote(texto_whatsapp(contato))


def link_conversa(telefone: str | None) -> str:
    """Conversa direta com o numero; vazio se o numero nao servir."""
    numero = _numero_internacional(telefone)
    return f"https://wa.me/{numero}" if numero else ""


def _esc(valor: str) -> str:
    return (
        (valor or "").replace("\\", "\\\\").replace("\n", "\\n").replace(",", "\\,").replace(";", "\\;")
    )


def _dobrar(linha: str) -> str:
    """Linhas de vCard tem no maximo 75 caracteres; as seguintes comecam com espaco."""
    partes = [linha[:75]]
    resto = linha[75:]
    while resto:
        partes.append(" " + resto[:74])
        resto = resto[74:]
    return "\r\n".join(partes)


def vcard(contato) -> str:
    nome = contato.nome or ""
    pedacos = nome.split()
    sobrenome = pedacos[-1] if len(pedacos) > 1 else ""
    primeiros = " ".join(pedacos[:-1]) if len(pedacos) > 1 else nome

    linhas = ["BEGIN:VCARD", "VERSION:3.0", f"N:{_esc(sobrenome)};{_esc(primeiros)};;;", f"FN:{_esc(contato.nome_exibicao)}"]
    if contato.empresa:
        linhas.append(f"ORG:{_esc(contato.empresa.nome)}")
    if contato.cargo:
        linhas.append(f"TITLE:{_esc(contato.cargo)}")
    for tipo, tel in (("CELL", contato.celular), ("WORK", contato.telefone_comercial)):
        if tel:
            numero = _numero_internacional(tel)
            linhas.append(f"TEL;TYPE={tipo}:{'+' + numero if numero else tel}")
    if contato.email:
        linhas.append(f"EMAIL;TYPE=WORK:{contato.email}")
    if contato.endereco_comercial:
        linhas.append(f"ADR;TYPE=WORK:;;{_esc(' '.join(contato.endereco_comercial.split()))};;;;")
    if contato.foto and fotos.caminho(contato.foto).exists():
        dados = base64.b64encode(fotos.caminho(contato.foto).read_bytes()).decode()
        linhas.append(f"PHOTO;ENCODING=b;TYPE=JPEG:{dados}")
    linhas.append("END:VCARD")
    return "\r\n".join(_dobrar(l) for l in linhas) + "\r\n"


def nome_arquivo(contato) -> str:
    from werkzeug.utils import secure_filename

    from app.services.texto import normalizar

    base = secure_filename("-".join(normalizar(contato.nome or "").split())) or "contato"
    return f"{base}.vcf"
