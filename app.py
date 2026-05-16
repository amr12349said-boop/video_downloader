import os, re, uuid, json, time, threading, queue
from pathlib import Path
import yt_dlp
from flask import Flask, render_template, request, jsonify, send_from_directory, session

app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24).hex()

BASE_DIR = Path.home() / "Desktop" / "تجميل الفديوهات"
if not (Path.home() / "Desktop").exists():
    BASE_DIR = Path(__file__).parent / "downloads"
BASE_DIR.mkdir(exist_ok=True)
CONFIG_FILE = BASE_DIR / "config_web.json"
HISTORY_FILE = BASE_DIR / "history_web.json"
STATUS_DIR = BASE_DIR / ".status"
STATUS_DIR.mkdir(exist_ok=True)

DEFAULT_CONFIG = {
    "format": "best[ext=mp4]/best",
    "subtitles": False,
    "playlist": False,
    "cookies_file": "",
    "proxy": "",
    "limit_speed": "",
    "max_height": 1080,
    "auto_cleanup_minutes": 30,
    "output_template": "%(title)s.%(ext)s",
}

download_queue = queue.Queue()
active_downloads = {}
download_progress = {}

def get_config():
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, encoding="utf-8") as f:
            return {**DEFAULT_CONFIG, **json.load(f)}
    return dict(DEFAULT_CONFIG)

def save_config(cfg):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)

def get_history():
    if HISTORY_FILE.exists():
        with open(HISTORY_FILE, encoding="utf-8") as f:
            return json.load(f)
    return []

def add_history(entry):
    history = get_history()
    history.insert(0, entry)
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

def get_platform_dir(extractor_key):
    safe = re.sub(r'[<>:"/\\|?*]', '_', extractor_key or 'Unknown')
    path = BASE_DIR / safe
    path.mkdir(exist_ok=True)
    return path

def clean_filename(s):
    return re.sub(r'[<>:"/\\|?*]', '_', s).strip()

def format_size(bytes_):
    if not bytes_:
        return ''
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_ < 1024:
            return f"{bytes_:.1f}{unit}"
        bytes_ /= 1024
    return f"{bytes_:.1f}TB"

