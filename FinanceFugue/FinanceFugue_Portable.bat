@echo off
chcp 65001 > nul
title FinanceFugue Portable Runner

echo ========================================================
echo   FinanceFugue - Fast Portable Launcher (Zero Build)
echo ========================================================
echo.

cd /d "%~dp0"
set PYTHONPATH=%~dp0

echo [INFO] Запуск FinanceFugue из исходников (мгновенный старт)...
start "" pythonw "%~dp0main_pyside.py"

if errorlevel 1 (
    echo [ERROR] pythonw не найден или завершился с ошибкой. Пробуем через python...
    python "%~dp0main_pyside.py"
    pause
)
