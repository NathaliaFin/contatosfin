"""Constantes do sistema: perfis, campos da ficha e situacoes."""

from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Perfis de acesso
# ---------------------------------------------------------------------------
PERFIL_ADMIN = "admin"
PERFIL_GESTOR = "gestor"
PERFIL_USUARIO = "usuario"

PERFIS = {
    PERFIL_ADMIN: "Administrador",
    PERFIL_GESTOR: "Gestor de dados",
    PERFIL_USUARIO: "Usuário",
}

#: Perfis que inserem, editam, excluem e aprovam diretamente.
PERFIS_GESTAO = (PERFIL_ADMIN, PERFIL_GESTOR)


# ---------------------------------------------------------------------------
# Campos da ficha
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Campo:
    chave: str
    rotulo: str
    secao: str
    tipo: str = "texto"  # texto | textarea | email | telefone | cpf | cnpj | empresa | grupos
    restrito: bool = False
    tamanho: int = 200
    largura: str = "meia"  # inteira | meia | terco | quarto (grade de 12 colunas)


SECOES = {
    "dados": "Dados do contato",
    "secretaria": "Secretaria",
    "grupos": "Grupos de pesquisa",
    "observacoes": "Observações",
    "restritos": "Dados restritos",
}

CAMPOS: tuple[Campo, ...] = (
    Campo("nome", "Nome", "dados", largura="inteira"),
    Campo("cargo", "Cargo", "dados"),
    Campo("empresa", "Empresa", "dados", tipo="empresa"),
    Campo("email", "E-mail", "dados", tipo="email", tamanho=254),
    Campo("celular", "Celular", "dados", tipo="telefone", tamanho=40, largura="quarto"),
    Campo("telefone_comercial", "Telefone comercial", "dados", tipo="telefone", tamanho=40, largura="quarto"),
    Campo("endereco_comercial", "Endereço comercial", "dados", tipo="textarea", largura="inteira"),

    Campo("secretaria_nome", "Nome", "secretaria", largura="terco"),
    Campo("secretaria_email", "E-mail", "secretaria", tipo="email", tamanho=254, largura="terco"),
    Campo("secretaria_celular", "Celular", "secretaria", tipo="telefone", tamanho=40, largura="terco"),

    Campo("grupos", "Grupos de pesquisa", "grupos", tipo="grupos", largura="inteira"),

    Campo("inicio_mandato", "Início do mandato / primeiro contato", "observacoes"),
    Campo("horario_trabalho", "Horário de trabalho", "observacoes", largura="quarto"),
    Campo("ramal", "Ramal", "observacoes", tamanho=40, largura="quarto"),
    Campo("preferencias", "Preferências", "observacoes", tipo="textarea", largura="inteira"),
    Campo("observacoes", "Outras observações", "observacoes", tipo="textarea", largura="inteira"),

    Campo("nacionalidade", "Nacionalidade", "restritos", restrito=True, largura="terco"),
    Campo("estado_civil", "Estado civil", "restritos", restrito=True, largura="terco"),
    Campo("qualificacao", "Profissão / qualificação", "restritos", restrito=True, largura="terco"),
    Campo("rg", "Documento de identidade (RG e órgão)", "restritos", restrito=True, largura="terco"),
    Campo("cpf", "CPF", "restritos", tipo="cpf", restrito=True, largura="terco"),
    Campo("cnpj", "CNPJ", "restritos", tipo="cnpj", restrito=True, largura="terco"),
    Campo("fidelidade_aerea", "Fidelidade companhias aéreas", "restritos", tipo="textarea", restrito=True, largura="inteira"),
)

CAMPOS_POR_CHAVE = {c.chave: c for c in CAMPOS}
ROTULOS = {c.chave: (c.rotulo if c.secao != "secretaria" else f"{c.rotulo} da secretária") for c in CAMPOS}
ROTULOS["foto"] = "Foto"

#: Campos de texto simples gravados direto em colunas do Contato.
CAMPOS_TEXTO = tuple(c.chave for c in CAMPOS if c.tipo not in ("empresa", "grupos"))


def campos_da_secao(secao: str, incluir_restritos: bool = True):
    return [c for c in CAMPOS if c.secao == secao and (incluir_restritos or not c.restrito)]


# ---------------------------------------------------------------------------
# Solicitacoes
# ---------------------------------------------------------------------------
TIPO_INCLUSAO = "inclusao"
TIPO_ALTERACAO = "alteracao"
TIPO_EXCLUSAO = "exclusao"

TIPOS_SOLICITACAO = {
    TIPO_INCLUSAO: "Inclusão de contato",
    TIPO_ALTERACAO: "Alteração de dados",
    TIPO_EXCLUSAO: "Exclusão de contato",
}

STATUS_PENDENTE = "pendente"
STATUS_APROVADA = "aprovada"
STATUS_RECUSADA = "recusada"
STATUS_CANCELADA = "cancelada"

STATUS_SOLICITACAO = {
    STATUS_PENDENTE: "Pendente",
    STATUS_APROVADA: "Aprovada",
    STATUS_RECUSADA: "Recusada",
    STATUS_CANCELADA: "Cancelada",
}

# ---------------------------------------------------------------------------
# Historico
# ---------------------------------------------------------------------------
ACAO_INCLUSAO = "inclusao"
ACAO_ALTERACAO = "alteracao"
ACAO_EXCLUSAO = "exclusao"

ACOES = {
    ACAO_INCLUSAO: "Inclusão",
    ACAO_ALTERACAO: "Alteração",
    ACAO_EXCLUSAO: "Exclusão",
}

ORIGEM_DIRETA = "direta"
ORIGEM_SOLICITACAO = "solicitacao"

ORIGENS = {
    ORIGEM_DIRETA: "Feita pelo gestor",
    ORIGEM_SOLICITACAO: "Solicitação aprovada",
}

#: Texto gravado no historico no lugar do valor de um dado restrito: o
#: historico nao e cifrado, entao nunca guarda CPF, RG etc. em claro.
VALOR_RESTRITO = "(dado restrito)"

GRUPOS_INICIAIS = ("Conselho", "Diretoria", "RI", "Associadas", "Rep. classe 3")
