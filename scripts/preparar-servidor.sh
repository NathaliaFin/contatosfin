#!/bin/bash
# ===========================================================================
#  Preparacao inicial do servidor - Contatos Fin
#
#  Roda UMA VEZ, no SRVAPP01 (172.16.0.12). E chamado pelo
#  preparar-servidor.bat a partir do Windows -- nao precisa ser executado a mao.
#
#  Instala: o ambiente virtual, o servico systemd e o site no nginx.
#  Nao mexe no Portal de Eventos (/opt/eventos) nem em outro site do servidor.
#  E seguro rodar de novo: nao sobrescreve um .env que ja esteja no servidor.
# ===========================================================================
set -euo pipefail

DIR=/var/www/contatos
SERVICO=contatos
DOMINIO=contatos.fin.org.br
USUARIO=azureuser

echo "=========================================================="
echo " PREPARANDO O SERVIDOR"
echo "=========================================================="

# --- 1. Pacotes do sistema -------------------------------------------------
echo
echo "[1/8] Conferindo os pacotes do sistema..."
sudo apt-get update -qq
sudo apt-get install -y -qq python3-venv python3-pip nginx

# --- 2. Pasta do projeto ---------------------------------------------------
echo "[2/8] Criando a pasta do projeto em ${DIR}..."
sudo mkdir -p "${DIR}"
sudo chown -R "${USUARIO}:www-data" "${DIR}"
sudo chmod 2775 "${DIR}"

# --- 3. Codigo -------------------------------------------------------------
echo "[3/8] Instalando os arquivos do sistema..."
tar -xf /tmp/contatos-deploy.tar -C "${DIR}"
rm -f /tmp/contatos-deploy.tar

# --- 4. Configuracao (.env) ------------------------------------------------
echo "[4/8] Aplicando a configuracao..."
if [ -f "${DIR}/.env" ]; then
    echo "      O servidor ja tem um .env proprio. Mantido sem alteracao."
    rm -f /tmp/contatos.env
elif [ -f /tmp/contatos.env ]; then
    mv /tmp/contatos.env "${DIR}/.env"
    # A chave de producao precisa ser diferente da usada no computador local.
    NOVA_CHAVE=$(python3 -c "import secrets; print(secrets.token_hex(32))")
    sed -i "s|^SECRET_KEY=.*|SECRET_KEY=${NOVA_CHAVE}|" "${DIR}/.env"
    chmod 600 "${DIR}/.env"
    chown "${USUARIO}:${USUARIO}" "${DIR}/.env"
    echo "      Chave de seguranca propria gerada para o servidor."
else
    echo "      ERRO: nenhum .env foi enviado. O sistema nao sobe sem ele."
    exit 1
fi

# --- 5. Ambiente Python ----------------------------------------------------
echo "[5/8] Criando o ambiente Python e instalando as dependencias..."
cd "${DIR}"
if [ ! -d .venv ]; then
    python3 -m venv .venv
fi
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q -r requirements.txt

# --- 6. Banco de dados -----------------------------------------------------
echo "[6/8] Conferindo o banco e criando as tabelas..."
.venv/bin/python scripts/testar_banco.py
export FLASK_APP=wsgi.py
if [ -d migrations ]; then
    .venv/bin/flask db upgrade
else
    echo "      Ainda nao ha migrations - nenhuma tabela a criar."
fi
if .venv/bin/flask --help 2>/dev/null | grep -qE '^\s+seed\b'; then
    .venv/bin/flask seed
fi

mkdir -p "${DIR}/instance/uploads"
chown -R "${USUARIO}:www-data" "${DIR}/instance"
chmod -R 2775 "${DIR}/instance"

# --- 7. Servico systemd ----------------------------------------------------
echo "[7/8] Registrando o servico ${SERVICO}..."
sudo mkdir -p /var/log/contatos
sudo chown "${USUARIO}:www-data" /var/log/contatos

sudo tee /etc/systemd/system/${SERVICO}.service >/dev/null <<UNIT
[Unit]
Description=Sistema Contatos - Fin
After=network.target

[Service]
User=${USUARIO}
Group=www-data
WorkingDirectory=${DIR}
Environment="FLASK_APP=wsgi.py"
ExecStart=${DIR}/.venv/bin/gunicorn \\
    --workers 3 \\
    --timeout 120 \\
    --bind unix:${DIR}/contatos.sock \\
    --umask 007 \\
    --access-logfile /var/log/contatos/access.log \\
    --error-logfile /var/log/contatos/error.log \\
    wsgi:app
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
UNIT

sudo systemctl daemon-reload
sudo systemctl enable ${SERVICO}
sudo systemctl restart ${SERVICO}

# --- 8. Nginx --------------------------------------------------------------
echo "[8/8] Publicando o site no nginx..."
# O HTTPS da Fin e encerrado antes deste servidor: o certificado de
# *.fin.org.br fica no proxy da infraestrutura, que repassa a requisicao em
# HTTP simples para ca. O "map" abaixo preserva o X-Forwarded-Proto original
# vindo desse proxy. O nome da variavel e exclusivo deste site porque o nginx
# compartilha os "map" entre todos os sites do servidor.
sudo tee /etc/nginx/sites-available/${SERVICO} >/dev/null <<NGINX
map \$http_x_forwarded_proto \$contatos_proto {
    default   \$scheme;
    "~^https?\$" \$http_x_forwarded_proto;
}

server {
    listen 80;
    server_name ${DOMINIO};

    client_max_body_size 30M;
    charset utf-8;

    location /static/ {
        alias ${DIR}/app/static/;
        expires 30d;
        access_log off;
    }

    location / {
        proxy_set_header Host \$http_host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$contatos_proto;
        proxy_redirect off;
        proxy_pass http://unix:${DIR}/contatos.sock;
    }

    access_log /var/log/nginx/contatos.access.log;
    error_log  /var/log/nginx/contatos.error.log;
}
NGINX

sudo ln -sf /etc/nginx/sites-available/${SERVICO} /etc/nginx/sites-enabled/${SERVICO}
if ! sudo nginx -t; then
    echo "      ERRO na configuracao do nginx. Removendo o site novo para"
    echo "      nao afetar o Portal de Eventos."
    sudo rm -f /etc/nginx/sites-enabled/${SERVICO}
    exit 1
fi
sudo systemctl reload nginx

# --- Conferencia -----------------------------------------------------------
sleep 2
echo
echo "=========================================================="
if systemctl is-active --quiet ${SERVICO}; then
    echo " SERVIDOR PREPARADO COM SUCESSO"
    echo
    echo " O sistema esta rodando para http://${DOMINIO}/"
    echo
    echo " PROXIMO PASSO: rode o ativar-producao.bat no seu computador."
else
    echo " ATENCAO: o servico nao subiu."
    echo
    systemctl status ${SERVICO} --no-pager -l | head -n 20
    exit 1
fi
echo "=========================================================="
