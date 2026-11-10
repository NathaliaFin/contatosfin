"""Modelos do banco de dados."""

from datetime import datetime

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from app import constants as c
from app.extensions import db
from app.services.cripto import TextoCifrado
from app.services.texto import normalizar


def agora() -> datetime:
    return datetime.now().replace(microsecond=0)


# ---------------------------------------------------------------------------
# Usuarios
# ---------------------------------------------------------------------------
class Usuario(UserMixin, db.Model):
    __tablename__ = "usuarios"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(254), nullable=False, unique=True, index=True)
    perfil = db.Column(db.String(20), nullable=False, default=c.PERFIL_USUARIO)
    ativo = db.Column(db.Boolean, nullable=False, default=True)
    senha_hash = db.Column(db.String(255))
    azure_oid = db.Column(db.String(64), unique=True)
    criado_em = db.Column(db.DateTime, nullable=False, default=agora)
    ultimo_acesso = db.Column(db.DateTime)

    def definir_senha(self, senha: str | None) -> None:
        self.senha_hash = generate_password_hash(senha) if senha else None

    def checar_senha(self, senha: str) -> bool:
        return bool(self.senha_hash and senha and check_password_hash(self.senha_hash, senha))

    @property
    def is_active(self) -> bool:  # usado pelo Flask-Login
        return bool(self.ativo)

    @property
    def is_admin(self) -> bool:
        return self.perfil == c.PERFIL_ADMIN

    @property
    def pode_gerir(self) -> bool:
        """Insere, edita, exclui, aprova e ve dados restritos e relatorios."""
        return self.perfil in c.PERFIS_GESTAO

    @property
    def rotulo_perfil(self) -> str:
        return c.PERFIS.get(self.perfil, self.perfil)


# ---------------------------------------------------------------------------
# Cadastros de apoio
# ---------------------------------------------------------------------------
contato_grupo = db.Table(
    "contato_grupo",
    db.Column("contato_id", db.Integer, db.ForeignKey("contatos.id", ondelete="CASCADE"), primary_key=True),
    db.Column("grupo_id", db.Integer, db.ForeignKey("grupos.id", ondelete="CASCADE"), primary_key=True),
)


class Grupo(db.Model):
    __tablename__ = "grupos"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(120), nullable=False, unique=True)
    ordem = db.Column(db.Integer, nullable=False, default=0)
    ativo = db.Column(db.Boolean, nullable=False, default=True)

    @classmethod
    def ordenados(cls, apenas_ativos: bool = True):
        consulta = cls.query
        if apenas_ativos:
            consulta = consulta.filter(cls.ativo.is_(True))
        return consulta.order_by(cls.ordem, cls.nome).all()


class Empresa(db.Model):
    __tablename__ = "empresas"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(255), nullable=False)
    #: Nome sem acentos e em minusculas. E unico: impede "ABEL" e "abel".
    nome_normalizado = db.Column(db.String(255), nullable=False, unique=True, index=True)
    criado_por_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"))
    criado_em = db.Column(db.DateTime, nullable=False, default=agora)

    criado_por = db.relationship("Usuario")

    def definir_nome(self, nome: str) -> None:
        self.nome = nome.strip()
        self.nome_normalizado = normalizar(nome)[:255]


# ---------------------------------------------------------------------------
# Contato (a ficha)
# ---------------------------------------------------------------------------
class Contato(db.Model):
    __tablename__ = "contatos"

    id = db.Column(db.Integer, primary_key=True)

    nome = db.Column(db.String(200))
    cargo = db.Column(db.String(200))
    empresa_id = db.Column(db.Integer, db.ForeignKey("empresas.id", ondelete="SET NULL"), index=True)
    email = db.Column(db.String(254))
    celular = db.Column(db.String(40))
    telefone_comercial = db.Column(db.String(40))
    endereco_comercial = db.Column(db.Text)

    secretaria_nome = db.Column(db.String(200))
    secretaria_email = db.Column(db.String(254))
    secretaria_celular = db.Column(db.String(40))

    inicio_mandato = db.Column(db.String(200))
    horario_trabalho = db.Column(db.String(200))
    ramal = db.Column(db.String(40))
    preferencias = db.Column(db.Text)
    observacoes = db.Column(db.Text)

    # Dados restritos: cifrados no banco, visiveis so a gestor e administrador.
    nacionalidade = db.Column(TextoCifrado)
    estado_civil = db.Column(TextoCifrado)
    qualificacao = db.Column(TextoCifrado)
    rg = db.Column(TextoCifrado)
    cpf = db.Column(TextoCifrado)
    cnpj = db.Column(TextoCifrado)
    fidelidade_aerea = db.Column(TextoCifrado)

    foto = db.Column(db.String(64))

    #: Texto normalizado (nome, cargo, empresa, e-mails) usado pela busca.
    busca = db.Column(db.Text)
    letra = db.Column(db.String(1), index=True)

    criado_em = db.Column(db.DateTime, nullable=False, default=agora)
    criado_por_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"))
    atualizado_em = db.Column(db.DateTime)
    atualizado_por_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"))
    #: Exclusao logica: a ficha some das telas, mas o historico continua.
    excluido_em = db.Column(db.DateTime, index=True)
    excluido_por_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"))

    empresa = db.relationship("Empresa", backref=db.backref("contatos", lazy="dynamic"))
    grupos = db.relationship("Grupo", secondary=contato_grupo, order_by="Grupo.ordem", lazy="selectin")
    criado_por = db.relationship("Usuario", foreign_keys=[criado_por_id])
    atualizado_por = db.relationship("Usuario", foreign_keys=[atualizado_por_id])

    @classmethod
    def ativos(cls):
        return cls.query.filter(cls.excluido_em.is_(None))

    @property
    def numero(self) -> str:
        return f"{self.id:04d}" if self.id else "----"

    @property
    def nome_exibicao(self) -> str:
        return self.nome or "(contato sem nome)"


