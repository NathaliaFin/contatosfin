"""Teste de ponta a ponta do Contatos Fin (copia local SQLite)."""
import io
import re
import sys

import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import preview_local  # popula instance/preview.db (copia de teste)
from PIL import Image

app = preview_local.app
app.config["WTF_CSRF_ENABLED"] = False
from app import constants as c
from app.extensions import db
from app.models import Contato, Empresa, Historico, Solicitacao
from sqlalchemy import text

falhas = []


def ok(cond, msg):
    print(("  OK   " if cond else "  FALHA ") + msg)
    if not cond:
        falhas.append(msg)


def entrar(cli, email):
    cli.post("/auth/sair")
    r = cli.post("/auth/login", data={"email": email, "senha": "Fin@2026"})
    return r


def png(cor=(0, 40, 230), tamanho=(800, 600)):
    b = io.BytesIO()
    Image.new("RGB", tamanho, cor).save(b, "PNG")
    b.seek(0)
    return b


with app.app_context():
    cli = app.test_client()

    print("\n[1] Login e permissoes")
    r = cli.get("/contatos")
    ok(r.status_code == 302 and "/auth/login" in r.location, "anonimo redirecionado ao login")
    r = cli.get("/auth/login")
    ok(r.status_code == 200 and b"Contatos" in r.data, "tela de login abre")
    r = cli.post("/auth/login", data={"email": "usuario@fin.org.br", "senha": "errada"})
    ok(r.status_code == 401, "senha errada recusada")

    entrar(cli, "usuario@fin.org.br")
    r = cli.get("/contatos")
    ok(r.status_code == 200 and b"Helena Duarte" in r.data, "usuario ve o fichario")
    ok(b"Altera\xc3\xa7\xc3\xa3o pendente" in r.data, "carimbo de alteracao pendente aparece na lista")
    ok(cli.get("/contatos/novo").status_code == 403, "usuario NAO cria ficha direto")
    ok(cli.get("/relatorios/").status_code == 403, "usuario NAO ve relatorios")
    ok(cli.get("/admin/usuarios").status_code == 403, "usuario NAO ve administracao")
    helena = Contato.query.filter_by(nome="Helena Duarte Vasconcelos").first()
    r = cli.get(f"/contatos/{helena.id}")
    ok(r.status_code == 200 and b"Dados restritos" not in r.data and b"casada" not in r.data, "usuario NAO ve dados restritos")
    ok(cli.post(f"/contatos/{helena.id}/editar", data={"nome": "X"}).status_code == 403, "usuario NAO edita direto (POST)")

    print("\n[2] Busca sem diferenca de maiusculas/acentos")
    r = cli.get("/contatos?q=ABEL")
    ok(b"Helena Duarte" in r.data and b"Carlos Eduardo" in r.data, "busca 'ABEL' acha as duas fichas")
    r = cli.get("/contatos?q=angela")
    ok("Ângela".encode() in r.data, "busca 'angela' acha 'Ângela'")
    ok(Empresa.query.filter(Empresa.nome_normalizado.like("abel%")).count() == 1, "'ABEL' e 'abel' viraram UMA empresa so")
    r = cli.get("/empresas/buscar?q=abEL")
    ok(r.is_json and len(r.json) == 1, "autocompletar de empresa ignora maiusculas")
    r = cli.post("/empresas/criar", json={"nome": "aBeCiP"})
    ok(r.json["criada"] is False and r.json["nome"] == "ABECIP", "cadastrar 'aBeCiP' reaproveita 'ABECIP'")
    r = cli.post("/empresas/criar", json={"nome": "Nova Entidade Teste"})
    ok(r.json["criada"] is True, "usuario comum cadastra empresa nova")

    print("\n[3] Usuario solicita alteracao")
    r = cli.get(f"/contatos/{helena.id}/solicitar-alteracao")
    ok(r.status_code == 200 and b'name="cpf"' not in r.data, "formulario do usuario sem campos restritos")
    form = {
        "nome": helena.nome, "cargo": "Presidente", "empresa": helena.empresa.nome,
        "email": helena.email, "celular": "11 9 1234-5678", "telefone_comercial": "",
        "endereco_comercial": helena.endereco_comercial or "", "secretaria_nome": helena.secretaria_nome,
        "secretaria_email": helena.secretaria_email, "secretaria_celular": helena.secretaria_celular,
        "inicio_mandato": helena.inicio_mandato, "horario_trabalho": helena.horario_trabalho,
        "ramal": helena.ramal, "preferencias": helena.preferencias, "observacoes": "",
        "grupos": [str(g.id) for g in helena.grupos], "comentario": "Telefone novo",
        "cpf": "111.444.777-35",  # tentativa de injetar dado restrito: deve ser ignorada
    }
    r = cli.post(f"/contatos/{helena.id}/solicitar-alteracao", data={**form, "email": "invalido@"})
    ok(r.status_code == 400 and "E-mail em formato inválido".encode() in r.data, "e-mail invalido e barrado")
    r = cli.post(f"/contatos/{helena.id}/solicitar-alteracao",
                 data={**form, "foto": (png(), "foto.png")}, content_type="multipart/form-data")
    ok(r.status_code == 302, "solicitacao enviada")
    s = Solicitacao.query.order_by(Solicitacao.id.desc()).first()
    db.session.refresh(helena)
    ok(s.tipo == c.TIPO_ALTERACAO and s.pendente, "solicitacao gravada como pendente")
    ok(set(s.dados) == {"celular"} and s.dados["celular"] == "(11) 91234-5678", "so o campo alterado vai no pedido, ja formatado")
    ok("cpf" not in s.dados, "dado restrito injetado foi ignorado")
    ok(helena.celular == "(11) 98888-1001", "ficha NAO mudou antes da aprovacao")
    ok(s.foto_proposta and not helena.foto, "foto proposta guardada sem trocar a foto da ficha")
    log = (preview_local.INSTANCE / "emails-nao-enviados.log").read_text(encoding="utf-8")
    ok("gestor@fin.org.br" in log and f"Nº {s.id}" in log, "e-mail ao gestor gerado (log local, SMTP sem senha)")
    r = cli.get(f"/contatos/{helena.id}")
    ok("Alteração pendente".encode() in r.data, "ficha mostra 'Alteracao pendente'")
    ok(cli.post(f"/solicitacoes/{s.id}/aprovar").status_code == 403, "usuario NAO aprova o proprio pedido")

    print("\n[4] Gestor aprova")
    entrar(cli, "gestor@fin.org.br")
    r = cli.get("/solicitacoes/")
    ok(r.status_code == 200 and b"Helena" in r.data, "fila de solicitacoes do gestor")
    r = cli.get(f"/solicitacoes/{s.id}")
    ok(b"(11) 91234-5678" in r.data and b"Aprovar" in r.data, "tela de analise mostra antes/depois")
    ok(cli.get(f"/solicitacoes/{s.id}/foto").status_code == 200, "gestor ve a foto proposta")
    r = cli.post(f"/solicitacoes/{s.id}/aprovar", data={"motivo": "Confirmado com a secretaria."})
    ok(r.status_code == 302, "aprovacao executada")
    db.session.refresh(helena); db.session.refresh(s)
    ok(helena.celular == "(11) 91234-5678" and s.status == c.STATUS_APROVADA, "ficha atualizada e pedido aprovado")
    ok(helena.foto == s.foto_proposta, "foto aplicada na ficha")
    ok(cli.get(f"/contatos/{helena.id}/foto").status_code == 200, "foto da ficha servida")
    h = Historico.query.filter_by(solicitacao_id=s.id).first()
    ok(h and h.origem == c.ORIGEM_SOLICITACAO and "celular" in h.mudancas, "historico registra a aprovacao")
    log = (preview_local.INSTANCE / "emails-nao-enviados.log").read_text(encoding="utf-8")
    ok("usuario@fin.org.br" in log and "aprovada" in log, "e-mail de decisao ao solicitante gerado")

    print("\n[5] Gestor edita direto, dados restritos cifrados")
    r = cli.get(f"/contatos/{helena.id}")
    ok(b"Dados restritos" in r.data and b"casada" in r.data, "gestor ve dados restritos")
    valores = {**form, "cpf": "111.444.777-35", "cnpj": "", "rg": "12.345.678-9 SSP/SP", "nacionalidade": "brasileira",
               "estado_civil": "casada", "qualificacao": "dirigente de entidade de classe", "fidelidade_aerea": "Smiles 123",
               "celular": "(11) 91234-5678"}
    r = cli.post(f"/contatos/{helena.id}/editar", data={**valores, "cpf": "123.456.789-00"})
    ok(r.status_code == 400 and b"CPF inv" in r.data, "CPF com digito errado e barrado")
    r = cli.post(f"/contatos/{helena.id}/editar", data=valores)
    ok(r.status_code == 302, "edicao direta salva")
    bruto = db.session.execute(text("SELECT cpf, rg FROM contatos WHERE id=:i"), {"i": helena.id}).first()
    ok(bruto[0] and "111" not in bruto[0] and bruto[0].startswith("gAAAA"), "CPF gravado CIFRADO no banco")
    db.session.expire_all()
    ok(db.session.get(Contato, helena.id).cpf == "111.444.777-35", "CPF decifrado ao ler")
    h = Historico.query.filter_by(contato_id=helena.id, origem=c.ORIGEM_DIRETA, acao=c.ACAO_ALTERACAO).order_by(Historico.id.desc()).first()
    ok(h and h.mudancas.get("cpf") == ["", c.VALOR_RESTRITO] and "111" not in str(h.mudancas), "historico NAO guarda CPF em claro")

    print("\n[6] Inclusao e exclusao pelo usuario, recusa pelo gestor")
    entrar(cli, "usuario@fin.org.br")
    r = cli.post("/contatos/solicitar-inclusao", data={"nome": "Contato Sugerido", "empresa": "nova entidade TESTE", "comentario": "Conheci no evento"})
    ok(r.status_code == 302, "usuario sugere novo contato")
    inc = Solicitacao.query.filter_by(tipo=c.TIPO_INCLUSAO).order_by(Solicitacao.id.desc()).first()
    ok(Contato.query.filter_by(nome="Contato Sugerido").count() == 0, "contato sugerido ainda NAO entra no fichario")
    alvo = Contato.query.filter_by(nome="Otávio Martins Leal").first()
    cli.post(f"/contatos/{alvo.id}/solicitar-exclusao", data={"comentario": "Não atua mais"})
    exc = Solicitacao.query.filter_by(tipo=c.TIPO_EXCLUSAO).order_by(Solicitacao.id.desc()).first()
    entrar(cli, "gestor@fin.org.br")
    cli.post(f"/solicitacoes/{inc.id}/aprovar")
    novo = Contato.query.filter_by(nome="Contato Sugerido").first()
    ok(novo is not None and novo.empresa.nome == "Nova Entidade Teste", "inclusao aprovada cria a ficha e reaproveita a empresa")
    cli.post(f"/solicitacoes/{exc.id}/recusar", data={"motivo": "Ainda é conselheiro."})
    db.session.refresh(exc); db.session.refresh(alvo)
    ok(exc.status == c.STATUS_RECUSADA and alvo.excluido_em is None, "exclusao recusada mantem a ficha")
    r = cli.post(f"/contatos/{alvo.id}/excluir")
    db.session.refresh(alvo)
    ok(alvo.excluido_em is not None and cli.get(f"/contatos/{alvo.id}").status_code == 404, "gestor exclui (exclusao logica)")

    print("\n[7] Relatorios, CSV e telas restantes")
    r = cli.get("/relatorios/")
    ok(r.status_code == 200 and b"Helena" in r.data, "relatorio de historico")
    r = cli.get("/relatorios/?aba=solicitacoes&status=aprovada")
    ok(r.status_code == 200, "relatorio de solicitacoes filtrado")
    r = cli.get("/relatorios/exportar?aba=historico")
    ok(r.status_code == 200 and r.data.startswith("﻿".encode()) and "Ação".encode() in r.data, "CSV exportado com BOM")
    for url in ["/empresas/", "/admin/grupos", "/contatos/novo", f"/contatos/{helena.id}/editar", "/contatos?letra=H", "/contatos?pendentes=1"]:
        ok(cli.get(url).status_code == 200, f"GET {url}")
    ok(cli.get("/admin/usuarios").status_code == 403, "gestor NAO ve usuarios (so admin)")

    print("\n[8] Administrador")
    entrar(cli, "admin@fin.org.br")
    ok(cli.get("/admin/usuarios").status_code == 200, "admin ve usuarios")
    r = cli.post("/admin/usuarios/novo", data={"nome": "Nova Gestora", "email": "nova@fin.org.br", "perfil": "gestor", "ativo": "1"})
    ok(r.status_code == 302, "admin cria gestor")
    from app.models import Usuario
    eu = Usuario.query.filter_by(email="admin@fin.org.br").first()
    r = cli.post(f"/admin/usuarios/{eu.id}", data={"nome": eu.nome, "email": eu.email, "perfil": "usuario", "ativo": "1"})
    ok(r.status_code == 400, "admin NAO rebaixa a si mesmo")
    r = cli.post("/admin/grupos", data={"acao": "criar", "nome": "Comitê Jurídico"})
    ok(r.status_code == 302, "grupo criado")

    print("\n[9] Foto invalida")
    entrar(cli, "gestor@fin.org.br")
    r = cli.post("/contatos/novo", data={"nome": "Teste Foto", "foto": (io.BytesIO(b"nao sou imagem"), "x.jpg")},
                 content_type="multipart/form-data")
    ok(r.status_code == 400 and "não é uma imagem".encode() in r.data, "arquivo falso recusado")

    print("\n[10] Demonstracao: criar e remover sem tocar no resto")
    from app.models import Usuario
    from app.services import contatos as servico
    from app.services import demo
    antes = {"contatos": Contato.query.count(), "pedidos": Solicitacao.query.count(),
             "empresas": Empresa.query.count(), "usuarios": Usuario.query.count(), "historico": Historico.query.count()}
    r = demo.criar()
    ok(r["fichas"] == 22 and r["pedidos"] == 4 and demo.existe(), "demo cria 22 fichas e 4 pedidos")
    # um gestor real aprova a inclusao ficticia: a ficha nova sai em nome dele
    gestor_real = Usuario.query.filter_by(email="gestor@fin.org.br").first()
    pedido = Solicitacao.query.join(Usuario, Solicitacao.solicitante_id == Usuario.id).filter(
        Usuario.email == demo.EMAIL_USUARIO, Solicitacao.tipo == c.TIPO_INCLUSAO).first()
    servico.aprovar(pedido, gestor_real)
    db.session.commit()
    r = demo.remover()
    depois = {"contatos": Contato.query.count(), "pedidos": Solicitacao.query.count(),
              "empresas": Empresa.query.count(), "usuarios": Usuario.query.count(), "historico": Historico.query.count()}
    ok(r["fichas"] == 23, "remocao apaga as 22 fichas + a incluida a partir do pedido ficticio")
    ok(antes == depois, f"banco volta exatamente ao estado anterior ({antes} == {depois})")
    ok(not demo.existe(), "demo nao existe mais")

    print("\n[11] Exportar dados em Excel")
    from openpyxl import load_workbook
    entrar(cli, "usuario@fin.org.br")
    ok(cli.post("/relatorios/exportar-contatos").status_code == 403, "usuario NAO exporta")
    entrar(cli, "gestor@fin.org.br")
    ok(b"Exportar dados" in cli.get("/relatorios/?aba=exportar").data, "aba Exportar dados aparece")
    ativos = Contato.ativos().count()
    registros = Historico.query.filter_by(acao=c.ACAO_EXPORTACAO).count()
    r = cli.post("/relatorios/exportar-contatos")
    ws = load_workbook(io.BytesIO(r.data)).active
    cab = [x.value for x in ws[1]]
    ok(r.status_code == 200 and ws.max_row == ativos + 1, f"planilha com todas as {ativos} fichas ativas")
    ok("CPF" not in cab and "Nome" in cab and "Listas de trabalho" in cab, "sem restritos por padrao")
    r = cli.post("/relatorios/exportar-contatos", data={"restritos": "1"})
    ws = load_workbook(io.BytesIO(r.data)).active
    linhas = {row[1]: dict(zip([x.value for x in ws[1]], row)) for row in ws.iter_rows(min_row=2, values_only=True)}
    ok(linhas.get("Helena Duarte Vasconcelos", {}).get("Estado civil") == "casada", "restritos decifrados quando pedidos")
    ok(Historico.query.filter_by(acao=c.ACAO_EXPORTACAO).count() == registros + 2, "cada exportacao fica no historico")

