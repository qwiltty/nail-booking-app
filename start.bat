@echo off
title Сервер онлайн-записи (Ноготочки)
chcp 65001 > nul
echo ========================================================
echo   💅 ЗАПУСК СИСТЕМЫ ОНЛАЙН-ЗАПИСИ ДЛЯ МАСТЕРА МАНИКЮРА
echo ========================================================
echo.
if exist venv\Scripts\python.exe (
    venv\Scripts\python.exe run.py
) else (
    py run.py
)
pause
