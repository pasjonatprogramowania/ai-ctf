"""Minimalny ekstraktor tekstu z PDF (bez zaleznosci zewnetrznych).

Obsluguje: klasyczny xref, obiekty strumieniowe FlateDecode, fonty Type0/CIDFontType2
z ToUnicode CMap, proste fonty z WinAnsi/MacRoman, oraz Type3 (best effort).
"""
import re, sys, os, zlib, glob

OBJ_RE = re.compile(rb'(?<![0-9])(\d{1,7})\s+(\d{1,5})\s+obj\b')
LEN_RE = re.compile(rb'/Length\s+(\d+)(?!\s+\d+\s+R)')


class PDF:
    def __init__(self, data):
        self.data = data
        self.objs = {}
        self._scan()

    def _scan(self):
        data = self.data
        pos = 0
        n = len(data)
        while pos < n:
            m = OBJ_RE.search(data, pos)
            if not m:
                break
            num = int(m.group(1))
            body = m.end()
            s = data.find(b'stream', body)
            e = data.find(b'endobj', body)
            if s != -1 and (e == -1 or s < e) and (s - body) < 30000:
                dict_part = data[body:s]
                j = s + 6
                while j < n and data[j] in (13, 10):
                    j += 1
                lm = LEN_RE.search(dict_part)
                if lm:
                    ln = int(lm.group(1))
                    raw = data[j:j + ln]
                    nxt = data.find(b'endstream', j + ln)
                    pos = (nxt + 9) if nxt != -1 else j + ln
                else:
                    k = data.find(b'endstream', j)
                    if k == -1:
                        k = min(n, j + 5_000_000)
                    raw = data[j:k]
                    pos = k + 9
                self.objs[num] = (dict_part, raw)
            else:
                dict_part = data[body:e] if e != -1 else data[body:body + 4000]
                self.objs[num] = (dict_part, None)
                pos = (e + 6) if e != -1 else body

    def raw(self, num):
        return self.objs.get(num, (b'', None))

    def stream(self, num):
        d, s = self.objs.get(num, (b'', None))
        if s is None:
            return None
        if b'FlateDecode' in d:
            try:
                return zlib.decompress(s)
            except Exception:
                try:
                    return zlib.decompressobj().decompress(s)
                except Exception:
                    return None
        return s

    # --- struktura dokumentu -------------------------------------------------
    def catalog(self):
        for num, (d, _) in self.objs.items():
            if b'/Type' in d and re.search(rb'/Type\s*/Catalog', d):
                return num, d
        return None, None

    def pages(self):
        out = []
        num, d = self.catalog()
        if num is None:
            # awaryjnie: wszystkie obiekty /Type /Page
            for n2, (d2, _) in sorted(self.objs.items()):
                if re.search(rb'/Type\s*/Page[^s]', d2):
                    out.append(n2)
            return out
        m = re.search(rb'/Pages\s+(\d+)\s+\d+\s+R', d)
        if not m:
            return out
        self._walk(int(m.group(1)), out, set())
        return out

    def _walk(self, num, out, seen):
        if num in seen or len(out) > 5000:
            return
        seen.add(num)
        d, _ = self.objs.get(num, (b'', None))
        if re.search(rb'/Type\s*/Page[^s]', d):
            out.append(num)
            return
        km = re.search(rb'/Kids\s*\[(.*?)\]', d, re.S)
        if km:
            for ref in re.findall(rb'(\d+)\s+\d+\s+R', km.group(1)):
                self._walk(int(ref), out, seen)
            return
        # Kids moze byc posredni
        km = re.search(rb'/Kids\s+(\d+)\s+\d+\s+R', d)
        if km:
            kd, _ = self.objs.get(int(km.group(1)), (b'', None))
            for ref in re.findall(rb'(\d+)\s+\d+\s+R', kd):
                self._walk(int(ref), out, seen)


def hex2uni(h):
    b = bytes.fromhex(h if isinstance(h, str) else h.decode())
    if len(b) % 2:
        b += b'\x00'
    try:
        return b.decode('utf-16-be')
    except Exception:
        return ''.join(chr(c) for c in b)


def parse_cmap(txt):
    m = {}
    for blk in re.findall(rb'beginbfchar(.*?)endbfchar', txt, re.S):
        for src, dst in re.findall(rb'<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]*)>', blk):
            m[int(src, 16)] = hex2uni(dst)
    for blk in re.findall(rb'beginbfrange(.*?)endbfrange', txt, re.S):
        for mm in re.finditer(
                rb'<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>\s*(?:<([0-9A-Fa-f]+)>|\[(.*?)\])',
                blk, re.S):
            lo, hi = int(mm.group(1), 16), int(mm.group(2), 16)
            if hi - lo > 65535:
                continue
            if mm.group(3):
                base = hex2uni(mm.group(3))
                for k in range(hi - lo + 1):
                    if base:
                        m[lo + k] = base[:-1] + chr(ord(base[-1]) + k)
            else:
                for k, it in enumerate(re.findall(rb'<([0-9A-Fa-f]+)>', mm.group(4))):
                    m[lo + k] = hex2uni(it)
    return m