# Fora do app_context do resto do teste: la dentro o usuario da requisicao
# anterior fica guardado em g e a entrada nem chega a acontecer.
print("\n[12] Sair de verdade com 'manter conectado' (como na entrada pela Microsoft)")
novo = app.test_client()
novo.post("/auth/login", data={"email": "gestor@fin.org.br", "senha": "Fin@2026", "lembrar": "1"})
ok(novo.get_cookie("remember_token") is not None, "entrada cria o cookie de manter conectado")
novo.post("/auth/sair")
r = novo.get("/contatos")
ok(r.status_code == 302 and "/auth/login" in r.headers["Location"], "depois de sair, volta para a tela de login")
ok(novo.get_cookie("remember_token") is None, "cookie de manter conectado apagado")

print("\n[13] Aplicativo instalavel")
m = novo.get("/manifest.webmanifest")
ok(m.status_code == 200 and m.json["short_name"] == "Contatos" and len(m.json["icons"]) == 3, "manifesto com nome e icones")
ok(all(novo.get(i["src"]).status_code == 200 for i in m.json["icons"]), "icones existem")
w = novo.get("/sw.js")
ok(w.status_code == 200 and "javascript" in w.mimetype and b"offline.html" in w.data, "service worker servido na raiz")
ok(novo.get("/static/offline.html").status_code == 200, "pagina sem conexao existe")
ok(b"rel=\"manifest\"" in novo.get("/auth/login").data, "tela de entrada aponta para o manifesto")

