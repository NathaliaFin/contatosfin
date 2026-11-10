"""Instancias das extensoes Flask, isoladas para evitar importacao circular."""

from flask_login import LoginManager
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect

db = SQLAlchemy()
migrate = Migrate()
csrf = CSRFProtect()
login_manager = LoginManager()

login_manager.login_view = "auth.login"
login_manager.login_message = "Faça login para acessar o sistema."
login_manager.login_message_category = "aviso"

#: "basic" porque o sistema fica atras do proxy da Fin, que nao entrega
#: sempre o mesmo IP de origem (mesma decisao do afin).
login_manager.session_protection = "basic"
