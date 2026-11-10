@echo off
chcp 65001 >nul
title Rodar no meu computador - Contatos Fin
cd /d "%~dp0.."

echo ==========================================================
echo  RODAR O SISTEMA NO SEU COMPUTADOR
echo ==========================================================
echo.
echo  Abre uma copia de teste em http://127.0.0.1:5000
echo.
echo  Usa um banco de teste proprio (SQLite), com dados de
echo  demonstracao. NAO mexe no banco de producao do Azure.
echo.
echo  Usuarios de teste - a senha de todos e Fin@2026:
echo     admin@fin.org.br     Administrador
echo     gestor@fin.org.br    Gestor de dados
echo     usuario@fin.org.br   Usuario
echo.
echo  Os e-mails nao sao enviados: ficam em instance\emails-nao-enviados.log
echo.
echo  Para parar, feche esta janela ou aperte Ctrl+C.
echo ==========================================================
echo.

if not exist "preview_local.py" (
    echo O sistema ainda nao tem a copia de teste local
    echo ^(preview_local.py^). Ela sera criada junto com as telas.
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo Ambiente Python nao encontrado. Criando agora...
    python -m venv .venv
    .venv\Scripts\python.exe -m pip install -q -r requirements.txt
)

.venv\Scripts\python.exe preview_local.py

echo.
echo Servidor encerrado.
pause