print("\n[14] Listas de trabalho: participantes e impressao")
novo.post("/auth/login", data={"email": "usuario@fin.org.br", "senha": "Fin@2026"})
with app.app_context():
    from app.models import Grupo as G
    conselho = G.query.filter_by(nome="Conselho").first()
    membros = [x.nome for x in Contato.ativos().filter(Contato.grupos.any(G.id == conselho.id)).all()]
r = novo.get(f"/listas/{conselho.id}")
html = r.get_data(as_text=True)
ok(r.status_code == 200 and all(m in html for m in membros) and len(membros) > 0, f"pagina da lista mostra os {len(membros)} participantes")
for modo in ("dados", "nomes", "fotos"):
    r = novo.get(f"/listas/{conselho.id}/imprimir?modo={modo}")
    h = r.get_data(as_text=True)
    ok(r.status_code == 200 and all(m in h for m in membros), f"impressao '{modo}' com todos os participantes")
h_nomes = novo.get(f"/listas/{conselho.id}/imprimir?modo=nomes").get_data(as_text=True)
ok("E-mail" not in h_nomes.split("<main")[1], "modo so nomes nao traz dados de contato")
ok("casada" not in novo.get(f"/listas/{conselho.id}/imprimir?modo=dados").get_data(as_text=True), "impressao nunca traz dados restritos")
ok(novo.get("/listas/99999").status_code == 404, "lista inexistente da 404")

