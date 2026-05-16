import os, sqlite3, shutil
from pathlib import Path

src = Path(os.environ['LOCALAPPDATA']) / 'Google' / 'Chrome' / 'User Data' / 'Default' / 'Network' / 'Cookies'
dst = Path(os.environ['TEMP']) / 'chrome_cookies_plain.sqlite'
shutil.copy2(str(src), str(dst))

conn = sqlite3.connect(str(dst))
cursor = conn.cursor()

cursor.execute("SELECT host_key, name, value, length(encrypted_value) FROM cookies WHERE host_key LIKE '%.youtube.com' AND value != ''")
rows = cursor.fetchall()
print(f'YouTube cookies with plaintext values: {len(rows)}')
for r in rows[:10]:
    print(f'  {r[0]:30s} {r[1]:20s} val="{r[2][:50]}" enc_len={r[3]}')

cursor.execute("SELECT COUNT(*) FROM cookies WHERE host_key LIKE '%.youtube.com' AND value = ''")
empty = cursor.fetchone()[0]
print(f'\nYouTube cookies with EMPTY plaintext: {empty}')

conn.close()
os.remove(str(dst))
