"""Testa a conexao com o MySQL do Azure usando o .env do projeto.

Usado pelo testar-banco.bat (Windows) e pelo preparar-servidor.sh (servidor).
Nao depende do restante do sistema, entao funciona mesmo antes das telas
existirem. A senha nunca e exibida.
"""
import os
import ssl
import sys
from pathlib import Path

try:
    import pymysql
except ImportError:
    print("ERRO: biblioteca PyMySQL nao instalada. Rode o '1. antes de comecar.bat'.")
    sys.exit(1)

RAIZ = Path(__file__).resolve().parent.parent


def ler_env(caminho):
    valores = {}
    if not caminho.exists():
        return valores
    for linha in caminho.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        chave, valor = linha.split("=", 1)
        valores[chave.strip()] = valor.strip().strip('"').strip("'")
    return valores


def main():
    env = ler_env(RAIZ / ".env")
    env.update({k: v for k, v in os.environ.items() if k.startswith("DB_")})

    faltando = [k for k in ("DB_HOST", "DB_DATABASE", "DB_USERNAME", "DB_PASSWORD") if not env.get(k)]
    if faltando:
        print("ERRO: preencha no .env: " + ", ".join(faltando))
        return 1

    contexto_ssl = None
    if env.get("DB_SSL", "true").lower() == "true":
        ca = env.get("DB_SSL_CA") or None
        contexto_ssl = ssl.create_default_context(cafile=ca)

    print("  Servidor : %s:%s" % (env["DB_HOST"], env.get("DB_PORT", "3306")))
    print("  Banco    : %s" % env["DB_DATABASE"])
    print("  Usuario  : %s" % env["DB_USERNAME"])
    print()

    try:
        conexao = pymysql.connect(
            host=env["DB_HOST"],
            port=int(env.get("DB_PORT", "3306")),
            user=env["DB_USERNAME"],
            password=env["DB_PASSWORD"],
            database=env["DB_DATABASE"],
            ssl=contexto_ssl,
            charset="utf8mb4",
            connect_timeout=15,
        )
    except pymysql.err.OperationalError as erro:
        codigo = erro.args[0] if erro.args else None
        print("  FALHA NA CONEXAO: %s" % (erro.args[1] if len(erro.args) > 1 else erro))
        if codigo == 1045:
            print("  -> Usuario ou senha recusados pelo banco. Confira o DB_PASSWORD no .env.")
        elif codigo in (2003, 2005):
            print("  -> Servidor inalcancavel. Confira a internet/VPN e o DB_HOST.")
        return 1

    with conexao:
        cur = conexao.cursor()
        cur.execute("SELECT VERSION()")
        versao = cur.fetchone()[0]
        cur.execute("SHOW STATUS LIKE 'Ssl_version'")
        linha_ssl = cur.fetchone()
        cur.execute("SHOW TABLES")
        tabelas = sorted(r[0] for r in cur.fetchall())

    print("  CONEXAO OK")
    print("  MySQL %s, criptografia %s" % (versao, (linha_ssl[1] if linha_ssl and linha_ssl[1] else "DESLIGADA")))
    print()
    print("  Tabelas existentes no banco:")
    if tabelas:
        for t in tabelas:
            print("    - " + t)
    else:
        print("    nenhuma - o banco ainda esta vazio")
    return 0


if __name__ == "__main__":
    sys.exit(main())
