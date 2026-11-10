"""Carga inicial do banco: listas de trabalho e o administrador."""

from flask import current_app

from app import constants as c
from app.extensions import db
from app.models import Grupo, Usuario


def semear_tudo() -> dict:
    resumo = {"grupos": 0, "admin": ""}

    if Grupo.query.count() == 0:
        for ordem, nome in enumerate(c.GRUPOS_INICIAIS, start=1):
            db.session.add(Grupo(nome=nome, ordem=ordem))
            resumo["grupos"] += 1

    email = current_app.config["ADMIN_EMAIL"]
    admin = Usuario.query.filter_by(email=email).first()
    if admin is None:
        admin = Usuario(nome=current_app.config["ADMIN_NOME"], email=email, perfil=c.PERFIL_ADMIN)
        admin.definir_senha(current_app.config["ADMIN_SENHA"] or None)
        db.session.add(admin)
        resumo["admin"] = f"{email} (criado)"
    else:
        if admin.perfil != c.PERFIL_ADMIN:
            admin.perfil = c.PERFIL_ADMIN
        resumo["admin"] = f"{email} (já existia)"

    db.session.commit()
    return resumo
