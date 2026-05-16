@echo off
chcp 65001 >nul
title Video Downloader Pro
cd /d "%~dp0"
echo ========================================
echo   Video Downloader Pro v2.0
echo   أداة تحميل الفيديوهات من جميع المنصات
echo ========================================
echo.
powershell -ExecutionPolicy Bypass -File "%~dp0run.ps1"
pause