# ---------------------------------------------------------------------------
# Solicitacoes de usuarios comuns
# ---------------------------------------------------------------------------
class Solicitacao(db.Model):
    __tablename__ = "solicitacoes"

    id = db.Column(db.Integer, primary_key=True)
    tipo = db.Column(db.String(20), nullable=False)
    status = db.Column(db.String(20), nullable=False, default=c.STATUS_PENDENTE, index=True)
    contato_id = db.Column(db.Integer, db.ForeignKey("contatos.id", ondelete="SET NULL"), index=True)
    #: Nome do contato no momento do pedido, para o relatorio continuar legivel.
    contato_nome = db.Column(db.String(200))

    #: Valores propostos (somente os campos alterados, ou todos na inclusao).
    dados = db.Column(db.JSON, nullable=False, default=dict)
    #: {campo: {"de": texto, "para": texto}} - fotografia legivel do pedido.
    mudancas = db.Column(db.JSON, nullable=False, default=dict)
    foto_proposta = db.Column(db.String(64))
    remover_foto = db.Column(db.Boolean, nullable=False, default=False)
    comentario = db.Column(db.Text)

    solicitante_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=False)
    criado_em = db.Column(db.DateTime, nullable=False, default=agora, index=True)
    decidido_por_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"))
    decidido_em = db.Column(db.DateTime)
    motivo_decisao = db.Column(db.Text)
    email_enviado = db.Column(db.Boolean, nullable=False, default=False)

    contato = db.relationship("Contato", backref=db.backref("solicitacoes", lazy="dynamic"))
    solicitante = db.relationship("Usuario", foreign_keys=[solicitante_id])
    decidido_por = db.relationship("Usuario", foreign_keys=[decidido_por_id])

    @property
    def pendente(self) -> bool:
        return self.status == c.STATUS_PENDENTE

    @property
    def rotulo_tipo(self) -> str:
        return c.TIPOS_SOLICITACAO.get(self.tipo, self.tipo)

    @property
    def rotulo_status(self) -> str:
        return c.STATUS_SOLICITACAO.get(self.status, self.status)


# ---------------------------------------------------------------------------
# Historico (relatorios)
# ---------------------------------------------------------------------------
class Historico(db.Model):
    __tablename__ = "historico"

    id = db.Column(db.Integer, primary_key=True)
    contato_id = db.Column(db.Integer, db.ForeignKey("contatos.id", ondelete="SET NULL"), index=True)
    contato_nome = db.Column(db.String(200))
    acao = db.Column(db.String(20), nullable=False)
    origem = db.Column(db.String(20), nullable=False, default=c.ORIGEM_DIRETA)
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"))
    solicitacao_id = db.Column(db.Integer, db.ForeignKey("solicitacoes.id", ondelete="SET NULL"))
    #: {campo: [antes, depois]} em texto legivel. Dados restritos nunca
    #: aparecem aqui em claro (ver constants.VALOR_RESTRITO).
    mudancas = db.Column(db.JSON, nullable=False, default=dict)
    criado_em = db.Column(db.DateTime, nullable=False, default=agora, index=True)

    contato = db.relationship("Contato")
    usuario = db.relationship("Usuario")
    solicitacao = db.relationship("Solicitacao")

    @property
    def rotulo_acao(self) -> str:
        return c.ACOES.get(self.acao, self.acao)

    @property
    def rotulo_origem(self) -> str:
        return c.ORIGENS.get(self.origem, self.origem)
