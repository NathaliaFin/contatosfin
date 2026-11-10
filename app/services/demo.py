"""Fichas FICTICIAS de demonstracao, para avaliar o sistema com dados.

    flask demo              cria as fichas (se ainda nao existirem)
    flask demo --remover    apaga TUDO o que a demonstracao criou

Tudo e criado em nome de dois usuarios inativos e sem senha
("Demonstracao - gestor" e "Demonstracao - usuario"), com e-mails
@exemplo.invalid. E por eles que a remocao encontra o que apagar - fichas,
empresas, pedidos, historico e fotos -, sem tocar em nada cadastrado de
verdade. Pessoas, telefones e e-mails sao inventados; nenhum CPF e gerado.
"""

import io

from PIL import Image, ImageDraw
from werkzeug.datastructures import FileStorage

from app import constants as c
from app.extensions import db
from app.models import Contato, Empresa, Grupo, Historico, Solicitacao, Usuario
from app.services import contatos as servico
from app.services import fotos

EMAIL_GESTOR = "demo.gestor@exemplo.invalid"
EMAIL_USUARIO = "demo.usuario@exemplo.invalid"

FICHAS = [
    dict(nome="Helena Duarte Vasconcelos", cargo="Presidente", empresa="ABEL - Associação Brasileira das Empresas de Leasing",
         email="helena.vasconcelos@exemplo.org.br", celular="(11) 98888-1001", secretaria_nome="Paula Ramos",
         secretaria_email="secretaria.abel@exemplo.org.br", secretaria_celular="(11) 97777-2002",
         endereco_comercial="Av. Paulista, 1000, 10º andar\nBela Vista — São Paulo/SP",
         grupos=["Conselho", "Diretoria", "RI", "Associadas", "Rep. classe 3"], inicio_mandato="Março de 2024",
         horario_trabalho="9h às 18h", ramal="2101", preferencias="Prefere contato por e-mail; reuniões pela manhã.",
         nacionalidade="brasileira", estado_civil="casada", qualificacao="dirigente de entidade de classe"),
    dict(nome="Ricardo Almeida Prado", cargo="Diretor-executivo", empresa="ABECIP",
         email="ricardo.prado@exemplo.com.br", telefone_comercial="(11) 3333-4040", grupos=["Diretoria", "Associadas"]),
    dict(nome="Beatriz Nogueira Lins", cargo="Superintendente de Relações Institucionais", empresa="ABBC",
         email="beatriz.lins@exemplo.com.br", celular="(61) 99123-4567", grupos=["RI"], foto=True,
         horario_trabalho="8h às 17h", preferencias="Agenda pela secretaria com 48h de antecedência."),
    dict(nome="Carlos Eduardo Menezes", cargo="Vice-presidente", empresa="abel - associação brasileira das empresas de leasing",
         celular="(11) 99555-0101", grupos=["Conselho"]),
    dict(nome="Daniela Freitas Rocha", cargo="Gerente jurídica", empresa="ABBI", email="daniela.rocha@exemplo.com.br",
         grupos=["Associadas"], foto=True),
    dict(nome="Eduardo Siqueira Campos", cargo="Conselheiro", empresa="ACREFI", grupos=["Conselho", "Rep. classe 3"],
         inicio_mandato="Primeiro contato em 2022"),
    dict(nome="Fernanda Torres Bastos", cargo="Assessora parlamentar", empresa="Fin",
         email="fernanda.bastos@exemplo.org.br", celular="(61) 98100-2233", ramal="1450", grupos=["RI"], foto=True),
    dict(nome="Gustavo Henrique Lobo", cargo="Presidente do conselho", empresa="ABECS", grupos=["Conselho", "Diretoria"],
         secretaria_nome="Márcia Lopes", secretaria_email="secretaria.abecs@exemplo.com.br"),
    dict(nome="Isabela Moura Pacheco", cargo="Coordenadora de eventos", empresa="ABECIP", email="isabela.pacheco@exemplo.com.br"),
    dict(nome="Jorge Luiz Antunes", cargo="Diretor financeiro", empresa="ANEPS", telefone_comercial="(11) 3030-5050",
         grupos=["Associadas"]),
    dict(nome="Ângela Ribeiro Coutinho", cargo="Secretária-geral", empresa="ABBC", grupos=["Diretoria"], foto=True,
         email="angela.coutinho@exemplo.com.br"),
    dict(nome="Otávio Martins Leal", cargo="Consultor", empresa="Leal Consultoria", celular="(21) 99876-5432"),
    dict(nome="Kátia Regina Fontes", cargo="Diretora de Relações Governamentais", empresa="ABECS",
         email="katia.fontes@exemplo.com.br", celular="(61) 99432-1188", grupos=["RI", "Diretoria"], foto=True,
         preferencias="Evitar ligações após as 19h."),
    dict(nome="Luís Fernando Barreto", cargo="Presidente", empresa="ACREFI", email="luis.barreto@exemplo.com.br",
         secretaria_nome="Cláudia Neves", secretaria_celular="(11) 97222-3344", grupos=["Conselho", "Associadas"],
         inicio_mandato="Abril de 2025", nacionalidade="brasileiro", estado_civil="divorciado"),
    dict(nome="Mariana Costa Albuquerque", cargo="Economista-chefe", empresa="ABBI", email="mariana.albuquerque@exemplo.com.br",
         grupos=["Rep. classe 3"]),
    dict(nome="Nelson Augusto Teixeira", cargo="Diretor de Autorregulação", empresa="ABBC", telefone_comercial="(11) 3101-2020",
         ramal="330", grupos=["Associadas"]),
    dict(nome="Patrícia Helena Sampaio", cargo="Chefe de gabinete", empresa="Fin", email="patricia.sampaio@exemplo.org.br",
         celular="(61) 98877-6655", grupos=["Diretoria"], foto=True, horario_trabalho="9h às 19h"),
    dict(nome="Renato Guimarães Paiva", cargo="Vice-presidente executivo", empresa="ANEPS", email="renato.paiva@exemplo.com.br",
         grupos=["Conselho"]),
    dict(nome="Sílvia Maria Andrade", cargo="Gerente de comunicação", empresa="ABECIP", email="silvia.andrade@exemplo.com.br",
         celular="(11) 98345-6789"),
    dict(nome="Thiago Bezerra Moraes", cargo="Assessor técnico", empresa="ABEL - Associação Brasileira das Empresas de Leasing",
         telefone_comercial="(11) 3285-1000", grupos=["RI"]),
    dict(nome="Vanessa Lacerda Pinto", cargo="Diretora jurídica", empresa="Leal Consultoria", email="vanessa.pinto@exemplo.com.br",
         grupos=["Rep. classe 3", "Associadas"]),
    dict(nome="Wagner Oliveira Brandão", cargo="Conselheiro fiscal", empresa="ABBI", celular="(31) 99654-3210",
         grupos=["Conselho"], observacoes="Participa das reuniões do conselho por videoconferência."),
]

