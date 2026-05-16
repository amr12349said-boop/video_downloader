import os, sys, json, re, time, threading, queue
from pathlib import Path

try:
    import yt_dlp
except ImportError:
    print("[!] yt-dlp not installed. Run: pip install yt-dlp")
    sys.exit(1)

DOWNLOAD_DIR = Path.home() / "Desktop" / "تجميل الفديوهات"
CONFIG_FILE = DOWNLOAD_DIR / "config_pro.json"
HISTORY_FILE = DOWNLOAD_DIR / "history.json"

DEFAULT_CONFIG = {
    "format": "best[ext=mp4]/best",
    "output_template": "%(title)s.%(ext)s",
    "subtitles": False,
    "playlist": False,
    "cookies": "",
    "proxy": "",
    "limit_speed": "",
    "concurrent": 1,
    "max_height": 1080,
}

def ensure_dirs():
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

def load_config():
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, encoding="utf-8") as f:
            return {**DEFAULT_CONFIG, **json.load(f)}
    return dict(DEFAULT_CONFIG)

def save_config(cfg):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)

def load_history():
    if HISTORY_FILE.exists():
        with open(HISTORY_FILE, encoding="utf-8") as f:
            return json.load(f)
    return []

def save_history(entry):
    history = load_history()
    history.insert(0, entry)
    if len(history) > 200:
        history = history[:200]
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

class DownloadTracker:
    def __init__(self):
        self._callbacks = {}

    def progress_hook(self, task_id=None):
        def hook(d):
            if d['status'] == 'downloading':
                total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
                downloaded = d.get('downloaded_bytes', 0)
                speed = d.get('speed', 0)
                pct = (downloaded / total * 100) if total else 0
                speed_str = f"{speed / 1024 / 1024:.1f} MB/s" if speed else "?"
                msg = f"\r  [{pct:5.1f}%] {downloaded/1024/1024:.1f}MB/{total/1024/1024:.1f}MB @ {speed_str}   "
                sys.stdout.write(msg)
                sys.stdout.flush()
                if task_id and task_id in self._callbacks:
                    self._callbacks[task_id]({
                        'percent': round(pct, 1),
                        'downloaded': downloaded,
                        'total': total,
                        'speed': speed,
                    })
            elif d['status'] == 'finished':
                print("\r  [100.0%] اكتمل التحميل، جارٍ الدمج...")
        return hook

    def register(self, task_id, callback):
        self._callbacks[task_id] = callback

    def unregister(self, task_id):
        self._callbacks.pop(task_id, None)

tracker = DownloadTracker()

def get_platform_dir(info):
    key = info.get('extractor_key', 'Unknown')
    safe = re.sub(r'[<>:"/\\|?*]', '_', key)
    path = DOWNLOAD_DIR / safe
    path.mkdir(exist_ok=True)
    return path

def clean_filename(title):
    return re.sub(r'[<>:"/\\|?*]', '_', title).strip()

