import os, shutil, sqlite3
from pathlib import Path
import win32crypt

src = Path(os.environ['LOCALAPPDATA']) / 'Google' / 'Chrome' / 'User Data' / 'Default' / 'Network' / 'Cookies'
dst = Path(os.environ['TEMP']) / 'chrome_cookies_copy.sqlite'

shutil.copy2(str(src), str(dst))
conn = sqlite3.connect(str(dst))
cursor = conn.cursor()

cursor.execute("SELECT host_key, path, is_secure, expires_utc, name, value, encrypted_value FROM cookies WHERE host_key LIKE '%.youtube.com' OR host_key = 'youtube.com'")
rows = cursor.fetchall()
print(f'Found {len(rows)} YouTube cookies')

count = 0
with open('cookies.txt', 'w', encoding='utf-8') as f:
    f.write('# Netscape HTTP Cookie File\n')
    for row in rows:
        host, path, is_secure, expires, name, val, enc_val = row
        try:
            if val:
                cookie_value = val
            else:
                cookie_value = win32crypt.CryptUnprotectData(enc_val, None, None, None, 0)[1].decode('utf-8')
            secure_str = 'TRUE' if is_secure else 'FALSE'
            expires_str = str(int(expires)) if expires else '0'
            f.write(f'{host}\tTRUE\t{path}\t{secure_str}\t{expires_str}\t{name}\t{cookie_value}\n')
            count += 1
        except Exception as e:
            print(f'Failed: {name}: {e}')

conn.close()
os.remove(str(dst))
print(f'Exported {count} cookies to cookies.txt')
