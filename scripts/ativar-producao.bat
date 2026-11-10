@echo off
chcp 65001 >nul
title Ativar modo de producao - Contatos Fin
cd /d "%~dp0.."

set "KEY=%~dp0..\..\SRVWEB-HUBRI_KEY.pem"
set "SRV=azureuser@172.16.0.12"

echo ==========================================================
echo  ATIVAR O MODO DE PRODUCAO - RODA UMA VEZ SO
echo ==========================================================
echo.
echo  Passa o sistema para o modo de producao: desliga as
echo  mensagens tecnicas de erro e exige conexao segura nos
echo  cookies de sessao.
echo.
echo  NAO emite certificado. Na Fin o HTTPS e resolvido pelo
echo  proxy da infraestrutura. O script confere se
echo  https://contatos.fin.org.br/ ja chega ao sistema antes
echo  de mudar qualquer coisa.
echo.
echo  Se algo der errado, ele volta sozinho ao modo anterior.
echo.
echo ==========================================================
echo.

if not exist "%KEY%" (
    echo ERRO: chave SSH nao encontrada em:
    echo    %KEY%
    pause
    exit /b 1
)

set /p confirma="Digite ATIVAR para continuar: "
if /i not "%confirma%"=="ATIVAR" (
    echo.
    echo Cancelado. Nada foi alterado.
    pause
    exit /b 1
)

echo.
echo Enviando o script de ativacao...
scp -i "%KEY%" "scripts\ativar-producao.sh" %SRV%:/tmp/ativar-producao.sh
if errorlevel 1 goto erro

echo.
ssh -i "%KEY%" %SRV% "chmod +x /tmp/ativar-producao.sh && bash /tmp/ativar-producao.sh; RESULTADO=$?; rm -f /tmp/ativar-producao.sh; exit $RESULTADO"
if errorlevel 1 goto erro

echo.
pause
exit /b 0

:erro
echo.
echo ==========================================================
echo  A ATIVACAO NAO FOI CONCLUIDA
echo.
echo  Leia a mensagem acima: ela diz exatamente em que ponto
echo  parou. O sistema continua no ar no modo anterior.
echo.
echo  Se precisar de mais detalhes, rode:
echo     scripts\ver-log-servidor.bat
echo ==========================================================
pause
exit /b 1