print("\n[15] Trava de fichas repetidas")
with app.app_context():
    hel = Contato.query.filter_by(nome="Helena Duarte Vasconcelos").first()
    hel_id, hel_email, hel_cel = hel.id, hel.email, hel.celular
    outro = Contato.ativos().filter(Contato.id != hel.id, Contato.email.isnot(None)).first()
    outro_id = outro.id
    excluida = Contato.query.filter(Contato.excluido_em.isnot(None), Contato.email.isnot(None)).first()
    excluida_email = excluida.email if excluida else None
    total = lambda: Contato.ativos().count()
    antes = total()

novo.post("/auth/sair")
novo.post("/auth/login", data={"email": "gestor@fin.org.br", "senha": "Fin@2026"})
r = novo.post("/contatos/novo", data={"nome": "Outra Pessoa", "email": hel_email.upper()})
h = r.get_data(as_text=True)
ok(r.status_code == 409 and "Já existe uma ficha com este e-mail" in h and "Helena Duarte" in h, "e-mail repetido (maiusculas) TRAVA a nova ficha")
ok("salvar mesmo assim" not in h, "trava de e-mail nao oferece 'salvar mesmo assim'")
r = novo.post("/contatos/novo", data={"nome": "Outra Pessoa", "email": hel_email, "confirmar_repetido": "1"})
ok(r.status_code == 409, "confirmar NAO fura a trava de e-mail")

