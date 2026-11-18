@echo off
title Telegram Бот онлайн-записи (Ноготочки)
chcp 65001 > nul
echo ========================================================
echo   💅 ЗАПУСК TELEGRAM БОТА ОНЛАЙН-ЗАПИСИ
echo   (0 рублей, без серверов, работает напрямую через Telegram)
echo ========================================================
echo.
if exist venv\Scripts\python.exe (
    venv\Scripts\python.exe bot.py
) else (
    py bot.py
)
pause
