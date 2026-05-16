import os, shutil, sqlite3
from pathlib import Path

src = Path(os.environ['LOCALAPPDATA']) / 'Google' / 'Chrome' / 'User Data' / 'Default' / 'Network' / 'Cookies'
dst = Path(os.environ['TEMP']) / 'cookies_schema.sqlite'

shutil.copy2(str(src), str(dst))
conn = sqlite3.connect(str(dst))
c = conn.cursor()
c.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = c.fetchall()
for t in tables:
    print(f'Table: {t[0]}')
    c.execute(f'SELECT sql FROM sqlite_master WHERE type="table" AND name="{t[0]}"')
    print(c.fetchone()[0])
    print()
conn.close()
os.remove(str(dst))