_CORES_FOTO = [("#0028E6", "#DCE2FD"), ("#0000A0", "#C9D2FF"), ("#5C47FF", "#E6E1FF"), ("#0065FF", "#D6E6FF"), ("#7347FF", "#ECE4FF")]


def _foto_ilustrativa(indice: int) -> FileStorage:
    """Silhueta 3x4 nas cores da Fin (nao e foto de ninguem).

    Desenhada em 4x o tamanho final e reduzida com filtro LANCZOS: e o que
    deixa as bordas lisas, sem o serrilhado do desenho direto.
    """
    frente, fundo = _CORES_FOTO[indice % len(_CORES_FOTO)]
    k = 4
    img = Image.new("RGB", (450 * k, 600 * k), fundo)
    d = ImageDraw.Draw(img)
    d.ellipse((152 * k, 118 * k, 298 * k, 286 * k), fill=frente)                 # cabeca
    d.rounded_rectangle((62 * k, 320 * k, 388 * k, 700 * k), radius=160 * k, fill=frente)  # ombros
    img = img.resize((450, 600), Image.LANCZOS)
    arquivo = io.BytesIO()
    img.save(arquivo, "PNG")
    arquivo.seek(0)
    return FileStorage(stream=arquivo, filename="demo.png", content_type="image/png")


def refazer_fotos() -> int:
    """Redesenha as silhuetas das fichas ficticias cuja foto ninguem trocou."""
    gestor = Usuario.query.filter_by(email=EMAIL_GESTOR).first()
    if gestor is None:
        return 0
    indices = {f["nome"]: i for i, f in enumerate(FICHAS) if f.get("foto")}
    refeitas = 0
    for ct in Contato.query.filter_by(criado_por_id=gestor.id).filter(Contato.foto.isnot(None)):
        if ct.nome not in indices:
            continue
        trocada = any(
            "foto" in (h.mudancas or {})
            for h in Historico.query.filter_by(contato_id=ct.id, acao=c.ACAO_ALTERACAO)
        )
        if trocada:
            continue  # alguem enviou outra foto: nao mexe
        nova = fotos.salvar_upload(_foto_ilustrativa(indices[ct.nome]))
        fotos.apagar(ct.foto)
        ct.foto = nova
        refeitas += 1
    db.session.commit()
    return refeitas


def _usuario(email: str, nome: str, perfil: str) -> Usuario:
    u = Usuario.query.filter_by(email=email).first()
    if u is None:
        u = Usuario(nome=nome, email=email, perfil=perfil, ativo=False)
        db.session.add(u)
        db.session.flush()
    return u


def existe() -> bool:
    gestor = Usuario.query.filter_by(email=EMAIL_GESTOR).first()
    return bool(gestor and Contato.query.filter_by(criado_por_id=gestor.id).count())