r = novo.post("/contatos/novo", data={"nome": "helena duarte VASCONCELOS", "email": "homonima@exemplo.com.br"})
h = r.get_data(as_text=True)
ok(r.status_code == 409 and "Pode ser a mesma pessoa" in h and "mesmo nome" in h, "nome igual (sem diferenca de maiusculas) so AVISA")
with app.app_context():
    ok(total() == antes, "aviso nao grava nada")
r = novo.post("/contatos/novo", data={"nome": "helena duarte VASCONCELOS", "email": "homonima@exemplo.com.br", "confirmar_repetido": "1"})
ok(r.status_code == 302, "'e outra pessoa' grava a homonima")
with app.app_context():
    homonima = Contato.query.filter_by(email="homonima@exemplo.com.br").first()
    homonima_id = homonima.id
r = novo.post(f"/contatos/{homonima_id}/editar", data={"nome": "helena duarte VASCONCELOS", "email": "homonima@exemplo.com.br", "cargo": "Diretora"})
ok(r.status_code == 302, "editar a homonima sem mexer no nome nao avisa de novo")

digitos = re.sub(r"\D", "", hel_cel or "")
r = novo.post("/contatos/novo", data={"nome": "Pessoa do Celular", "celular": digitos})
ok(r.status_code == 409 and "mesmo celular" in r.get_data(as_text=True), "celular igual (outro formato) avisa")

