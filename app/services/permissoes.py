"""Controle de acesso por perfil.

- Administrador: tudo, inclusive a area de usuarios.
- Gestor de dados: insere, edita, exclui, aprova, ve dados restritos e
  relatorios.
- Usuario: consulta e solicita alteracoes (sem ver dados restritos).
"""

from functools import wraps

from flask import abort
from flask_login import current_user

from app import constants as c


def perfil_requerido(*perfis: str):
    def decorador(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(401)
            if current_user.perfil not in perfis:
                abort(403)
            return func(*args, **kwargs)

        return wrapper

    return decorador


def admin_requerido(func):
    return perfil_requerido(c.PERFIL_ADMIN)(func)


def gestao_requerida(func):
    return perfil_requerido(*c.PERFIS_GESTAO)(func)
