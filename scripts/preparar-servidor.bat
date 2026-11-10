@echo off
chcp 65001 >nul
title Preparar servidor (primeira vez) - Contatos Fin
cd /d "%~dp0.."

set "KEY=%~dp0..\..\SRVWEB-HUBRI_KEY.pem"
set "SRV=azureuser@172.16.0.12"
set "PACOTE=%TEMP%\contatos-deploy.tar"

echo ==========================================================
echo  PREPARAR O SERVIDOR - RODA UMA VEZ SO
echo ==========================================================
echo.
echo  Este script instala o sistema do zero no servidor
echo  SRVAPP01 (172.16.0.12) e publica em
echo  http://contatos.fin.org.br/
echo.
echo  Ele instala: o ambiente virtual Python, o servico do
echo  sistema, o site no nginx e cria as tabelas do banco.
echo.
echo  NAO mexe no Portal de Eventos nem em nenhum outro site
echo  que ja esteja no servidor.
echo.
echo  Depois desta primeira vez, use sempre o
echo  "3. atualizar-servidor.bat" para publicar alteracoes.
echo.
echo ==========================================================
echo.

if not exist "%KEY%" (
    echo ERRO: chave SSH nao encontrada em:
    echo    %KEY%
    echo.
    echo Coloque o SRVWEB-HUBRI_KEY.pem na pasta Documentos.
    pause
    exit /b 1
)

if not exist ".env" (
    echo ERRO: o arquivo .env nao foi encontrado.
    echo.
    echo Ele guarda a senha do banco e e obrigatorio.
    pause
    exit /b 1
)

if not exist "wsgi.py" (
    echo ERRO: o sistema ainda nao tem o arquivo wsgi.py.
    echo.
    echo Rode este script so depois que as telas estiverem prontas
    echo e enviadas para o GitHub.
    pause
    exit /b 1
)

set /p confirma="Digite PREPARAR para continuar: "
if /i not "%confirma%"=="PREPARAR" (
    echo.
    echo Cancelado. Nada foi feito no servidor.
    pause
    exit /b 1
)

echo.
echo [1/4] Empacotando os arquivos do sistema...
git archive --format=tar -o "%PACOTE%" HEAD
if errorlevel 1 (
    echo.
    echo ERRO ao empacotar. Voce ja fez o primeiro commit no git?
    echo Rode antes o enviar-para-github.bat
    pause
    exit /b 1
)

echo [2/4] Enviando os arquivos para o servidor...
scp -i "%KEY%" "%PACOTE%" %SRV%:/tmp/contatos-deploy.tar
if errorlevel 1 goto erro

echo [3/4] Enviando a configuracao...
scp -i "%KEY%" ".env" %SRV%:/tmp/contatos.env
if errorlevel 1 goto erro
scp -i "%KEY%" "scripts\preparar-servidor.sh" %SRV%:/tmp/preparar-servidor.sh
if errorlevel 1 goto erro

echo [4/4] Instalando no servidor. Isso demora alguns minutos...
echo.
ssh -i "%KEY%" %SRV% "chmod +x /tmp/preparar-servidor.sh && bash /tmp/preparar-servidor.sh; RESULTADO=$?; rm -f /tmp/preparar-servidor.sh /tmp/contatos.env; exit $RESULTADO"
if errorlevel 1 goto erro

del "%PACOTE%" >nul 2>&1

echo.
echo ==========================================================
echo  PROXIMO PASSO: rode o ativar-producao.bat
echo ==========================================================
pause
exit /b 0

:erro
del "%PACOTE%" >nul 2>&1
echo.
echo ==========================================================
echo  A PREPARACAO FALHOU
echo.
echo  Verifique se voce esta na rede interna da FIN (VPN).
echo  Veja a mensagem de erro acima para saber em que ponto
echo  parou. E seguro rodar este script novamente.
echo ==========================================================
pause
exit /b 1
