import os, json, sqlite3, shutil, base64
from pathlib import Path
import win32crypt
from Cryptodome.Cipher import AES

local_state = Path(os.environ['LOCALAPPDATA']) / 'Google' / 'Chrome' / 'User Data' / 'Local State'
with open(str(local_state), encoding='utf-8') as f:
    state = json.load(f)
enc_key = base64.b64decode(state['os_crypt']['encrypted_key'].encode('ascii'))
master_key = win32crypt.CryptUnprotectData(enc_key[5:], None, None, None, 0)[1]
print(f'Master key length: {len(master_key)} bytes')

src = Path(os.environ['LOCALAPPDATA']) / 'Google' / 'Chrome' / 'User Data' / 'Default' / 'Network' / 'Cookies'
dst = Path(os.environ['TEMP']) / 'chrome_cookies_debug.sqlite'
shutil.copy2(str(src), str(dst))

conn = sqlite3.connect(str(dst))
cursor = conn.cursor()
cursor.execute("SELECT name, encrypted_value FROM cookies WHERE host_key LIKE '%.youtube.com' LIMIT 3")

for name, enc_val in cursor.fetchall():
    print(f'\nCookie: {name}')
    print(f'  Raw bytes ({len(enc_val)}): {enc_val[:20].hex()}')
    print(f'  First 3 bytes: {enc_val[:3]}')
    print(f'  v10/v11 check: {enc_val[:3] == b"v10" or enc_val[:3] == b"v11"}')

    try:
        nonce = enc_val[3:15]
        ciphertext = enc_val[15:-16]
        tag = enc_val[-16:]
        print(f'  Nonce: {nonce.hex()}')
        print(f'  Ciphertext: {ciphertext[:10].hex()}...')
        print(f'  Tag: {tag.hex()}')

        cipher = AES.new(master_key, AES.MODE_GCM, nonce=nonce)
        decrypted = cipher.decrypt_and_verify(ciphertext, tag)
        print(f'  DECRYPTED: {decrypted.decode("utf-8")}')
    except Exception as e:
        print(f'  FAILED: {e}')

conn.close()
os.remove(str(dst))