def format_duration(secs):
    if not secs:
        return ''
    h, r = divmod(int(secs), 3600)
    m, s = divmod(r, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"

def status_file(task_id):
    return STATUS_DIR / f"{task_id}.json"

def write_status(task_id, data):
    with open(status_file(task_id), "w", encoding="utf-8") as f:
        json.dump(data, f)

def read_status(task_id):
    sf = status_file(task_id)
    if sf.exists():
        with open(sf, encoding="utf-8") as f:
            return json.load(f)
    return {}

def progress_callback(task_id):
    def hook(d):
        s = {'status': d['status'], 'task_id': task_id}
        if d['status'] == 'downloading':
            total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
            downloaded = d.get('downloaded_bytes', 0)
            speed = d.get('speed', 0)
            s['percent'] = round(downloaded / total * 100, 1) if total else 0
            s['downloaded'] = downloaded
            s['total'] = total
            s['speed'] = speed
            s['eta'] = d.get('eta', 0)
            write_status(task_id, s)
        elif d['status'] == 'finished':
            s['percent'] = 100
            s['msg'] = 'اكتمل التحميل، جارٍ الدمج...'
            write_status(task_id, s)
    return hook

def download_worker(url, format_id, task_id, opts_extra=None):
    cfg = get_config()
    fmt = format_id or cfg['format']
    try:
        write_status(task_id, {'status': 'fetching', 'msg': 'جاري جلب معلومات الفيديو...'})
        with yt_dlp.YoutubeDL({'quiet': True, 'no_warnings': True}) as ydl:
            info = ydl.extract_info(url, download=False)

        platform_dir = get_platform_dir(info.get('extractor_key', 'Unknown'))
        title = info.get('title', 'video')
        safe_title = clean_filename(title)

        ext_guess = 'mp4'
        if 'audio' in fmt:
            ext_guess = 'm4a'

        temp_filename = f'{task_id}.%(ext)s'
        output_template = str(platform_dir / temp_filename)

        opts = {
            'outtmpl': output_template,
            'format': fmt,
            'merge_output_format': 'mp4',
            'quiet': True,
            'no_warnings': True,
            'progress_hooks': [progress_callback(task_id)],
            'embedmetadata': True,
        }

        if cfg.get('subtitles'):
            opts.update({'writesubtitles': True, 'writeautomaticsub': True, 'subtitleslangs': ['en', 'ar']})
        if cfg.get('cookies_file'):
            opts['cookiefile'] = cfg['cookies_file']
        if cfg.get('proxy'):
            opts['proxy'] = cfg['proxy']
        if cfg.get('limit_speed'):
            opts['ratelimit'] = int(cfg['limit_speed'])
        if not cfg.get('playlist'):
            opts['noplaylist'] = True
        if opts_extra:
            opts.update(opts_extra)

        write_status(task_id, {'status': 'downloading', 'msg': 'جاري التحميل...', 'percent': 0})
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.extract_info(url, download=True)

        actual_file = None
        for f in platform_dir.iterdir():
            if f.name.startswith(task_id) and f.suffix in ('.mp4', '.webm', '.mkv', '.m4a'):
                actual_file = f
                break

        if actual_file:
            final_ext = actual_file.suffix.lstrip('.')
            new_name = f'{safe_title}.{final_ext}'
            new_path = platform_dir / new_name
            try:
                if not new_path.exists():
                    actual_file.rename(new_path)
                actual_file = new_path
            except OSError:
                pass

        entry = {
            'title': title,
            'url': url,
            'platform': info.get('extractor_key', 'Unknown'),
            'filename': actual_file.name if actual_file else title,
            'path': str(actual_file) if actual_file else '',
            'size': format_size(actual_file.stat().st_size) if actual_file and actual_file.exists() else '',
            'duration': format_duration(info.get('duration')),
            'format': fmt,
            'time': time.strftime('%Y-%m-%d %H:%M:%S'),
        }
        add_history(entry)

        write_status(task_id, {'status': 'completed', 'msg': 'تم التحميل بنجاح!', 'entry': entry})
        download_progress.pop(task_id, None)

    except Exception as e:
        err = str(e)
        if 'ffmpeg' in err.lower():
            err += ' | يرجى تثبيت FFmpeg للجودة العالية'
        write_status(task_id, {'status': 'error', 'msg': err})
        download_progress.pop(task_id, None)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/history')
def history_page():
    return render_template('history.html')

@app.route('/settings')
def settings_page():
    return render_template('settings.html')

@app.route('/api/info', methods=['POST'])
def get_info():
    url = request.form.get('url', '').strip()
    if not url:
        return jsonify({'error': 'الرجاء إدخال رابط الفيديو'}), 400
    try:
        with yt_dlp.YoutubeDL({'quiet': True, 'no_warnings': True}) as ydl:
            info = ydl.extract_info(url, download=False)

        formats = []
        seen = set()
        formats.append({
            'format_id': 'best[ext=mp4]/best',
            'label': 'أفضل جودة (MP4)',
            'note': 'فيديو + صوت - MP4',
            'size': '',
            'ext': 'mp4',
            'is_best': True,
        })
        has_audio = False
        for f in info.get('formats', []):
            height = f.get('height') or 0
            ext = f.get('ext', '')
            filesize = f.get('filesize') or f.get('filesize_approx', 0)
            vcodec = f.get('vcodec', 'none')
            acodec = f.get('acodec', 'none')
            has_v = vcodec != 'none'
            has_a = acodec not in ('none', None)
            if height and ext in ('mp4', 'webm') and has_v:
                key = (height, ext, has_a)
                if key not in seen:
                    seen.add(key)
                    size_mb = round(filesize / (1024 * 1024), 1) if filesize else 0
                    label = f'{height}p ({ext})'
                    label += ' كامل' if has_a else ' فيديو فقط'
                    formats.append({
                        'format_id': f['format_id'],
                        'label': label,
                        'note': f'{height}p - {ext}',
                        'size': f'{size_mb}MB' if size_mb else '',
                        'ext': ext,
                        'is_best': False,
                    })
            if not has_v and has_a and ext in ('m4a', 'mp3', 'webm') and not has_audio:
                has_audio = True
                size_mb = round(filesize / (1024 * 1024), 1) if filesize else 0
                formats.append({
                    'format_id': 'bestaudio[ext=m4a]/bestaudio',
                    'label': 'صوت فقط (MP3)',
                    'note': 'صوت عالي الجودة',
                    'size': f'{size_mb}MB' if size_mb else '',
                    'ext': 'm4a',
                    'is_best': False,
                })

        formats.sort(key=lambda x: (
            0 if x.get('is_best') else (1 if 'صوت' in x.get('label', '') else 2),
            -(int(re.search(r'(\d+)', x.get('note', '')).group(1)) if re.search(r'(\d+)', x.get('note', '')) else 0)
        ))

        thumbs = info.get('thumbnails', [])
        thumbnail = thumbs[-1].get('url', '') if thumbs else ''
        return jsonify({
            'title': info.get('title', 'فيديو'),
            'thumbnail': thumbnail,
            'duration': info.get('duration', 0),
            'formats': formats,
            'extractor': info.get('extractor_key', ''),
            'extractor_long': info.get('extractor', ''),
            'view_count': info.get('view_count', 0),
            'like_count': info.get('like_count', 0),
            'uploader': info.get('uploader', ''),
        })
    except Exception as e:
        return jsonify({'error': f'فشل جلب المعلومات: {str(e)}'}), 400

@app.route('/api/download', methods=['POST'])
def start_download():
    url = request.form.get('url', '').strip()
    format_id = request.form.get('format_id', 'best[ext=mp4]/best').strip()
    if not url:
        return jsonify({'error': 'الرجاء إدخال الرابط'}), 400

    task_id = uuid.uuid4().hex
    download_progress[task_id] = {'status': 'queued', 'percent': 0}
    write_status(task_id, {'status': 'queued', 'msg': 'في قائمة الانتظار...'})

    thread = threading.Thread(target=download_worker, args=(url, format_id, task_id), daemon=True)
    thread.start()

    return jsonify({'task_id': task_id, 'status': 'queued'})

@app.route('/api/progress/<task_id>')
def get_progress(task_id):
    status = read_status(task_id)
    if not status:
        return jsonify({'status': 'unknown'})
    return jsonify(status)

@app.route('/api/history')
def get_history_api():
    limit = request.args.get('limit', 50, type=int)
    platform = request.args.get('platform', '')
    history = get_history()
    if platform:
        history = [h for h in history if h.get('platform', '').lower() == platform.lower()]
    return jsonify(history[:limit])

@app.route('/api/history/clear', methods=['POST'])
def clear_history():
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump([], f)
    return jsonify({'success': True})

@app.route('/api/stats')
def get_stats():
    history = get_history()
    platforms = {}
    for h in history:
        p = h.get('platform', 'Unknown')
        platforms[p] = platforms.get(p, 0) + 1
    platform_list = [{'name': k, 'count': v} for k, v in sorted(platforms.items(), key=lambda x: -x[1])]
    total_size = sum(len(json.dumps(h)) for h in history)
    return jsonify({
        'total_downloads': len(history),
        'platforms': platform_list,
        'total_platforms': len(platform_list),
        'total_size_bytes': total_size,
    })

@app.route('/api/bulk', methods=['POST'])
def bulk_download():
    urls_text = request.form.get('urls', '').strip()
    format_id = request.form.get('format_id', 'best[ext=mp4]/best').strip()
    if not urls_text:
        return jsonify({'error': 'الرجاء إدخال الروابط'}), 400

    urls = [u.strip() for u in urls_text.split('\n') if u.strip()]
    tasks = []
    for url in urls:
        task_id = uuid.uuid4().hex
        write_status(task_id, {'status': 'queued', 'msg': 'في قائمة الانتظار...'})
        thread = threading.Thread(target=download_worker, args=(url, format_id, task_id), daemon=True)
        thread.start()
        tasks.append({'task_id': task_id, 'url': url})
    return jsonify({'tasks': tasks, 'count': len(tasks)})

@app.route('/api/config', methods=['GET', 'POST'])
def config_api():
    if request.method == 'POST':
        cfg = get_config()
        for key in cfg:
            if key in request.form:
                val = request.form[key]
                if val in ('true', 'false'):
                    cfg[key] = val == 'true'
                elif val.isdigit():
                    cfg[key] = int(val)
                else:
                    cfg[key] = val
        save_config(cfg)
        return jsonify({'success': True})
    return jsonify(get_config())

@app.route('/api/platforms')
def list_platforms():
    dirs = []
    if BASE_DIR.exists():
        for d in BASE_DIR.iterdir():
            if d.is_dir() and not d.name.startswith('.'):
                files = [f for f in d.iterdir() if f.is_file()]
                total_size = sum(f.stat().st_size for f in files)
                dirs.append({
                    'name': d.name,
                    'count': len(files),
                    'size': format_size(total_size),
                })
    return jsonify(dirs)

@app.route('/files/<path:platform>/<path:filename>')
def serve_file(platform, filename):
    platform_dir = get_platform_dir(platform)
    safe_path = (Path(platform_dir) / filename).resolve()
    try:
        safe_path.relative_to(Path(platform_dir).resolve())
    except ValueError:
        return 'Invalid path', 400
    return send_from_directory(str(platform_dir), filename, as_attachment=True)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', '1') == '1'
    print('=' * 50)
    print('  Video Downloader Pro - Web Interface')
    print('  أداة تحميل الفيديوهات من جميع المنصات')
    print('=' * 50)
    print(f'  الحفظ في: {BASE_DIR}')
    print(f'  افتح: http://localhost:{port}')
    print('=' * 50)
    app.run(host='0.0.0.0', port=port, debug=debug, threaded=True)