def format_duration(secs):
    if not secs:
        return ''
    h, r = divmod(int(secs), 3600)
    m, s = divmod(r, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"

def format_size(bytes_):
    if not bytes_:
        return ''
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_ < 1024:
            return f"{bytes_:.1f} {unit}"
        bytes_ /= 1024
    return f"{bytes_:.1f} TB"

def download_video(url, format_id=None, task_id=None, progress_callback=None):
    cfg = load_config()
    fmt = format_id or cfg["format"]

    if progress_callback and task_id:
        tracker.register(task_id, progress_callback)

    try:
        with yt_dlp.YoutubeDL({'quiet': True, 'no_warnings': True}) as ydl:
            info = ydl.extract_info(url, download=False)

        platform_dir = get_platform_dir(info)
        title = info.get('title', 'video')
        safe_title = clean_filename(title)
        ext = 'mp4'
        output_template = str(platform_dir / f'{safe_title} [%(id)s].%(ext)s')

        opts = {
            'outtmpl': output_template,
            'format': fmt,
            'merge_output_format': 'mp4',
            'quiet': True,
            'no_warnings': True,
            'progress_hooks': [tracker.progress_hook(task_id)],
            'embed-metadata': True,
        }

        if cfg.get('subtitles'):
            opts.update({'writesubtitles': True, 'writeautomaticsub': True, 'subtitleslangs': ['en', 'ar', 'all']})
        if cfg.get('cookies'):
            opts['cookiefile'] = cfg['cookies']
        if cfg.get('proxy'):
            opts['proxy'] = cfg['proxy']
        if cfg.get('limit_speed'):
            opts['ratelimit'] = cfg['limit_speed']
        if not cfg.get('playlist'):
            opts['noplaylist'] = True

        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.extract_info(url, download=True)

        ext = 'mp4'
        actual_file = platform_dir / f'{safe_title} [{info.get("id", "unknown")}].{ext}'
        if not actual_file.exists():
            for f in platform_dir.iterdir():
                if safe_title in f.name and f.suffix in ('.mp4', '.webm', '.mkv', '.m4a'):
                    actual_file = f
                    ext = f.suffix.lstrip('.')
                    break

        entry = {
            'title': title,
            'url': url,
            'platform': info.get('extractor_key', 'Unknown'),
            'filename': actual_file.name,
            'path': str(actual_file),
            'size': format_size(actual_file.stat().st_size) if actual_file.exists() else '',
            'duration': format_duration(info.get('duration')),
            'format': fmt,
            'time': time.strftime('%Y-%m-%d %H:%M:%S'),
        }
        save_history(entry)

        if task_id:
            tracker.unregister(task_id)

        return {'success': True, 'file': str(actual_file), 'title': title, 'entry': entry}

    except Exception as e:
        if task_id:
            tracker.unregister(task_id)
        return {'success': False, 'error': str(e)}

def list_formats(url):
    try:
        with yt_dlp.YoutubeDL({'quiet': True, 'no_warnings': True}) as ydl:
            info = ydl.extract_info(url, download=False)
        print(f"\n{'='*60}")
        print(f"  {info.get('title', 'Video')}")
        print(f"  {info.get('extractor_key', 'Unknown')} | {format_duration(info.get('duration'))}")
        print(f"{'='*60}\n")
        print(f"{'CODE':<10} {'EXT':<8} {'RES':<12} {'SIZE':<10} {'NOTE':<20}")
        print(f"{'-'*60}")
        formats = info.get('formats', [])
        if not formats:
            print("  (no format info available)")
            return
        for f in formats:
            fid = f.get('format_id', '?')
            ext = f.get('ext', '?')
            height = f.get('height', '')
            width = f.get('width', '')
            res = f"{height}p" if height else ('audio' if f.get('vcodec') == 'none' else '?')
            size = format_size(f.get('filesize') or f.get('filesize_approx', 0))
            note = f.get('format_note', '')
            vcodec = f.get('vcodec', 'none')
            acodec = f.get('acodec', 'none')
            has_v = vcodec != 'none'
            has_a = acodec not in ('none', None)
            tag = ''
            if has_v and has_a: tag = 'VID+AUD'
            elif has_v: tag = 'VID'
            elif has_a: tag = 'AUD'
            print(f"{fid:<10} {ext:<8} {str(res):<12} {size:<10} {note:<20} {tag}")
        print()
    except Exception as e:
        print(f"Error: {e}")

def show_banner():
    print()
    print("  +========================================+")
    print("  |       Video Downloader Pro             |")
    print("  |     يدعم أكثر من 1000 منصة              |")
    print("  +========================================+")
    print(f"  حفظ في: {DOWNLOAD_DIR}")
    print()

def interactive_mode():
    ensure_dirs()
    show_banner()
    while True:
        print("\n--- القائمة الرئيسية ---")
        print("  1. تحميل فيديو")
        print("  2. تحميل بصوت فقط (MP3)")
        print("  3. تحميل قائمة تشغيل")
        print("  4. عرض الصيغ المتاحة")
        print("  5. الإعدادات")
        print("  6. عرض سجل التحميلات")
        print("  7. فتح مجلد التحميلات")
        print("  0. خروج")
        choice = input("\nاختيار: ").strip()

        if choice == '1':
            url = input("رابط الفيديو: ").strip()
            if url:
                r = download_video(url)
                if r['success']:
                    print(f"  [OK] تم التحميل: {r['file']}")
                else:
                    print(f"  [ERR] {r['error']}")
        elif choice == '2':
            url = input("رابط الفيديو: ").strip()
            if url:
                r = download_video(url, 'bestaudio[ext=m4a]/bestaudio')
                if r['success']:
                    print(f"  [OK] تم تحميل الصوت: {r['file']}")
                else:
                    print(f"  [ERR] {r['error']}")
        elif choice == '3':
            url = input("رابط القائمة: ").strip()
            if url:
                cfg = load_config()
                cfg['playlist'] = True
                save_config(cfg)
                r = download_video(url)
                cfg['playlist'] = False
                save_config(cfg)
                if r['success']:
                    print(f"  [OK] تم تحميل القائمة: {r['file']}")
                else:
                    print(f"  [ERR] {r['error']}")
        elif choice == '4':
            url = input("رابط الفيديو: ").strip()
            if url:
                list_formats(url)
        elif choice == '5':
            settings_menu()
        elif choice == '6':
            show_history()
        elif choice == '7':
            os.startfile(DOWNLOAD_DIR)
        elif choice == '0':
            print("مع السلامة!")
            break

def settings_menu():
    cfg = load_config()
    while True:
        print("\n--- الإعدادات ---")
        print(f"  1. الجودة: {cfg['format']}")
        print(f"  2. الدقة القصوى: {cfg.get('max_height', 1080)}p")
        print(f"  3. الترجمة: {'نعم' if cfg['subtitles'] else 'لا'}")
        print(f"  4. قائمة التشغيل: {'نعم' if cfg['playlist'] else 'لا'}")
        print(f"  5. ملف الكوكيز: {cfg.get('cookies') or 'غير مضبوط'}")
        print(f"  6. البروكسي: {cfg.get('proxy') or 'لا'}")
        print(f"  7. حد السرعة: {cfg.get('limit_speed') or 'لا'}")
        print(f"  0. رجوع")
        choice = input("\nاختيار: ").strip()

        if choice == '1':
            print("\nصيغ الجودة:")
            print("  1. أفضل جودة MP4 (م Recomended)")
            print("  2. 2160p (4K)")
            print("  3. 1080p (Full HD)")
            print("  4. 720p (HD)")
            print("  5. 480p")
            print("  6. 360p")
            print("  7. صوت فقط")
            print("  8. إدخال صيغة مخصصة")
            q = input("اختيار: ").strip()
            fmt_map = {
                '1': 'best[ext=mp4]/best',
                '2': 'bestvideo[height<=2160]+bestaudio/best[height<=2160]',
                '3': 'bestvideo[height<=1080]+bestaudio/best[height<=1080]',
                '4': 'bestvideo[height<=720]+bestaudio/best[height<=720]',
                '5': 'bestvideo[height<=480]+bestaudio/best[height<=480]',
                '6': 'bestvideo[height<=360]+bestaudio/best[height<=360]',
                '7': 'bestaudio[ext=m4a]/bestaudio',
            }
            if q in fmt_map:
                cfg['format'] = fmt_map[q]
            elif q == '8':
                cfg['format'] = input("أدخل صيغة yt-dlp: ").strip()
            save_config(cfg)
            print("تم الحفظ!")
        elif choice == '2':
            h = input("الدقة القصوى (مثال: 1080, 2160): ").strip()
            if h.isdigit():
                cfg['max_height'] = int(h)
                cfg['format'] = f'bestvideo[height<={h}]+bestaudio/best[height<={h}]'
                save_config(cfg)
                print("تم الحفظ!")
        elif choice in ('3', '4', '5', '6', '7'):
            key_map = {'3': 'subtitles', '4': 'playlist'}
            key_val = {'5': 'cookies', '6': 'proxy', '7': 'limit_speed'}
            if choice in key_map:
                cfg[key_map[choice]] = not cfg.get(key_map[choice], False)
            else:
                v = input(f"أدخل قيمة {key_val[choice]}: ").strip()
                cfg[key_val[choice]] = v
            save_config(cfg)
            print("تم الحفظ!")
        elif choice == '0':
            break

def show_history():
    history = load_history()
    if not history:
        print("\nلا توجد تحميلات سابقة")
        return
    print(f"\n--- آخر {len(history)} تحميل ---")
    for i, h in enumerate(history, 1):
        print(f"  {i}. [{h.get('platform','?')}] {h.get('title','?')}")
        print(f"     {h.get('time','')} | {h.get('size','')} | {h.get('format','')}")

def main():
    ensure_dirs()

    if len(sys.argv) < 2:
        interactive_mode()
        return

    arg = sys.argv[1]
    url = sys.argv[-1]

    show_banner()

    if arg in ('-h', '--help'):
        print("الاستخدام:")
        print(f"  python downloader_pro.py <URL>              التحميل بأفضل جودة")
        print(f"  python downloader_pro.py -f <URL>           عرض الصيغ المتاحة")
        print(f"  python downloader_pro.py -a <URL>           تحميل صوت فقط")
        print(f"  python downloader_pro.py -p <URL>           تحميل قائمة تشغيل")
        print(f"  python downloader_pro.py -s <URL>           مع ترجمة")
        print(f"  python downloader_pro.py -4k <URL>          تحميل 4K")
        print(f"  python downloader_pro.py -fmt <f> <URL>     صيغة محددة")
        print(f"  python downloader_pro.py --history          عرض سجل التحميلات")
        print(f"  python downloader_pro.py --config           فتح الإعدادات")
        return

    if arg == '--history':
        show_history()
        return

    if arg == '--config':
        settings_menu()
        return

    if arg == '-f':
        list_formats(url)
        return

    fmt_map = {
        '-a': 'bestaudio[ext=m4a]/bestaudio',
        '-4k': 'bestvideo[height<=2160]+bestaudio/best[height<=2160]',
        '-p': None,
        '-s': None,
    }

    fmt = fmt_map.get(arg)
    if arg == '-p':
        cfg = load_config()
        cfg['playlist'] = True
        save_config(cfg)
        r = download_video(url, 'best[ext=mp4]/best')
        cfg['playlist'] = False
        save_config(cfg)
    elif arg == '-s':
        cfg = load_config()
        cfg['subtitles'] = True
        save_config(cfg)
        r = download_video(url)
        cfg['subtitles'] = False
        save_config(cfg)
    elif arg == '-fmt' and len(sys.argv) >= 3:
        fmt = sys.argv[2]
        url = sys.argv[3] if len(sys.argv) > 3 else None
        if not url:
            print("Usage: -fmt <format_code> <URL>")
            return
        r = download_video(url, fmt)
    elif arg.startswith('http'):
        r = download_video(arg)
    elif fmt:
        r = download_video(url, fmt)
    else:
        r = download_video(url)

    if r and r.get('success'):
        print(f"\n  [OK] تم التحميل بنجاح!")
        print(f"  [FILE] {r['file']}")
    elif r:
        print(f"\n  [ERR] {r.get('error', 'فشل التحميل')}")

if __name__ == '__main__':
    main()
