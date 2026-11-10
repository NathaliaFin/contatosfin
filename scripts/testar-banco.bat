@echo off
chcp 65001 >nul
title Testar o banco de dados - Contatos Fin
cd /d "%~dp0.."

echo ==========================================================
echo  TESTAR A CONEXAO COM O BANCO DE DADOS
echo ==========================================================
echo.
echo  Le a senha do arquivo .env e tenta conectar no MySQL
echo  do Azure. A senha nunca aparece na tela.
echo.

if not exist ".env" (
    echo ERRO: o arquivo .env nao foi encontrado nesta pasta.
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo Ambiente Python nao encontrado. Criando agora...
    python -m venv .venv
    .venv\Scripts\python.exe -m pip install -q -r requirements.txt
    if errorlevel 1 (
        echo Falha ao instalar as dependencias. Veja a mensagem acima.
        pause
        exit /b 1
    )
)

.venv\Scripts\python.exe scripts\testar_banco.py

echo.
pause
