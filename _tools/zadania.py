import os, re, glob, sys

SRC = r'C:\Users\pawel\Desktop\CTF - AI\_extract'
OUT = r'C:\Users\pawel\Desktop\CTF - AI\_extract\_ZADANIA_digest.md'

NOISE = re.compile(r'^\s*(\d{2}\.\d{2}\.\d{4}, \d{2}:\d{2} S\d{2}E\d{2}.*|https://bravecourses\.circle\.so/.*|\d+/24)\s*$')
PAGE = re.compile(r'^\s*===== STRONA \d+ =====\s*$')

chunks = []
for f in sorted(glob.glob(os.path.join(SRC, '*.txt'))):
    name = os.path.basename(f).replace('.txt', '')
    code = name.split('_')[0]
    lines = open(f, encoding='utf-8').read().split('\n')
    idxs = [i for i, l in enumerate(lines) if l.strip() in ('ZADANIE', 'Zadanie', 'ZADANIE:')]
    block = [f'\n\n## {code} — {name}\n']
    if not idxs:
        block.append('_brak sekcji ZADANIE_\n')
    for i in idxs[:3]:
        end = min(len(lines), i + 130)
        chunk = []
        for l in lines[i:end]:
            if PAGE.match(l) or NOISE.match(l):
                continue
            chunk.append(l.rstrip())
        text = '\n'.join(chunk)
        text = re.sub(r'\n{3,}', '\n\n', text)
        block.append(text + '\n')
    chunks.append('\n'.join(block))

with open(OUT, 'w', encoding='utf-8') as fh:
    fh.write('# Digest sekcji ZADANIE\n' + '\n'.join(chunks))
print('znakow:', sum(len(c) for c in chunks), '->', OUT)
