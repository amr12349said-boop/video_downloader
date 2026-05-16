$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

$Host.UI.RawUI.WindowTitle = "Video Downloader Pro"

$VideosDir = Join-Path $env:USERPROFILE "Desktop\تجميل الفديوهات"
if (-not (Test-Path $VideosDir)) { New-Item -ItemType Directory -Path $VideosDir -Force | Out-Null }

Clear-Host
Write-Host "╔══════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║         Video Downloader Pro v2.0              ║" -ForegroundColor Yellow
Write-Host "║      أداة تحميل الفيديوهات من جميع المنصات      ║" -ForegroundColor Yellow
Write-Host "╚══════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

Write-Host " مسار الحفظ: " -ForegroundColor White -NoNewline
Write-Host "$VideosDir" -ForegroundColor Green
Write-Host ""

Write-Host " [1] تشغيل الواجهة الرسومية (Web UI)" -ForegroundColor Cyan
Write-Host " [2] تحميل فيديو (سطر أوامر)" -ForegroundColor Cyan
Write-Host " [3] تحميل متعدد (سطر أوامر)" -ForegroundColor Cyan
Write-Host " [4] فتح مجلد التحميلات" -ForegroundColor Cyan
Write-Host " [5] عرض إحصائيات المنصات" -ForegroundColor Cyan
Write-Host " [6] عرض سجل التحميلات" -ForegroundColor Cyan
Write-Host " [0] خروج" -ForegroundColor Gray
Write-Host ""

$choice = Read-Host "اختر رقم (0-6)"
Write-Host ""

switch ($choice) {
    "1" {
        Write-Host "جاري تشغيل الخادم..." -ForegroundColor Yellow
        Write-Host "افتح المتصفح: http://localhost:5000" -ForegroundColor Green
        Write-Host "اضغط Ctrl+C للإيقاف" -ForegroundColor Gray
        Write-Host ""
        python "$ScriptDir/app.py"
    }
    "2" {
        $url = Read-Host "أدخل رابط الفيديو"
        if ([string]::IsNullOrWhiteSpace($url)) { Write-Host "خطأ: لم يتم إدخال رابط" -ForegroundColor Red; exit 1 }
        $fmt = Read-Host "اختر الجودة [Enter=أفضل جودة]" 
        if ([string]::IsNullOrWhiteSpace($fmt)) { $fmt = "best[ext=mp4]/best" }

        Write-Host "جاري التحميل..." -ForegroundColor Yellow
        python -c @"
import sys, os
sys.path.insert(0, r'$ScriptDir')
from downloader_pro import download_video, show_banner, DOWNLOAD_DIR
show_banner()
r = download_video('$url', '$fmt')
if r.get('success'):
    print(f'[OK] تم التحميل: {r[\"file\"]}')
else:
    print(f'[ERR] {r.get(\"error\", \"فشل\")}')
"@ 2>&1

        if ($LASTEXITCODE -eq 0) {
            Write-Host "`nتم التحميل بنجاح!" -ForegroundColor Green
        } else {
            Write-Host "`nفشل التحميل" -ForegroundColor Red
        }
    }
    "3" {
        Write-Host "الصق الروابط (واحد في كل سطر، اضغط Enter مرتين للإنهاء):" -ForegroundColor Cyan
        $urls = @()
        while ($true) {
            $line = Read-Host
            if ([string]::IsNullOrWhiteSpace($line)) { break }
            $urls += $line.Trim()
        }
        if ($urls.Count -eq 0) { Write-Host "لا توجد روابط" -ForegroundColor Red; break }

        Write-Host "جاري تحميل $($urls.Count) فيديو..." -ForegroundColor Yellow
        foreach ($url in $urls) {
            Write-Host "`n[$($urls.IndexOf($url)+1)/$($urls.Count)] $url" -ForegroundColor Cyan
            python -c @"
import sys
sys.path.insert(0, r'$ScriptDir')
from downloader_pro import download_video
r = download_video('$url', 'best[ext=mp4]/best')
if r.get('success'):
    print(f'[OK] {r[\"title\"]}')
else:
    print(f'[ERR] {r.get(\"error\", \"فشل\")}')
"@ 2>&1
        }
        Write-Host "`nاكتمل التحميل المتعدد!" -ForegroundColor Green
    }
    "4" {
        if (Test-Path $VideosDir) { Invoke-Item $VideosDir; Write-Host "تم فتح المجلد" -ForegroundColor Green }
        else { Write-Host "المجلد غير موجود" -ForegroundColor Yellow }
    }
    "5" {
        if (Test-Path $VideosDir) {
            $dirs = Get-ChildItem -Directory $VideosDir
            $total = 0
            Write-Host "المنصات:" -ForegroundColor Cyan
            Write-Host ("-" * 40) -ForegroundColor Gray
            foreach ($d in $dirs) {
                $count = (Get-ChildItem -File $d.FullName).Count
                $size = "{0:N2} MB" -f ((Get-ChildItem -File $d.FullName | Measure-Object Length -Sum).Sum / 1MB)
                $total += $count
                Write-Host (" {0,-25} {1,4} فيديو  {2,8}" -f $d.Name, $count, $size) -ForegroundColor White
            }
            Write-Host ("-" * 40) -ForegroundColor Gray
            Write-Host (" المجموع: {0,20} فيديو" -f $total) -ForegroundColor Yellow
        } else {
            Write-Host "لا توجد تحميلات" -ForegroundColor Yellow
        }
    }
    "6" {
        python -c @"
import sys, json
sys.path.insert(0, r'$ScriptDir')
from downloader_pro import load_history, HISTORY_FILE
history = load_history()
if not history:
    print('لا توجد تحميلات سابقة')
else:
    print(f'آخر {len(history)} تحميل:')
    print('-' * 60)
    for i, h in enumerate(history[:20], 1):
        print(f'{i}. [{h.get(\"platform\",\"?\")}] {h.get(\"title\",\"?\")}')
        print(f'   {h.get(\"time\",\"\")} | {h.get(\"size\",\"\")} | {h.get(\"format\",\"\")}')
"@ 2>&1
    }
    "0" { Write-Host "مع السلامة!" -ForegroundColor Yellow }
    default { Write-Host "اختيار غير صحيح" -ForegroundColor Red }
}

Write-Host ""
Read-Host "اضغط Enter للخروج"
