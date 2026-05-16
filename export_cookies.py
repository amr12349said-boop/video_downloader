import browser_cookie3, http.cookiejar
cj = browser_cookie3.chrome(domain_name='youtube.com')
with open('cookies.txt', 'w', encoding='utf-8') as f:
    f.write('# Netscape HTTP Cookie File\n')
    for c in cj:
        domain = c.domain
        path = c.path
        secure = 'TRUE' if c.secure else 'FALSE'
        expires = str(int(c.expires)) if c.expires else '0'
        name = c.name
        value = c.value
        f.write(f'{domain}\tTRUE\t{path}\t{secure}\t{expires}\t{name}\t{value}\n')
print(f'Exported {len(list(cj))} cookies')
