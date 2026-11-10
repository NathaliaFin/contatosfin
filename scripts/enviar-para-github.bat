@echo off
chcp 65001 >nul
title Enviar para o GitHub - Contatos Fin
cd /d "%~dp0.."

echo =========================================
git status --short
echo =========================================
echo.

REM Protecao: o .env guarda a senha do banco e nunca pode ir para o GitHub.
git ls-files --error-unmatch .env >nul 2>&1
if not errorlevel 1 (
    echo ==========================================================
    echo  PERIGO: o arquivo .env esta sendo versionado.
    echo.
    echo  Ele contem a senha do banco de dados e NAO pode ir para
    echo  o GitHub. Rode este comando para remove-lo do controle
    echo  de versao e depois tente de novo:
    echo.
    echo     git rm --cached .env
    echo ==========================================================
    pause
    exit /b 1
)

REM Se nao ha nada novo para gravar, apenas envia o que ja esta pendente.
set NOVIDADE=
for /f "delims=" %%i in ('git status --porcelain') do set NOVIDADE=1

if not defined NOVIDADE (
    echo Nenhum arquivo foi alterado desde o ultimo envio.
    echo Verificando se ha algo pendente para subir...
    echo.
    goto enviar
)

set /p mensagem="Descreva o que foi alterado: "

if "%mensagem%"=="" (
    echo.
    echo A descricao nao pode ficar em branco. Nada foi enviado.
    pause
    exit /b 1
)

git add .

REM Segunda protecao: confere de novo depois do "git add".
set SEGREDO=
for /f "delims=" %%i in ('git diff --cached --name-only -- .env "*.pem"') do set SEGREDO=1
if defined SEGREDO (
    git reset -q
    echo.
    echo ==========================================================
    echo  PERIGO: o .env ou uma chave .pem ia ser enviado.
    echo  Nada foi enviado. Confira o .gitignore e chame o suporte.
    echo ==========================================================
    pause
    exit /b 1
)

git commit -m "%mensagem%"
if errorlevel 1 (
    echo.
    echo Nada foi commitado.
    pause
    exit /b 1
)

:enviar
git push -u origin main
if errorlevel 1 goto erro

echo.
echo Pronto! Codigo enviado para o GitHub.
echo Agora rode o "3. atualizar-servidor.bat" para publicar no site.
pause
exit /b 0

:erro
echo.
echo ==========================================================
echo  O ENVIO PARA O GITHUB FALHOU
echo.
echo  O commit foi feito no seu computador, mas nao subiu.
echo ==========================================================
echo.

REM Distingue as duas causas comuns, em vez de culpar a conexao sempre.
git fetch origin >nul 2>&1
if errorlevel 1 (
    echo  CAUSA PROVAVEL: sem acesso ao GitHub.
    echo  Verifique sua conexao com a internet e rode de novo.
    echo.
    pause
    exit /b 1
)

set ATRASADO=
for /f "delims=" %%i in ('git log --oneline HEAD..origin/main 2^>nul') do set ATRASADO=1

if defined ATRASADO (
    echo  CAUSA: o GitHub tem alteracoes que voce ainda nao baixou.
    echo.
    echo  Isso acontece quando o codigo foi alterado em outro
    echo  computador, ou direto pelo site do GitHub.
    echo.
    echo  Para resolver, rode o "1. antes de comecar.bat" - ele
    echo  baixa o que falta - e depois rode este script de novo.
    echo.
    echo  NAO use "git push --force": isso apagaria do GitHub o
    echo  trabalho que esta la e nao esta aqui.
) else (
    echo  O GitHub esta acessivel e nao ha nada novo la.
    echo  Leia a mensagem de erro acima: ela diz o motivo.
)

echo ==========================================================
pause
exit /b 1
