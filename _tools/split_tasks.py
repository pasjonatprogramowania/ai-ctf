import os, re, glob

SRC = r'C:\Users\pawel\Desktop\CTF - AI\_extract'
OUT = r'C:\Users\pawel\Desktop\CTF - AI\_tasks'
os.makedirs(OUT, exist_ok=True)

NOISE = re.compile(r'^\s*(\d{2}\.\d{2}\.\d{4}, \d{2}:\d{2} S\d{2}E\d{2}.*|https://bravecourses\.circle\.so/.*|\d+/24)\s*$')
PAGE = re.compile(r'^\s*===== STRONA \d+ =====\s*$')

index = []
for f in sorted(glob.glob(os.path.join(SRC, '*.txt'))):
    base = os.path.basename(f)[:-4]
    code = base.split('_')[0]
    lines = open(f, encoding='utf-8').read().split('\n')
    starts = [i for i, l in enumerate(lines) if l.strip().upper().startswith('ZADANIE')]
    if not starts:
        starts = [i for i, l in enumerate(lines) if re.match(r'^\s*Zadanie\b', l)]
    if not starts:
        starts = [i for i, l in enumerate(lines) if 'centrala' in l.lower()]
    if not starts:
        index.append((code, base, 0))
        continue
    i = starts[0]
    chunk = []
    for l in lines[i:i + 200]:
        if PAGE.match(l) or NOISE.match(l):
            continue
        chunk.append(l.rstrip())
    text = re.sub(r'\n{3,}', '\n\n', '\n'.join(chunk)).strip()
    with open(os.path.join(OUT, code + '.md'), 'w', encoding='utf-8') as fh:
        fh.write(f'# {base}\n\n{text}\n')
    index.append((code, base, len(text)))

with open(os.path.join(OUT, '_index.md'), 'w', encoding='utf-8') as fh:
    fh.write('| kod | lekcja | znakow sekcji zadania |\n|---|---|---|\n')
    for code, base, n in index:
        fh.write(f'| {code} | {base} | {n} |\n')
for code, base, n in index:
    print(f'{code}: {n}')
