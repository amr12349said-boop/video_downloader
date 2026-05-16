@echo off
cd /d "%~dp0"
echo يتم اغلاق Chrome...
taskkill /f /im chrome.exe >nul 2>nul
timeout /t 2 /nobreak >nul
echo جاري استخراج الكوكيز من Chrome...
python -m yt_dlp --cookies-from-browser chrome --cookies cookies.txt --skip-download "https://www.youtube.com" 2>&1
echo.
if exist cookies.txt (
    echo تم استخراج الكوكيز بنجاح!
    findstr /c:".youtube.com" cookies.txt >nul && echo تم العثور على كوكيز YouTube
) else (
    echo فشل استخراج الكوكيز
)
echo.
pause
