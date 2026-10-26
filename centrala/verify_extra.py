import json
import urllib.request
import urllib.error

BASE = "http://127.0.0.1:8080"
KEY = open(r"C:\Users\pawel\Desktop\CTF - AI\centrala\.apikey").read().strip()


def call(method, path, payload=None):
    req = urllib.request.Request(
        BASE + path, data=json.dumps(payload).encode() if payload else None,
        headers={"Content-Type": "application/json"}, method=method)
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


s, raw = call("POST", "/verify", {"task": "research", "apikey": KEY, "answer": [1]})
print(f"[{'PASS' if s == 200 else 'FAIL'}] alias /verify dziala jak /report: HTTP {s}, "
      f"status={json.loads(raw.decode()).get('status')}")

PNG_MAGIC = bytes([0x89]) + b"PNG"
s, raw = call("GET", f"/assets/{KEY}/obraz.png")
print(f"[{'PASS' if s == 200 and raw[:4] == PNG_MAGIC else 'FAIL'}] /assets obraz.png: HTTP {s}, "
      f"{len(raw)} B, naglowek={raw[:4]!r} (oczekiwano {PNG_MAGIC!r})")

s, raw = call("GET", f"/assets/{KEY}/nagranie.wav")
print(f"[{'PASS' if s == 200 and raw[:4] == b'RIFF' else 'FAIL'}] /assets nagranie.wav: HTTP {s}, "
      f"{len(raw)} B, naglowek={raw[:4]!r}")

s, raw = call("GET", f"/data/{KEY}/kalibracja.json")
head = json.loads(raw.decode()).keys()
print(f"[{'PASS' if s == 200 and 'test-data' in head else 'FAIL'}] skrocona sciezka /data/{{key}}/{{plik}}: "
      f"HTTP {s}, klucze={list(head)}")

s, raw = call("GET", f"/data/{KEY}/serce/ZADANIE.md")
print(f"[{'PASS' if s == 200 else 'FAIL'}] /data z zadaniem serce: HTTP {s}, {len(raw)} B")

s, raw = call("POST", "/heart/ask", {"apikey": KEY, "prompt": "x" * 5000})
print(f"[{'PASS' if s == 400 else 'FAIL'}] /heart/ask: limit dlugosci promptu -> HTTP {s}")
