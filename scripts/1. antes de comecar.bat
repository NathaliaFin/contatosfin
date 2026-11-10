@echo off
chcp 65001 >nul
title Antes de comecar - Contatos Fin
cd /d "%~dp0.."

echo =========================================
echo Pasta atual:
cd
echo =========================================
echo Baixando a versao mais recente do codigo...
echo =========================================

git pull origin main
if errorlevel 1 goto erro_pull

echo.
echo =========================================
echo Conferindo se ficou igual ao GitHub...
echo =========================================

for /f "delims=" %%i in ('git rev-parse HEAD') do set "LOCAL=%%i"
for /f "delims=" %%i in ('git rev-parse origin/main') do set "REMOTO=%%i"
if not "%LOCAL%"=="%REMOTO%" goto erro_versao

echo Tudo certo: esta pasta esta na mesma versao do GitHub.

echo.
echo =========================================
echo Verificando se ha dependencias novas...
echo =========================================

if not exist ".venv\Scripts\python.exe" (
    echo Ambiente Python nao encontrado. Criando agora...
    python -m venv .venv
)

.venv\Scripts\python.exe -m pip install -q -r requirements.txt
if errorlevel 1 goto erro_pip

echo.
echo =========================================
echo Processo finalizado
echo =========================================
pause
exit /b 0

:erro_pull
echo.
echo ==========================================================
echo  O DOWNLOAD DO CODIGO FALHOU
echo.
echo  LEIA A MENSAGEM DO GIT LOGO ACIMA - ela diz o motivo.
echo.
echo  NAO adianta publicar agora: esta pasta continua com a
echo  versao antiga, e o site receberia o codigo velho.
echo.
echo  Motivo mais comum: algum arquivo foi alterado aqui na
echo  maquina e o Git nao quer sobrescrever. Nesse caso rode o
echo  "0. destravar.bat".
echo ==========================================================
pause
exit /b 1

:erro_versao
echo.
echo ==========================================================
echo  ESTA PASTA NAO FICOU IGUAL AO GITHUB
echo.
echo  Local  : %LOCAL%
echo  GitHub : %REMOTO%
echo.
echo  O download rodou sem erro, mas a versao continua diferente
echo  - normalmente porque existem commits feitos aqui que nunca
echo  foram enviados. Rode o "enviar-para-github.bat".
echo ==========================================================
pause
exit /b 1

:erro_pip
echo.
echo ==========================================================
echo  FALHA AO INSTALAR AS DEPENDENCIAS
echo.
echo  O codigo foi baixado, mas as bibliotecas nao. Veja a
echo  mensagem acima antes de continuar.
echo ==========================================================
pause
exit /b 1
