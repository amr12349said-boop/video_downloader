import os, json, sqlite3, shutil, base64
from pathlib import Path
import win32crypt
from Cryptodome.Cipher import AES

# Get Chrome AES key
local_state = Path(os.environ['LOCALAPPDATA']) / 'Google' / 'Chrome' / 'User Data' / 'Local State'
with open(str(local_state), encoding='utf-8') as f:
    state = json.load(f)
enc_key = base64.b64decode(state['os_crypt']['encrypted_key'].encode('ascii'))
master_key = win32crypt.CryptUnprotectData(enc_key[5:], None, None, None, 0)[1]

# Copy cookies DB
src = Path(os.environ['LOCALAPPDATA']) / 'Google' / 'Chrome' / 'User Data' / 'Default' / 'Network' / 'Cookies'
dst = Path(os.environ['TEMP']) / 'chrome_cookies_decrypt.sqlite'
shutil.copy2(str(src), str(dst))

conn = sqlite3.connect(str(dst))
cursor = conn.cursor()
cursor.execute("SELECT host_key, path, is_secure, expires_utc, name, encrypted_value FROM cookies WHERE host_key LIKE '%.youtube.com' OR host_key = 'youtube.com'")
rows = cursor.fetchall()

def decrypt_value(encrypted_value):
    if not encrypted_value:
        return ''
    try:
        nonce = encrypted_value[3:15]
        ciphertext = encrypted_value[15:-16]
        tag = encrypted_value[-16:]
        cipher = AES.new(master_key, AES.MODE_GCM, nonce=nonce)
        return cipher.decrypt_and_verify(ciphertext, tag).decode('utf-8')
    except Exception:
        return ''

count = 0
with open('cookies.txt', 'w', encoding='utf-8') as f:
    f.write('# Netscape HTTP Cookie File\n')
    for row in rows:
        host, path, is_secure, expires, name, enc_val = row
        val = decrypt_value(enc_val)
        if val:
            secure_str = 'TRUE' if is_secure else 'FALSE'
            expires_str = str(int(expires)) if expires else '0'
            f.write(f'{host}\tTRUE\t{path}\t{secure_str}\t{expires_str}\t{name}\t{val}\n')
            count += 1

conn.close()
os.remove(str(dst))
print(f'Exported {count} YouTube cookies to cookies.txt')
