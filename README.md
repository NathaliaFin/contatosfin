# Contatos — Fin

Cadastro institucional de contatos da Confederação Nacional das Instituições
Financeiras, em **Python / Flask** com **MySQL** (Azure Database for MySQL).

- **Servidor de produção:** SRVAPP01 `172.16.0.12` — `https://contatos.fin.org.br`
- **Repositório:** https://github.com/NathaliaFin/contatosfin
- **Entrada:** conta Microsoft (SSO do Entra ID, como no afin) e, como acesso
  de emergência, e-mail e senha.
- **E-mail:** SMTP do Microsoft 365, como no sistema de reuniões.

Os scripts de uso diário (publicar, testar o banco, ver o log) estão em
[`scripts/`](scripts/) e explicados em [`scripts/Scripts.txt`](scripts/Scripts.txt).

---

## Perfis

| Perfil | Consulta | Dados restritos | Altera fichas | Aprova pedidos | Relatórios | Usuários |
|---|---|---|---|---|---|---|
| **Usuário** | sim | não | só por **solicitação** | — | — | — |
| **Gestor de dados** | sim | sim | direto | sim | sim | — |
| **Administrador** | sim | sim | direto | sim | sim | sim |

- Contas Microsoft `@fin.org.br` entram sozinhas com o perfil **Usuário**.
  O administrador promove a gestor em *Usuários*.
- Qualquer pessoa cadastra **empresas**, a qualquer momento. “ABEL”, “abel” e
  “Abel” são a mesma empresa (busca e cadastro ignoram maiúsculas e acentos).
- **Listas de trabalho** são mantidas por gestor e administrador.

## Como funciona a solicitação

1. O usuário abre a ficha e clica em **Solicitar alteração** (ou *Solicitar
   exclusão*, ou *Sugerir novo contato* na lista de contatos).
2. Altera direto nos campos — inclusive a foto — e envia.
3. Os gestores de dados recebem um e-mail. A ficha passa a mostrar o carimbo
   **ALTERAÇÃO PENDENTE**; nada muda nela ainda.
4. O gestor vê *antes → depois* campo a campo e **aprova** (a ficha é
   atualizada) ou **recusa**, com uma resposta opcional.
5. O solicitante recebe um e-mail com a decisão.

Tudo fica nos **Relatórios**: alterações nas fichas (feitas pelo gestor ou
aprovadas) e solicitações, com filtros e exportação para planilha.

## Dados restritos

Nacionalidade, estado civil, profissão, RG, CPF, CNPJ e fidelidade aérea:

- só gestor de dados e administrador veem;
- ficam **cifrados** no banco (chave `CHAVE_DADOS_RESTRITOS` do `.env` —
  **nunca troque** depois que houver dados);
- o histórico registra *que* mudaram, nunca os valores.

## Rodar no computador

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe preview_local.py      # cópia de teste, SQLite
```

Abre em <http://127.0.0.1:5000> com fichas **fictícias**. Usuários de teste
(senha `Fin@2026`): `admin@fin.org.br`, `gestor@fin.org.br`, `usuario@fin.org.br`.

Teste automático de todo o fluxo (perfis, solicitação, aprovação, e-mail,
criptografia):

```powershell
.\.venv\Scripts\python.exe tests\teste_fluxo.py
```

## Comandos

| Comando | O que faz |
|---|---|
| `flask testar-banco` | Testa a conexão com o banco (sem mostrar a senha) |
| `flask db upgrade` | Cria/atualiza as tabelas |
| `flask db migrate -m "texto"` | Gera migration depois de alterar `app/models.py` |
| `flask seed` | Cria as listas de trabalho iniciais e o administrador do `.env` |
| `flask criar-usuario` | Cria um usuário ou muda o perfil de um existente |

(`$env:FLASK_APP="wsgi.py"` antes, no PowerShell.)

## Estrutura

```
app/
  constants.py        perfis, campos da ficha, situações
  models.py           Usuario, Empresa, Grupo, Contato, Solicitacao, Historico
  services/           regras: contatos, fotos, email, sso, cripto, validacao
  routes/             auth, contatos, empresas, solicitacoes, relatorios, admin
  templates/          telas e e-mails
  static/             estilo.css, app.js, fonte Montserrat, logos Fin
migrations/           estrutura do banco (Alembic)
scripts/              publicar, testar banco, ver log...
tests/teste_fluxo.py  teste de ponta a ponta
```
