# -*- coding: utf-8 -*-
"""Entrada pela conta Microsoft (Entra ID).

O sistema fala com o Entra pelo fluxo de codigo de autorizacao: mandamos a
pessoa para a tela da Microsoft, ela volta com um ``code`` de uso unico e o
servidor troca esse codigo por um token. A senha nunca passa por aqui.

Quem a pessoa e sai do ``id_token`` que a propria MSAL valida (assinatura,
emissor, publico e validade), e nao de uma chamada extra ao Microsoft Graph:
o token ja traz ``oid``, nome e e-mail, entao a consulta so acrescentaria uma
ida a rede e um ponto a mais para falhar no meio do login.
"""

from dataclasses import dataclass

from flask import current_app

#: Reivindicacoes do id_token que costumam trazer o e-mail, em ordem de
#: preferencia. Em conta corporativa o ``preferred_username`` e o UPN e vem
#: sempre; ``email`` so aparece se o administrador do tenant o incluir.
CAMPOS_EMAIL = ("preferred_username", "email", "upn")


class ErroSSO(Exception):
    """Falha no dialogo com a Microsoft, com texto pronto para a tela."""


@dataclass(frozen=True)
class IdentidadeMicrosoft:
    """Quem a Microsoft disse que e a pessoa que acabou de entrar."""

    oid: str
    email: str
    nome: str


def configurado() -> bool:
    """Diz se ha credenciais suficientes para conversar com o Entra."""
    config = current_app.config
    return bool(
        config.get("SSO_ENABLED")
        and config.get("AZURE_TENANT_ID")
        and config.get("AZURE_CLIENT_ID")
        and config.get("AZURE_CLIENT_SECRET")
    )


def _aplicacao():
    import msal

    config = current_app.config
    return msal.ConfidentialClientApplication(
        client_id=config["AZURE_CLIENT_ID"],
        client_credential=config["AZURE_CLIENT_SECRET"],
        authority=f"https://login.microsoftonline.com/{config['AZURE_TENANT_ID']}",
    )


def url_de_autorizacao(estado: str) -> str:
    """Monta o endereco da tela de login da Microsoft.

    ``prompt="select_account"`` existe porque muita gente na Fin tem a conta
    pessoal e a corporativa no mesmo navegador: sem isto o Entra reaproveita
    silenciosamente a ultima usada e a pessoa entra com a conta errada.
    """
    return _aplicacao().get_authorization_request_url(
        scopes=current_app.config["AZURE_SCOPES"],
        redirect_uri=current_app.config["AZURE_REDIRECT_URI"],
        state=estado,
        prompt="select_account",
    )


def identidade_do_codigo(codigo: str) -> IdentidadeMicrosoft:
    """Troca o ``code`` recebido no retorno pelos dados da pessoa.

    Levanta ``ErroSSO`` com um texto exibivel quando a Microsoft recusa a
    troca ou quando o token volta sem os dados de que precisamos.
    """
    resultado = _aplicacao().acquire_token_by_authorization_code(
        codigo,
        scopes=current_app.config["AZURE_SCOPES"],
        redirect_uri=current_app.config["AZURE_REDIRECT_URI"],
    )

    if "error" in resultado:
        detalhe = resultado.get("error_description") or resultado["error"]
        current_app.logger.warning("SSO Microsoft recusou o codigo: %s", detalhe)
        raise ErroSSO(
            "A Microsoft não confirmou esta entrada. Tente novamente; se "
            "insistir, procure a TI."
        )

    dados = resultado.get("id_token_claims") or {}
    oid = (dados.get("oid") or "").strip()
    nome = (dados.get("name") or "").strip()
    email = ""
    for campo in CAMPOS_EMAIL:
        email = (dados.get(campo) or "").strip().lower()
        if email:
            break

    if not oid or not email:
        current_app.logger.warning(
            "SSO Microsoft: id_token sem oid ou e-mail (campos: %s)",
            ", ".join(sorted(dados)),
        )
        raise ErroSSO(
            "A conta Microsoft não informou e-mail. Procure a TI para revisar "
            "o cadastro dela."
        )

    return IdentidadeMicrosoft(oid=oid, email=email, nome=nome or email)