r = novo.post(f"/contatos/{outro_id}/editar", data={"nome": "Nome Qualquer Teste", "email": hel_email})
ok(r.status_code == 409 and "Já existe uma ficha com este e-mail" in r.get_data(as_text=True), "edicao com e-mail de outra ficha TRAVA")
if excluida_email:
    r = novo.post("/contatos/novo", data={"nome": "Reaproveita E-mail", "email": excluida_email})
    ok(r.status_code == 302, "e-mail de ficha excluida pode ser usado de novo")

novo.post("/auth/sair")
novo.post("/auth/login", data={"email": "usuario@fin.org.br", "senha": "Fin@2026"})
r = novo.post("/contatos/solicitar-inclusao", data={"nome": "Sugestao Repetida", "email": hel_email})
ok(r.status_code == 409 and "peça a alteração por lá" in r.get_data(as_text=True), "pedido de inclusao com e-mail existente TRAVA")
r = novo.post("/contatos/solicitar-inclusao", data={"nome": "Pessoa Nova Pedido", "email": "pedido.novo@exemplo.com.br"})
ok(r.status_code == 302, "pedido de inclusao com e-mail novo passa")
r = novo.post("/contatos/solicitar-inclusao", data={"nome": "Mesma Pessoa Pedido", "email": "pedido.novo@exemplo.com.br"})
ok(r.status_code == 409 and "pedido de inclusão com este e-mail" in r.get_data(as_text=True), "segundo pedido com o mesmo e-mail TRAVA")
r = novo.post(f"/contatos/{outro_id}/solicitar-alteracao", data={"nome": "Nome Qualquer", "email": hel_email})
ok(r.status_code == 409, "pedido de alteracao para e-mail de outra ficha TRAVA")

