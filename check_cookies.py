import os, sqlite3, shutil
from pathlib import Path

src = Path(os.environ['LOCALAPPDATA']) / 'Google' / 'Chrome' / 'User Data' / 'Default' / 'Network' / 'Cookies'
dst = Path(os.environ['TEMP']) / 'chrome_cookies_check.sqlite'
shutil.copy2(str(src), str(dst))

conn = sqlite3.connect(str(dst))
cursor = conn.cursor()

cursor.execute("SELECT COUNT(*) FROM cookies")
total = cursor.fetchone()[0]
print(f'Total cookies in DB: {total}')

cursor.execute("SELECT COUNT(*) FROM cookies WHERE host_key LIKE '%.youtube.com' OR host_key = 'youtube.com'")
yt = cursor.fetchone()[0]
print(f'YouTube cookies: {yt}')

cursor.execute("SELECT host_key, name, length(encrypted_value) as vlen FROM cookies WHERE host_key LIKE '%.youtube.com' LIMIT 5")
for r in cursor.fetchall():
    print(f'  {r[0]:30s} {r[1]:20s} val_len={r[2]}')

conn.close()
os.remove(str(dst))