TOKEN_RE = re.compile(rb"""
    (?P<ws>\s+)
  | (?P<str>\((?:[^()\\]|\\.)*\))
  | (?P<hex><[0-9A-Fa-f\s]*>)
  | (?P<arrS>\[)
  | (?P<arrE>\])
  | (?P<name>/[^\s/\[\]<>(){}]*)
  | (?P<num>[-+]?(?:\d+\.?\d*|\.\d+))
  | (?P<op>[A-Za-z'"*][A-Za-z0-9'"*]*)
""", re.X | re.S)


def unescape_lit(s):
    s = s[1:-1]
    out = bytearray()
    i = 0
    while i < len(s):
        c = s[i]
        if c == 0x5C and i + 1 < len(s):
            nx = s[i + 1]
            mp = {0x6E: 10, 0x72: 13, 0x74: 9, 0x62: 8, 0x66: 12,
                  0x28: 40, 0x29: 41, 0x5C: 92}
            if nx in mp:
                out.append(mp[nx]); i += 2; continue
            if 0x30 <= nx <= 0x37:
                oct_digits = ''
                j = i + 1
                while j < len(s) and len(oct_digits) < 3 and 0x30 <= s[j] <= 0x37:
                    oct_digits += chr(s[j]); j += 1
                out.append(int(oct_digits, 8) & 0xFF); i = j; continue
            if nx in (10, 13):
                i += 2
                if nx == 13 and i < len(s) and s[i] == 10:
                    i += 1
                continue
            out.append(nx); i += 2; continue
        out.append(c); i += 1
    return bytes(out)


class Font:
    def __init__(self, cmap=None, two_byte=False):
        self.cmap = cmap or {}
        self.two_byte = two_byte

    def decode(self, bs):
        out = []
        if self.two_byte:
            if len(bs) % 2:
                bs += b'\x00'
            for i in range(0, len(bs), 2):
                code = (bs[i] << 8) | bs[i + 1]
                out.append(self.cmap.get(code, ''))
        else:
            for b in bs:
                out.append(self.cmap.get(b, chr(b) if 32 <= b < 127 or b in (10, 13, 9) else ''))
        return ''.join(out)


def load_fonts(pdf, page_dict):
    fonts = {}
    fm = re.search(rb'/Font\s*<<(.*?)>>', page_dict, re.S)
    fin = None
    if fm:
        fin = fm.group(1)
    else:
        fr = re.search(rb'/Font\s+(\d+)\s+\d+\s+R', page_dict)
        if fr:
            fin = pdf.raw(int(fr.group(1)))[0]
    if not fin:
        # zasoby moga byc posrednie
        rr = re.search(rb'/Resources\s+(\d+)\s+\d+\s+R', page_dict)
        if rr:
            rd = pdf.raw(int(rr.group(1)))[0]
            fm = re.search(rb'/Font\s*<<(.*?)>>', rd, re.S)
            fin = fm.group(1) if fm else None
            if fin is None:
                fr = re.search(rb'/Font\s+(\d+)\s+\d+\s+R', rd)
                if fr:
                    fin = pdf.raw(int(fr.group(1)))[0]
    if not fin:
        return fonts
    for name, ref in re.findall(rb'/([A-Za-z0-9#+._-]+)\s+(\d+)\s+\d+\s+R', fin):
        fd = pdf.raw(int(ref))[0]
        two = b'/Type0' in fd or b'Identity-H' in fd
        cm = {}
        tu = re.search(rb'/ToUnicode\s+(\d+)\s+\d+\s+R', fd)
        if tu:
            st = pdf.stream(int(tu.group(1)))
            if st:
                cm = parse_cmap(st)
                if not cm:
                    two = False
        else:
            two = b'/Type0' in fd
        fonts[name] = Font(cm, two)
    return fonts


def mat_mul(m, n):
    a, b, c, d, e, f = m
    a2, b2, c2, d2, e2, f2 = n
    return (a * a2 + b * c2, a * b2 + b * d2,
            c * a2 + d * c2, c * b2 + d * d2,
            e * a2 + f * c2 + e2, e * b2 + f * d2 + f2)


