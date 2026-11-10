#!/bin/bash
# ===========================================================================
#  Ativa o modo de producao - Contatos Fin
#
#  Chamado pelo ativar-producao.bat. Nao precisa ser executado a mao.
#
#  IMPORTANTE: nao ha certbot aqui, e isso e proposital. Na Fin o certificado
#  de *.fin.org.br fica no proxy da infraestrutura, que encerra o HTTPS e
#  repassa a requisicao em HTTP simples para este servidor.
# ===========================================================================
set -euo pipefail

DIR=/var/www/contatos
SERVICO=contatos
DOMINIO=contatos.fin.org.br

echo "=========================================================="
echo " ATIVANDO O MODO DE PRODUCAO"
echo "=========================================================="

# --- 1. Confere se o HTTPS do proxy ja chega a este sistema ---------------
echo
echo "[1/3] Conferindo se https://${DOMINIO}/ chega a este servidor..."
CODIGO=$(curl -s -o /dev/null -w '%{http_code}' --max-time 20 "https://${DOMINIO}/" || true)
DESTINO=$(curl -s -o /dev/null -w '%{redirect_url}' --max-time 20 "https://${DOMINIO}/" || true)
if [ -z "${CODIGO}" ] || [ "${CODIGO}" = "000" ] || [ "${CODIGO}" = "400" ] \
   || [ "${CODIGO}" = "502" ] || [ "${CODIGO}" = "503" ] || [ "${CODIGO}" = "504" ] \
   || echo "${DESTINO}" | grep -q '^https://fin.org.br'; then
    echo
    echo "  ERRO: https://${DOMINIO}/ respondeu HTTP ${CODIGO:-000} ${DESTINO}"
    echo "  HTTP 400 costuma significar que o site do Contatos nao esta"
    echo "  ativo no nginx (quem responde e o Portal de Eventos): rode"
    echo "  antes o preparar-servidor.bat. Outros codigos: confira com a"
    echo "  infraestrutura se ${DOMINIO} chega a 172.16.0.12, porta 80."
    echo
    echo "  Sem HTTPS o modo de producao deixaria o login inacessivel,"
    echo "  porque os cookies de sessao passam a exigir conexao segura."
    echo "  Nada foi alterado."
    exit 1
fi
echo "      https://${DOMINIO}/ respondeu HTTP ${CODIGO}. HTTPS ativo."

# --- 2. Passa a aplicacao para producao ------------------------------------
echo "[2/3] Passando a aplicacao para o modo de producao..."
cd "${DIR}"
# O backup guarda a senha do banco: nasce com a mesma restricao do original.
BACKUP=".env.backup-$(date +%Y%m%d-%H%M%S)"
cp .env "${BACKUP}"
chmod 600 "${BACKUP}"
sed -i 's|^FLASK_ENV=.*|FLASK_ENV=production|' .env
grep -q '^FLASK_ENV=production' .env || { echo "  ERRO: nao consegui alterar o .env"; exit 1; }

sudo systemctl restart ${SERVICO}
sleep 3

# --- 3. Conferencia final --------------------------------------------------
echo "[3/3] Conferindo..."
if ! systemctl is-active --quiet ${SERVICO}; then
    echo
    echo "  ERRO: o sistema nao subiu. Desfazendo..."
    cp "${BACKUP}" .env
    sudo systemctl restart ${SERVICO}
    echo "  Modo anterior restaurado. Veja o motivo:"
    sudo journalctl -u ${SERVICO} -n 30 --no-pager
    exit 1
fi

CODIGO=$(curl -s -o /dev/null -w '%{http_code}' --max-time 20 "https://${DOMINIO}/auth/login" || echo "000")
echo
echo "=========================================================="
if [ "${CODIGO}" = "200" ]; then
    echo " MODO DE PRODUCAO ATIVO"
    echo
    echo " A tela de login respondeu HTTP 200 em"
    echo " https://${DOMINIO}/auth/login"
    echo
    echo " Entre como administrador e troque a senha inicial."
else
    echo " ATENCAO: a tela de login respondeu HTTP ${CODIGO}."
    echo " O servico esta rodando, mas confira o site no navegador."
fi
echo "=========================================================="
