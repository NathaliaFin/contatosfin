@echo off
chcp 65001 >nul
title Atualizar servidor - Contatos Fin
cd /d "%~dp0.."

set "KEY=%~dp0..\..\SRVWEB-HUBRI_KEY.pem"
set "SRV=azureuser@172.16.0.12"
set "DIR=/var/www/contatos"
set "SERVICO=contatos"
set "PACOTE=%TEMP%\contatos-deploy.tar"

echo ==========================================================
echo  PUBLICAR NO SITE
echo  https://contatos.fin.org.br/
echo ==========================================================
echo.

if not exist "%KEY%" (
    echo ERRO: chave SSH nao encontrada em:
    echo    %KEY%
    echo.
    echo Coloque o SRVWEB-HUBRI_KEY.pem na pasta Documentos.
    echo.
    pause
    exit /b 1
)

echo Conferindo se o codigo local esta atualizado...
git fetch origin main >nul 2>&1
if errorlevel 1 goto erro_fetch

for /f "delims=" %%i in ('git rev-parse HEAD') do set "LOCAL=%%i"
for /f "delims=" %%i in ('git rev-parse origin/main') do set "REMOTO=%%i"
if not "%LOCAL%"=="%REMOTO%" goto erro_atrasado

echo Versao conferida: identica a do GitHub.
echo.

set PENDENTE=
for /f "delims=" %%i in ('git status --porcelain') do set PENDENTE=1
if defined PENDENTE (
    echo ATENCAO: existem alteracoes ainda nao commitadas.
    echo Somente o que ja foi commitado sera publicado.
    echo.
    echo Se quiser publicar as alteracoes novas, feche esta janela
    echo e rode primeiro o enviar-para-github.bat
    echo.
    pause
)

echo [1/5] Empacotando os arquivos do sistema...
git archive --format=tar -o "%PACOTE%" HEAD
if errorlevel 1 goto erro

echo [2/5] Enviando para o servidor...
scp -i "%KEY%" "%PACOTE%" %SRV%:/tmp/contatos-deploy.tar
if errorlevel 1 goto erro

echo [3/5] Instalando os arquivos...
ssh -i "%KEY%" %SRV% "tar -xf /tmp/contatos-deploy.tar -C %DIR% && rm -f /tmp/contatos-deploy.tar"
if errorlevel 1 goto erro

echo [4/5] Atualizando dependencias e banco de dados...
ssh -i "%KEY%" %SRV% "cd %DIR% && .venv/bin/pip install -q -r requirements.txt && if [ -d migrations ]; then FLASK_APP=wsgi.py .venv/bin/flask db upgrade; fi"
if errorlevel 1 goto erro_banco

echo [5/5] Reiniciando o sistema...
ssh -i "%KEY%" %SRV% "sudo systemctl restart %SERVICO% && sleep 2 && systemctl is-active %SERVICO%"
if errorlevel 1 goto erro_servico

del "%PACOTE%" >nul 2>&1

echo.
echo ==========================================================
echo  PUBLICADO COM SUCESSO
echo.
echo  Confira em https://contatos.fin.org.br/
echo  Se a pagina parecer igual, use Ctrl+Shift+R no navegador.
echo ==========================================================
pause
exit /b 0

:erro_fetch
echo.
echo ==========================================================
echo  NAO FOI POSSIVEL CONFERIR A VERSAO NO GITHUB
echo.
echo  A publicacao foi cancelada por seguranca, para nao mandar
echo  codigo velho para o site sem querer.
echo.
echo  Verifique a conexao com a internet e tente de novo.
echo ==========================================================
pause
exit /b 1

:erro_atrasado
echo.
echo ==========================================================
echo  PUBLICACAO CANCELADA - CODIGO LOCAL DIFERENTE DO GITHUB
echo.
echo  Esta pasta NAO esta na mesma versao do GitHub.
echo.
echo  Local  : %LOCAL%
echo  GitHub : %REMOTO%
echo.
echo  Se voce fez commits que ainda nao subiram, rode o
echo  "enviar-para-github.bat". Se o GitHub tem algo novo,
echo  rode o "1. antes de comecar.bat". Depois tente de novo.
echo ==========================================================
pause
exit /b 1

:erro
del "%PACOTE%" >nul 2>&1
echo.
echo ==========================================================
echo  A PUBLICACAO FALHOU
echo.
echo  O site continua no ar com a versao anterior.
echo  Verifique se voce esta na rede interna da FIN (VPN) e
echo  tente novamente. Se persistir, veja a mensagem acima.
echo ==========================================================
pause
exit /b 1

:erro_banco
del "%PACOTE%" >nul 2>&1
echo.
echo ==========================================================
echo  FALHA AO ATUALIZAR DEPENDENCIAS OU BANCO
echo.
echo  Os arquivos novos ja foram enviados, mas o sistema NAO
echo  foi reiniciado - ele continua rodando a versao anterior
echo  em memoria.
echo.
echo  NAO reinicie o servico ate resolver. Chame o suporte
echo  tecnico e mostre a mensagem de erro acima.
echo ==========================================================
pause
exit /b 1

:erro_servico
del "%PACOTE%" >nul 2>&1
echo.
echo ==========================================================
echo  O SISTEMA NAO SUBIU APOS O REINICIO
echo.
echo  O site pode estar fora do ar. Para ver o motivo, rode:
echo.
echo     scripts\ver-log-servidor.bat
echo ==========================================================
pause
exit /b 1