# aprovacao: o e-mail apareceu numa ficha depois do pedido
with app.app_context():
    from app.models import Usuario as U
    from app.services import contatos as sv
    pedido = Solicitacao.query.filter_by(tipo=c.TIPO_INCLUSAO, status=c.STATUS_PENDENTE).order_by(Solicitacao.id.desc()).first()
    pedido_id = pedido.id
    ok(pedido.dados.get("email") == "pedido.novo@exemplo.com.br", "pedido pendente encontrado")
    sv.criar_contato({"nome": "Cadastro Paralelo", "email": "pedido.novo@exemplo.com.br"}, U.query.filter_by(email="gestor@fin.org.br").first())
    db.session.commit()
novo.post("/auth/sair")
novo.post("/auth/login", data={"email": "gestor@fin.org.br", "senha": "Fin@2026"})
h = novo.get(f"/solicitacoes/{pedido_id}").get_data(as_text=True)
ok("Aprovação bloqueada" in h and "Cadastro Paralelo" in h, "tela do pedido mostra a trava ao gestor")
novo.post(f"/solicitacoes/{pedido_id}/aprovar")
with app.app_context():
    ok(db.session.get(Solicitacao, pedido_id).status == c.STATUS_PENDENTE, "aprovacao barrada: pedido continua pendente")
    ok(Contato.ativos().filter(Contato.email == "pedido.novo@exemplo.com.br").count() == 1, "nenhuma segunda ficha com o mesmo e-mail")

print("\n[16] Montar a lista pela propria lista")
novo.post(f"/solicitacoes/{pedido_id}/recusar")
r = novo.post("/admin/grupos", data={"acao": "criar", "nome": "Lista Nova Teste"})
with app.app_context():
    from app.models import Grupo as G
    lid = G.query.filter_by(nome="Lista Nova Teste").first().id
    ids = [x.id for x in Contato.ativos().order_by(Contato.id).limit(3).all()]
ok(r.status_code == 302 and r.headers["Location"].endswith(f"/listas/{lid}/participantes"), "criar lista leva direto a escolha dos participantes")
h = novo.get(f"/listas/{lid}").get_data(as_text=True)
ok("Adicionar contatos" in h and "Adicionar ou tirar contatos" in h, "lista vazia mostra o botao de adicionar")
r = novo.get(f"/listas/{lid}/participantes")
ok(r.status_code == 200 and "Salvar participantes" in r.get_data(as_text=True), "pagina de escolha abre")
r = novo.post(f"/listas/{lid}/participantes", data={"vistos": ids, "marcados": ids})
with app.app_context():
    dentro = {x.id for x in Contato.ativos().filter(Contato.grupos.any(G.id == lid)).all()}
    hist = Historico.query.filter(Historico.contato_id.in_(ids), Historico.acao == c.ACAO_ALTERACAO).order_by(Historico.id.desc()).first()
ok(r.status_code == 302 and dentro == set(ids), "tres contatos entram na lista")
ok(hist is not None and "grupos" in hist.mudancas, "entrada na lista fica no historico da ficha")
r = novo.post(f"/listas/{lid}/participantes", data={"vistos": ids[:2], "marcados": ids[:1]})
with app.app_context():
    dentro = {x.id for x in Contato.ativos().filter(Contato.grupos.any(G.id == lid)).all()}
ok(dentro == {ids[0], ids[2]}, "desmarcado sai; quem nao estava na tela continua")
novo.post("/auth/sair")
novo.post("/auth/login", data={"email": "usuario@fin.org.br", "senha": "Fin@2026"})
ok(novo.get(f"/listas/{lid}/participantes").status_code == 403, "usuario NAO monta lista")
ok("Adicionar ou tirar" not in novo.get(f"/listas/{lid}").get_data(as_text=True), "usuario nao ve o botao")

print("\n" + ("TUDO CERTO" if not falhas else f"{len(falhas)} FALHA(S):\n - " + "\n - ".join(falhas)))
sys.exit(1 if falhas else 0)
