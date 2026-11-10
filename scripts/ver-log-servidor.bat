@echo off
chcp 65001 >nul
title Ver log do servidor - Contatos Fin
cd /d "%~dp0.."

set "KEY=%~dp0..\..\SRVWEB-HUBRI_KEY.pem"
set "SRV=azureuser@172.16.0.12"
set "SERVICO=contatos"

if not exist "%KEY%" (
    echo ERRO: chave SSH nao encontrada em:
    echo    %KEY%
    pause
    exit /b 1
)

echo ==========================================================
echo  SITUACAO DO SISTEMA NO SERVIDOR
echo ==========================================================
echo.

ssh -i "%KEY%" %SRV% "systemctl status %SERVICO% --no-pager -l | head -n 20"

echo.
echo ==========================================================
echo  ULTIMAS 40 LINHAS DO SERVICO
echo ==========================================================
echo.

ssh -i "%KEY%" %SRV% "sudo journalctl -u %SERVICO% -n 40 --no-pager"

echo.
echo ==========================================================
echo  ULTIMAS 30 LINHAS DE ERRO DA APLICACAO
echo ==========================================================
echo.

ssh -i "%KEY%" %SRV% "tail -n 30 /var/log/contatos/error.log 2>/dev/null || echo '(sem arquivo de erro ainda)'"

echo.
echo ==========================================================
echo  Copie a mensagem acima ao pedir ajuda ao suporte.
echo ==========================================================
pause
