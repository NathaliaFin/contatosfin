"""Configuracao da aplicacao, carregada a partir das variaveis de ambiente."""

import os
from pathlib import Path
from urllib.parse import quote_plus

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")


def _bool(nome: str, padrao: bool = False) -> bool:
    valor = os.getenv(nome)
    if valor is None:
        return padrao
    return valor.strip().lower() in {"1", "true", "yes", "on", "sim"}


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-nao-use-em-producao")

    # --- Banco de dados ---------------------------------------------------
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_PORT = os.getenv("DB_PORT", "3306")
    DB_DATABASE = os.getenv("DB_DATABASE", "contatosfin")
    DB_USERNAME = os.getenv("DB_USERNAME", "root")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "")
    DB_SSL = _bool("DB_SSL", True)
    DB_SSL_CA = os.getenv("DB_SSL_CA", "").strip()

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 280,
    }

    #: Chave que cifra os "dados restritos" (CPF, RG, CNPJ...) no banco.
    #: NUNCA troque depois que houver dados: o que foi gravado com a chave
    #: antiga fica ilegivel. Guarde uma copia em local seguro.
    CHAVE_DADOS_RESTRITOS = os.getenv("CHAVE_DADOS_RESTRITOS", "").strip()

    # --- Uploads (fotos) --------------------------------------------------
    UPLOAD_FOLDER = str(BASE_DIR / "instance" / "uploads")
    FOTO_MAX_MB = int(os.getenv("FOTO_MAX_MB", "5"))
    MAX_CONTENT_LENGTH = (int(os.getenv("FOTO_MAX_MB", "5")) + 2) * 1024 * 1024

    # --- Sessao -----------------------------------------------------------
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    REMEMBER_COOKIE_DURATION = 60 * 60 * 24 * 7  # 7 dias

    # --- Endereco publico (links nos e-mails) ----------------------------
    APP_URL = os.getenv("APP_URL", "http://127.0.0.1:5000").rstrip("/")

    # --- SSO Microsoft (Entra ID) ----------------------------------------
    SSO_ENABLED = _bool("SSO_ENABLED", False)
    AZURE_CLIENT_ID = os.getenv("AZURE_CLIENT_ID", "")
    AZURE_CLIENT_SECRET = os.getenv("AZURE_CLIENT_SECRET", "")
    AZURE_TENANT_ID = os.getenv("AZURE_TENANT_ID", "")
    AZURE_REDIRECT_URI = os.getenv(
        "AZURE_REDIRECT_URI", "http://localhost:5000/auth/sso/callback"
    )
    AZURE_SCOPES = ["User.Read"]
    #: Contas Microsoft deste dominio entram sozinhas, com perfil "usuario".
    SSO_DOMINIO = os.getenv("SSO_DOMINIO", "fin.org.br").strip().lower().lstrip("@")

    # --- E-mail (SMTP Microsoft 365, como no sistema de reunioes) --------
    SMTP_HOST = os.getenv("SMTP_HOST", "smtp.office365.com")
    SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USERNAME = os.getenv("SMTP_USERNAME", "")
    SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
    SMTP_FROM = os.getenv("SMTP_FROM", "") or os.getenv("SMTP_USERNAME", "")
    SMTP_FROM_NAME = os.getenv("SMTP_FROM_NAME", "Contatos Fin")

    # --- Seed -------------------------------------------------------------
    ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@fin.org.br").strip().lower()
    ADMIN_NOME = os.getenv("ADMIN_NOME", "Administrador")
    ADMIN_SENHA = os.getenv("ADMIN_SENHA", "")

    #: Sobrescreve a URI completa do banco. Usado pela copia de teste local
    #: (sqlite:///instance/preview.db), sem acesso ao MySQL do Azure.
    DATABASE_URL = os.getenv("DATABASE_URL", "").strip()

    @classmethod
    def database_uri(cls) -> str:
        if cls.DATABASE_URL:
            return cls.DATABASE_URL
        senha = quote_plus(cls.DB_PASSWORD)
        usuario = quote_plus(cls.DB_USERNAME)
        return (
            f"mysql+pymysql://{usuario}:{senha}@{cls.DB_HOST}:{cls.DB_PORT}/"
            f"{cls.DB_DATABASE}?charset=utf8mb4"
        )

    @classmethod
    def connect_args(cls) -> dict:
        """Argumentos de conexao do PyMySQL (o Azure exige TLS)."""
        if cls.DATABASE_URL and not cls.DATABASE_URL.startswith("mysql"):
            return {}
        if not cls.DB_SSL:
            return {}
        if cls.DB_SSL_CA:
            return {"ssl": {"ca": cls.DB_SSL_CA}}
        return {"ssl": {"ssl_mode": "REQUIRED"}}


class DevelopmentConfig(Config):
    DEBUG = True
    SESSION_COOKIE_SECURE = False
    ATRAS_DE_PROXY = False


class ProductionConfig(Config):
    DEBUG = False
    SESSION_COOKIE_SECURE = True
    REMEMBER_COOKIE_SECURE = True

    #: O HTTPS da Fin e encerrado no proxy da infraestrutura, que repassa a
    #: requisicao em HTTP simples para o nginx do SRVAPP01.
    ATRAS_DE_PROXY = _bool("ATRAS_DE_PROXY", True)


def get_config():
    ambiente = os.getenv("FLASK_ENV", "development").strip().lower()
    return ProductionConfig if ambiente == "production" else DevelopmentConfig