def criar(criador=None, solicitante=None, com_fotos=True, com_pedidos=True) -> dict:
    """Cria as fichas. Sem ``criador``/``solicitante``, usa os usuarios de
    demonstracao (e assim a remocao consegue achar tudo depois)."""
    criador = criador or _usuario(EMAIL_GESTOR, "Demonstração — gestor", c.PERFIL_GESTOR)
    solicitante = solicitante or _usuario(EMAIL_USUARIO, "Demonstração — usuário", c.PERFIL_USUARIO)

    grupos = {g.nome: g.id for g in Grupo.query.all()}
    criados = []
    for i, dados in enumerate(FICHAS):
        valores = {k: v for k, v in dados.items() if k not in ("grupos", "foto")}
        valores["grupos"] = sorted(grupos[n] for n in dados.get("grupos", []) if n in grupos)
        foto = fotos.salvar_upload(_foto_ilustrativa(i)) if com_fotos and dados.get("foto") else None
        criados.append(servico.criar_contato(valores, criador, foto=foto))
    db.session.commit()

    pedidos = 0
    if com_pedidos:
        por_nome = {ct.nome: ct for ct in criados}
        # 1) alteracao de cargo e celular
        alvo = por_nome["Ricardo Almeida Prado"]
        v = servico.valores_do_contato(alvo, incluir_restritos=False)
        v.update(cargo="Presidente", celular="(11) 97654-3210")
        servico.solicitar_alteracao(alvo, v, solicitante, "Mudou de cargo em novembro.")
        # 2) alteracao de e-mail
        alvo = por_nome["Jorge Luiz Antunes"]
        v = servico.valores_do_contato(alvo, incluir_restritos=False)
        v.update(email="jorge.antunes@exemplo.com.br")
        servico.solicitar_alteracao(alvo, v, solicitante, "E-mail informado pela secretária.")
        # 3) exclusao
        servico.solicitar_exclusao(por_nome["Renato Guimarães Paiva"], solicitante, "Deixou a entidade em outubro.")
        # 4) inclusao de contato novo
        novo = servico.valores_do_contato(None, incluir_restritos=False)
        novo.update(nome="Yara Cristina Lemos", cargo="Diretora de Inovação", empresa="ABBC",
                    email="yara.lemos@exemplo.com.br", grupos=[grupos[n] for n in ("RI",) if n in grupos])
        servico.solicitar_inclusao(novo, solicitante, "Conheci no evento de inovação.")
        db.session.commit()
        pedidos = 4

    return {"fichas": len(criados), "pedidos": pedidos}


def remover() -> dict:
    """Apaga tudo o que a demonstracao criou. Nada mais e tocado."""
    demo = Usuario.query.filter(Usuario.email.in_((EMAIL_GESTOR, EMAIL_USUARIO))).all()
    ids_demo = [u.id for u in demo]
    if not ids_demo:
        return {"fichas": 0, "pedidos": 0, "empresas": 0}

    # Fichas criadas pela demonstracao + as que nasceram de pedidos de
    # inclusao fictícios aprovados por alguem de verdade.
    ids_incluidas = [
        s.contato_id for s in Solicitacao.query.filter(
            Solicitacao.solicitante_id.in_(ids_demo), Solicitacao.tipo == c.TIPO_INCLUSAO,
            Solicitacao.contato_id.isnot(None),
        )
    ]
    contatos = Contato.query.filter(
        Contato.criado_por_id.in_(ids_demo) | Contato.id.in_(ids_incluidas or [0])
    ).all()
    ids_contatos = [ct.id for ct in contatos]

    pedidos = Solicitacao.query.filter(
        (Solicitacao.solicitante_id.in_(ids_demo))
        | (Solicitacao.contato_id.in_(ids_contatos or [0]))
    ).all()
    for s in pedidos:
        fotos.apagar(s.foto_proposta)
    ids_pedidos = [s.id for s in pedidos]

    Historico.query.filter(
        (Historico.contato_id.in_(ids_contatos or [0]))
        | (Historico.solicitacao_id.in_(ids_pedidos or [0]))
        | (Historico.usuario_id.in_(ids_demo))
    ).delete(synchronize_session=False)
    for s in pedidos:
        db.session.delete(s)
    db.session.flush()

    for ct in contatos:
        fotos.apagar(ct.foto)
        ct.grupos = []  # o SQLAlchemy apaga os vinculos com os grupos
        db.session.delete(ct)
    db.session.flush()

    # Empresas criadas pela demonstracao que nao ficaram com nenhuma ficha.
    empresas = 0
    for e in Empresa.query.filter(Empresa.criado_por_id.in_(ids_demo)).all():
        if e.contatos.count() == 0:
            db.session.delete(e)
            empresas += 1
        else:
            e.criado_por_id = None

    for u in demo:
        Contato.query.filter_by(atualizado_por_id=u.id).update({"atualizado_por_id": None})
        Contato.query.filter_by(excluido_por_id=u.id).update({"excluido_por_id": None})
        db.session.delete(u)
    db.session.commit()
    return {"fichas": len(contatos), "pedidos": len(pedidos), "empresas": empresas}
