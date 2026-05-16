import os, time
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

user_data = Path(os.environ['LOCALAPPDATA']) / 'Google' / 'Chrome' / 'User Data'

options = Options()
options.add_argument(f'--user-data-dir={user_data}')
options.add_argument('--profile-directory=Default')
options.add_argument('--headless=new')
options.add_argument('--disable-gpu')
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')
options.add_experimental_option('excludeSwitches', ['enable-logging'])

print('Launching Chrome...')
driver = webdriver.Chrome(options=options)
try:
    driver.get('https://www.youtube.com')
    time.sleep(3)
    cookies = driver.get_cookies()
    print(f'Got {len(cookies)} cookies')
    
    with open('cookies.txt', 'w', encoding='utf-8') as f:
        f.write('# Netscape HTTP Cookie File\n')
        for c in cookies:
            domain = c.get('domain', '')
            path = c.get('path', '/')
            secure = 'TRUE' if c.get('secure', False) else 'FALSE'
            expires = str(int(c.get('expiry', 0))) if c.get('expiry') else '0'
            name = c.get('name', '')
            value = c.get('value', '')
            f.write(f'{domain}\tTRUE\t{path}\t{secure}\t{expires}\t{name}\t{value}\n')
    
    yt_cookies = [c for c in cookies if 'youtube' in c.get('domain', '') or 'google' in c.get('domain', '')]
    print(f'YouTube/Google cookies: {len(yt_cookies)}')
    for c in yt_cookies[:5]:
        print(f'  {c["name"]}: {c["value"][:20]}...')
finally:
    driver.quit()
