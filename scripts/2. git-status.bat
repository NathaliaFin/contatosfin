@echo off
chcp 65001 >nul
title Status - Contatos Fin
cd /d "%~dp0.."
git status
pause
