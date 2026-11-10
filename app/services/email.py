"""Envio de e-mail via SMTP do Microsoft 365 - mesma estrategia do sistema
de Registro de Reunioes (reunioes.fin.org.br).

Configuracao no .env:
    SMTP_HOST       smtp.office365.com
    SMTP_PORT       587 (STARTTLS)
    SMTP_USERNAME   caixa do sistema (ex.: contatos@fin.org.br)
    SMTP_PASSWORD   senha da caixa
    SMTP_FROM       geralmente igual ao SMTP_USERNAME
    SMTP_FROM_NAME  nome de exibicao

Com SMTP_PASSWORD vazia nada e enviado: a mensagem e gravada em
instance/emails-nao-enviados.log, para conferencia na copia de teste.
"""

import smtplib
import ssl
from datetime import datetime
from email.message import EmailMessage
from email.utils import formataddr
from pathlib import Path

from flask import current_app, render_template

from app import constants as c
from app.models import Usuario


def configurado() -> bool:
    cfg = current_app.config
    return bool(cfg.get("SMTP_HOST") and cfg.get("SMTP_USERNAME") and cfg.get("SMTP_PASSWORD"))


def _registrar_local(destinatarios, assunto, texto) -> None:
    arquivo = Path(current_app.instance_path) / "emails-nao-enviados.log"
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    with arquivo.open("a", encoding="utf-8") as saida:
        saida.write(
            f"\n===== {datetime.now():%d/%m/%Y %H:%M:%S}\n"
            f"Para: {', '.join(destinatarios)}\nAssunto: {assunto}\n\n{texto}\n"
        )


def enviar(destinatarios, assunto: str, html: str, texto: str) -> bool:
    """Envia a mensagem. Devolve True se o servidor de e-mail aceitou."""
    destinatarios = sorted({d for d in destinatarios if d})
    if not destinatarios:
        current_app.logger.warning("E-mail '%s' sem destinatarios.", assunto)
        return False

    if not configurado():
        current_app.logger.info("SMTP nao configurado; e-mail '%s' gravado no log local.", assunto)
        _registrar_local(destinatarios, assunto, texto)
        return False

    cfg = current_app.config
    msg = EmailMessage()
    msg["Subject"] = assunto
    msg["From"] = formataddr((cfg["SMTP_FROM_NAME"], cfg["SMTP_FROM"]))
    # Destinatarios em copia oculta: um gestor nao recebe o e-mail dos outros.
    msg["To"] = formataddr((cfg["SMTP_FROM_NAME"], cfg["SMTP_FROM"]))
    msg["Bcc"] = ", ".join(destinatarios)
    msg.set_content(texto)
    msg.add_alternative(html, subtype="html")

    try:
        with smtplib.SMTP(cfg["SMTP_HOST"], cfg["SMTP_PORT"], timeout=30) as servidor:
            servidor.ehlo()
            servidor.starttls(context=ssl.create_default_context())
            servidor.ehlo()
            servidor.login(cfg["SMTP_USERNAME"], cfg["SMTP_PASSWORD"])
            servidor.send_message(msg)
        return True
    except Exception:  # noqa: BLE001 - a solicitacao ja foi gravada; so registramos
        current_app.logger.exception("Falha ao enviar o e-mail '%s'", assunto)
        return False


def _link(caminho: str) -> str:
    return f"{current_app.config['APP_URL']}{caminho}"


def _gestores() -> list[str]:
    gestores = Usuario.query.filter_by(perfil=c.PERFIL_GESTOR, ativo=True).all()
    if not gestores:
        # Sem gestor cadastrado, o pedido nao pode ficar sem dono.
        gestores = Usuario.query.filter_by(perfil=c.PERFIL_ADMIN, ativo=True).all()
    return [u.email for u in gestores]


def notificar_nova_solicitacao(solicitacao) -> bool:
    link = _link(f"/solicitacoes/{solicitacao.id}")
    contexto = {"s": solicitacao, "link": link, "rotulos": c.ROTULOS}
    assunto = f"[Contatos Fin] {solicitacao.rotulo_tipo}: {solicitacao.contato_nome} — aguardando aprovação"
    return enviar(
        _gestores(),
        assunto,
        render_template("emails/nova_solicitacao.html", **contexto),
        render_template("emails/nova_solicitacao.txt", **contexto),
    )


def notificar_decisao(solicitacao) -> bool:
    link = _link(f"/solicitacoes/{solicitacao.id}")
    contexto = {"s": solicitacao, "link": link, "rotulos": c.ROTULOS}
    assunto = f"[Contatos Fin] Sua solicitação foi {solicitacao.rotulo_status.lower()}: {solicitacao.contato_nome}"
    return enviar(
        [solicitacao.solicitante.email],
        assunto,
        render_template("emails/decisao.html", **contexto),
        render_template("emails/decisao.txt", **contexto),
    )
