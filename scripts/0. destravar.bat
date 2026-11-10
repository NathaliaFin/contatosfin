@echo off
chcp 65001 >nul
title Destravar o download - Contatos Fin
cd /d "%~dp0.."

echo ==========================================================
echo  DESTRAVAR O DOWNLOAD DO CODIGO
echo ==========================================================
echo.
echo Use este script SOMENTE quando o "1. antes de comecar.bat"
echo reclamar de arquivos alterados nesta maquina.
echo.
echo Isso costuma acontecer porque o OneDrive copia os arquivos
echo editados no notebook para ca antes do Git trazer o commit.
echo Para o Git daqui, parece que alguem mexeu nos arquivos.
echo.
echo NADA E APAGADO: o que for guardado continua recuperavel
echo pelo comando "git stash list".
echo.
echo Arquivos alterados nesta pasta agora:
echo ----------------------------------------------------------
git status --short
echo ----------------------------------------------------------
echo.

set "RESP="
set /p "RESP=Digite S e tecle Enter para continuar: "
if /i not "%RESP%"=="S" (
    echo.
    echo Cancelado. Nada foi alterado.
    pause
    exit /b 1
)

echo.
echo [1/3] Guardando de lado as alteracoes locais...
git stash push -m "destravar automatico"
if errorlevel 1 goto erro_stash

echo.
echo [2/3] Baixando a versao do GitHub...
git pull origin main
if errorlevel 1 goto erro_pull

echo.
echo [3/3] Conferindo...
for /f "delims=" %%i in ('git rev-parse HEAD') do set "LOCAL=%%i"
for /f "delims=" %%i in ('git rev-parse origin/main') do set "REMOTO=%%i"
if not "%LOCAL%"=="%REMOTO%" goto erro_versao

echo.
echo ==========================================================
echo  PRONTO - esta pasta esta igual ao GitHub
echo.
echo  Agora rode o "3. atualizar-servidor.bat" para publicar.
echo ==========================================================
pause
exit /b 0

:erro_stash
echo.
echo ==========================================================
echo  NAO FOI POSSIVEL GUARDAR AS ALTERACOES
echo.
echo  Nada foi alterado. Chame o suporte tecnico e mostre a
echo  mensagem acima.
echo ==========================================================
pause
exit /b 1

:erro_pull
echo.
echo ==========================================================
echo  O DOWNLOAD FALHOU MESMO DEPOIS DE DESTRAVAR
echo.
echo  Suas alteracoes foram guardadas e estao a salvo. Para
echo  traze-las de volta, rode:  git stash pop
echo.
echo  Chame o suporte tecnico e mostre a mensagem acima.
echo ==========================================================
pause
exit /b 1

:erro_versao
echo.
echo ==========================================================
echo  A PASTA AINDA NAO FICOU IGUAL AO GITHUB
echo.
echo  Local  : %LOCAL%
echo  GitHub : %REMOTO%
echo.
echo  NAO publique. Chame o suporte tecnico.
echo ==========================================================
pause
exit /b 1