def page_text(pdf, page_num, fonts):
    d = pdf.raw(page_num)[0]
    contents = []
    cm = re.search(rb'/Contents\s+(\d+)\s+\d+\s+R', d)
    if cm:
        contents.append(int(cm.group(1)))
    else:
        ca = re.search(rb'/Contents\s*\[(.*?)\]', d, re.S)
        if ca:
            contents = [int(x) for x in re.findall(rb'(\d+)\s+\d+\s+R', ca.group(1))]
    buf = b''
    for c in contents:
        st = pdf.stream(c)
        if st:
            buf += st + b'\n'
    if not buf:
        return ''
    out = []
    stack = []
    cur = Font()
    fs = 12.0
    tm = (1, 0, 0, 1, 0, 0)
    tlm = (1, 0, 0, 1, 0, 0)
    leading = 12.0
    state = {'y': None, 'xe': None}

    def emit(s):
        if not s:
            return
        y = tm[5]
        x = tm[4]
        if state['y'] is not None and out:
            if abs(y - state['y']) > 0.35 * fs:
                if not out[-1].endswith('\n'):
                    out.append('\n')
            elif state['xe'] is not None and (x - state['xe']) > 0.5 * fs:
                out.append(' ')
        out.append(s)
        state['y'] = y
        state['xe'] = x + 0.5 * fs * len(s)

    def decode_hex(t):
        h = re.sub(rb'[^0-9A-Fa-f]', b'', t)
        if len(h) % 2:
            h += b'0'
        return cur.decode(bytes.fromhex(h.decode()))

    for m in TOKEN_RE.finditer(buf):
        kind = m.lastgroup
        if kind == 'ws':
            continue
        tok = m.group()
        if kind in ('str', 'hex', 'num', 'name'):
            stack.append((kind, tok))
            continue
        if kind == 'arrS':
            stack.append(('arrS', tok))
            continue
        if kind == 'arrE':
            items = []
            for k, t in reversed(stack):
                if k == 'arrS':
                    break
                items.append((k, t))
            items.reverse()
            txt = []
            for k, t in items:
                if k == 'hex':
                    txt.append(decode_hex(t))
                elif k == 'str':
                    txt.append(cur.decode(unescape_lit(t)))
                elif k == 'num':
                    try:
                        if float(t) < -120:
                            txt.append(' ')
                    except Exception:
                        pass
            emit(''.join(txt))
            stack = []
            continue
        if kind == 'op':
            op = tok.decode('latin-1')
            nums = [float(t) for k, t in stack if k == 'num']
            if op == 'Tf':
                for k, t in reversed(stack):
                    if k == 'name':
                        cur = fonts.get(t[1:], Font())
                        break
                if nums:
                    fs = abs(nums[-1]) or 12.0
            elif op in ('Tj', "'", '"'):
                for k, t in reversed(stack):
                    if k == 'hex':
                        emit(decode_hex(t))
                        break
                    if k == 'str':
                        emit(cur.decode(unescape_lit(t)))
                        break
                if op in ("'", '"'):
                    tlm = mat_mul((1, 0, 0, 1, 0, -leading), tlm)
                    tm = tlm
            elif op in ('Td', 'TD'):
                if len(nums) >= 2:
                    tx, ty = nums[-2], nums[-1]
                    if op == 'TD':
                        leading = -ty
                    tlm = mat_mul((1, 0, 0, 1, tx, ty), tlm)
                    tm = tlm
            elif op == 'T*':
                tlm = mat_mul((1, 0, 0, 1, 0, -leading), tlm)
                tm = tlm
            elif op == 'Tm':
                if len(nums) >= 6:
                    tm = tuple(nums[-6:])
                    tlm = tm
            elif op == 'BT':
                tm = (1, 0, 0, 1, 0, 0)
                tlm = tm
            stack = []
            continue
    txt = ''.join(out)
    txt = re.sub(r'[ \t]+', ' ', txt)
    txt = re.sub(r'\n{3,}', '\n\n', txt)
    return txt.strip()


def extract(path):
    data = open(path, 'rb').read()
    pdf = PDF(data)
    parts = []
    for i, p in enumerate(pdf.pages(), 1):
        fonts = load_fonts(pdf, pdf.raw(p)[0])
        try:
            t = page_text(pdf, p, fonts)
        except Exception as e:
            t = f'[[blad ekstrakcji strony: {e}]]'
        parts.append(f'\n===== STRONA {i} =====\n{t}')
    return '\n'.join(parts)


if __name__ == '__main__':
    src = sys.argv[1]
    out_dir = sys.argv[2] if len(sys.argv) > 2 else os.path.join(os.path.dirname(src), '_extract')
    os.makedirs(out_dir, exist_ok=True)
    files = sorted(glob.glob(os.path.join(src, '*.pdf'))) if os.path.isdir(src) else [src]
    for f in files:
        name = os.path.splitext(os.path.basename(f))[0]
        safe = re.sub(r'[^A-Za-z0-9._-]+', '_', name).strip('_')
        try:
            txt = extract(f)
        except Exception as e:
            txt = f'[[BLAD: {e}]]'
        p = os.path.join(out_dir, safe + '.txt')
        with open(p, 'w', encoding='utf-8') as fh:
            fh.write(txt)
        print(f'{safe}: {len(txt)} znakow -> {p}')
