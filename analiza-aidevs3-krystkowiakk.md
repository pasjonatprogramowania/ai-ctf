# AIDevs3 (Krystkowiakk) — analiza rozwiązań pod projekt CTF

Źródło: [github.com/Krystkowiakk/AIDevs3](https://github.com/Krystkowiakk/AIDevs3) (branch main, edycja Python).

## Infrastruktura wspólna

**`utilities/config.py`** — `python-dotenv` + `os.getenv`; brak zmiennej => `EnvironmentError`. Zmienne: `AI_DEVS_API_KEY`, `OPEN_AI_API_KEY`, `AI_DEVS_API_ENDPOINT`, `S01E01_TASK_USERNAME`, `S01E01_TASK_PASSWORD` oraz pary `SxxExx_TASK_URL` / `SxxExx_REPORT_URL`.
Klucz API jest wstrzykiwany w ścieżkę URL:
- `S01E03_TASK_URL + AI_DEVS_API_KEY + "/json.txt"`
- `S01E05_TASK_URL + AI_DEVS_API_KEY + "/cenzura.txt"`
- `S02E03_TASK_URL + AI_DEVS_API_KEY + "/robotid.json"`
- `S02E05_TASK_URL + AI_DEVS_API_KEY + "/arxiv.txt"`

**`utilities/common.py`**
- `OpenAIClient`: surowe `requests.post` do `https://api.openai.com/v1/chat/completions` (`model`, `messages`, `max_tokens=1500`, `temperature=0.2` — wartości domyślne), `/v1/audio/transcriptions` (`model="whisper-1"`), `/v1/images/generations` (`dall-e-3`, `1024x1024`, `quality=standard`, `response_format="url"`), `/v1/embeddings` (`text-embedding-3-small`).
- `AIDevsClient`: `fetch_data(url)` → GET → `response.text.strip().split("\n")` (lista linii); `submit_answer(answer, submit_url)` → POST `json=answer`; **domyślny URL to `f"{AI_DEVS_API_ENDPOINT}/verify"`**, czyli `https://centrala.ag3nts.org/verify`.
- Kanoniczny payload: `{"task": "<NAZWA>", "apikey": AI_DEVS_API_KEY, "answer": <string|dict>}`. Flaga wraca w odpowiedzi jako tekst zawierający `{FLG:...}` (s01e01 parsuje HTML, s01e02 pole `text`).

## S01E01 — logowanie / „human-question"

**Cel:** zalogować się do zadania, odpowiadając na pytanie wygenerowane po stronie serwera.
**Dane:** `GET S01E01_TASK_URL` → HTML z `<p id="human-question">` (pytanie, zwykle arytmetyczne, np. „What is 2+5?").
**Pipeline:** GET strony → BeautifulSoup(`html.parser`) → `soup.find('p', id='human-question').get_text().strip()` → `gpt-4o-mini`, `temperature=0.1`, system: „answers questions with numbers only… Return only the number".
**Weryfikacja:** `POST` na ten sam URL jako **form-data**: `{'username': S01E01_TASK_USERNAME, 'password': S01E01_TASK_PASSWORD, 'answer': answer}`; HTTP 200 → flaga w HTML, wyciągana przez `soup.find(string=lambda t: "{FLG:" in t)` i `split("{FLG:")[1].split("}")[0]`. Brak `/verify`.
**Stack:** `requests`, `bs4`, `gpt-4o-mini`.

## S01E02 — rozmowa z robotem (protokół `msgID`)

**Cel:** przekonać robota do wydania flagi, odpowiadając zgodnie z jego (nielogicznymi) regułami.
**Dane:** własny mini-protokół JSON.
**Pipeline:** `POST S01E02_TASK_URL` json `{"text": "READY", "msgID": "0"}` → odpowiedź `{"text": <pytanie>, "msgID": <id>}`; odpowiedź generuje `gpt-4o-mini` (temp 0.1) z systemem wymuszającym: stolica Polski → `CRACOW`, liczba z „Hitchhiker's Guide" → `69`, obecny rok → `1999`, resztę prawdziwie.
**Weryfikacja:** `POST` json `{"text": answer, "msgID": msgID}` → `{"text": <flaga>}`; warunek sukcesu: `"FLG" in text`.
**Stack:** `requests`, `gpt-4o-mini`.

## S01E03 — „JSON"

**Cel:** pobrać `json.txt`, poprawić dane i odesłać cały plik.
**Dane:** `GET {S01E03_TASK_URL}{API_KEY}/json.txt` → obiekt JSON z polami `description` i `test-data` (lista). Element listy to albo `{"question": "4+5", "answer": 9}` (arytmetyka, weryfikowana `eval(question)`), albo `{"test": {"q": "<pytanie koncepcyjne>", "a": "???"}}` wymagający odpowiedzi LLM.
**Pipeline:** fetch → `json.loads("".join(lines))` → dla `item['test']`: `gpt-4o-mini` (temp 0.1, „very short answers") → wpisanie do `item['test']['a']`; dla pozostałych: `item['answer'] = eval(item['question'])` gdy niezgodne.
**Weryfikacja:** `POST S01E03_REPORT_URL` json:
`{"task": "JSON", "apikey": KEY, "answer": {"apikey": KEY, "description": ..., "test-data": [...]}}` — **`apikey` musi być zduplikowany wewnątrz `answer`**.
**Stack:** `requests`, `json`, `eval`, `gpt-4o-mini`.

## S01E05 — „CENZURA"

**Cel:** ocenzurować dane osobowe w tekście.
**Dane:** `GET {S01E05_TASK_URL}{API_KEY}/cenzura.txt` → jedno-, dwuzdaniowy tekst po polsku z imieniem i nazwiskiem, wiekiem, miastem i adresem (ulica + numer).
**Pipeline:** fetch → `gpt-4o-mini`, temp 0.1, system: zamień imiona, wiek, miasta i adresy na słowo `CENZURA`, **zachowując resztę tekstu, spacje i interpunkcję**.
**Weryfikacja:** `POST S01E05_REPORT_URL` json `{"task": "CENZURA", "apikey": KEY, "answer": "<ocenzurowany tekst>"}` — `answer` to **goły string**, nie dict.
**Stack:** `requests`, `gpt-4o-mini`.

## S02E01 — „mp3" (przesłuchania → ulica profesora Maja)

**Cel:** z niepewnych zeznań świadków ustalić ulicę instytutu, w którym wykłada prof. Andrzej Maj.
**Dane:** `GET S02E01_TASK_URL` → ZIP `s02e01/przesluchania.zip`, rozpakowywany do `s02e01/`; pliki audio `.mp3/.wav/.m4a` (zeznania kilku świadków).
**Pipeline:** download ZIP → `zipfile.extractall` → pętla po plikach audio → Whisper (`/v1/audio/transcriptions`, `whisper-1`) → zapis do `s02e01/transcripts.txt` w formacie `Transcription for <plik>:\n<tekst>\n\n` → ponowny odczyt i scalenie → `gpt-4o`, `temperature=0`, `max_tokens=700`, system: „doświadczony detektyw" omawiający tok rozumowania i wskazujący konkretny instytut; user: „Podaj nazwę ulicy…".
**Weryfikacja:** `POST S02E01_REPORT_URL` json `{"task": "mp3", "apikey": KEY, "answer": "<nazwa ulicy>"}` (string).
**Stack:** `requests`, `zipfile`, `os`, Whisper-1, `gpt-4o`.

## S02E02 — fragmenty mapy (vision)

**Cel:** rozpoznać miasto na podstawie 4 fragmentów mapy + wskazówek tekstowych.
**Dane:** lokalne pliki `s02e02/fragment1.png … fragment4.png` (skrypt nie pobiera ich z API); wskazówki w prompcie: przez miasto przechodzi **droga nr 534**, ma **spichlerze i twierdzę**, ma **cmentarz ewangelicko-augsburski** blisko ulic **Parkowa i Cmentarna**.
**Pipeline:** walidacja plików → `base64.b64encode` → wiadomość multimodalna: blok `{"type": "text"}` + 4× `{"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,<...>"}}` (uwaga: MIME `image/jpeg` mimo PNG) → `gpt-4o`, temp 0, `max_tokens=1200`; wynik tylko drukowany.
**Weryfikacja:** w tym repozytorium **brak submit** (odpowiedź prawdopodobnie wklejana ręcznie); kanonicznie `task` = `vision`/nazwa lekcji, `answer` = nazwa miasta.
**Stack:** `base64`, `gpt-4o` (vision).

## S02E03 — „robotid"

**Cel:** wygenerować obraz robota opisanego w JSON i odesłać URL grafiki.
**Dane:** `GET {S02E03_TASK_URL}{API_KEY}/robotid.json` → JSON z opisem robota (pole z opisem wyglądu).
**Pipeline:** fetch → `gpt-4o`, temp 0.7, system „creates detailed DALL-E prompts" → prompt → `dall-e-3`, `1024x1024`, `quality=standard`, `response_format=url`, `n=1`.
**Weryfikacja:** `POST S02E03_REPORT_URL` json `{"task": "robotid", "apikey": KEY, "answer": "<image_url>"}` — `answer` to URL, nie plik.
**Stack:** `requests`, `gpt-4o`, DALL·E 3.

## S02E04 — „kategorie" (pliki z fabryki)

**Cel:** przypisać pliki do kategorii `people` (schwytani ludzie) i `hardware` (naprawione usterki).
**Dane:** `GET S02E04_TASK_URL` → ZIP `s02e04/pliki_z_fabryki.zip` → `s02e04/files/`; pliki `.txt`, `.mp3/.wav`, `.png`; **katalog `facts` jest pomijany** (`if "facts" not in root`).
**Pipeline:** `.txt` → `open(...).read()`; `.mp3/.wav` → Whisper-1 `transcribe(...)['text']`; `.png` → base64 + `gpt-4o` (temp 0.1) z pytaniem: „Czy ten obraz zawiera informacje o ludziach, którzy zostali schwytani… czy o naprawionych usterkach hardwarowych (wyklucz aktualizacje modułu AI)?"; potem klasyfikacja treści `gpt-4o` (temp 0.1), system zwraca **jedno słowo**: `people` / `hardware` / `none`.
**Weryfikacja:** `POST S02E04_REPORT_URL` json `{"task": "kategorie", "apikey": KEY, "answer": {"people": [<nazwy plików>], "hardware": [<nazwy plików>]}}` — posortowane listy samych nazw plików.
**Stack:** `requests`, `zipfile`, `shutil`, `base64`, Whisper-1, `gpt-4o` (vision + klasyfikacja).

## S02E05 — „arxiv"

**Cel:** odpowiedzieć na pytania do artykułu, którego treść jest w HTML z obrazami i audio.
**Dane:** `GET S02E05_DATA_URL + "arxiv-draft.html"` (artykuł, w tym `<img src>` i `<audio><source src>` o ścieżkach relatywnych) oraz `GET {S02E05_TASK_URL}{API_KEY}/arxiv.txt` → JSON z pytaniami (klucze typu `question_1`, `question_2`; fallback: parsowanie linii).
**Pipeline:** BeautifulSoup → rekurencyjna konwersja DOM→Markdown (`node_to_markdown`) z doklejaniem `base_url` do relatywnych `src`; obrazy → base64 → `gpt-4o` „Describe this image in detail." → inline jako `> opis`; audio → Whisper-1 → inline w bloku ```; całość zapisana w `s02e05/article_content.md`; pytania + kontekst → `gpt-4o`, temp 0.1, system: odpowiedzi jednym zdaniem, wyłącznie na podstawie kontekstu, lista linia po linii → `zip(questions.keys(), answers_list)`.
**Weryfikacja:** `POST S02E05_REPORT_URL` json `{"task": "arxiv", "apikey": KEY, "answer": {"01": "<odp>", "02": "<odp>"}}` — identyfikatory zerowane do dwóch cyfr (`question_1` → `"01"`).
**Stack:** `requests`, `bs4` (`BeautifulSoup`, `NavigableString`), `base64`, `json`, Whisper-1, `gpt-4o`.

## Wnioski dla własnego CTF

- Centralny endpoint: `POST {BASE}/verify` (lub per-zadaniowy `*_REPORT_URL`), body `{"task","apikey","answer"}`, odpowiedź zawiera `{FLG:...}`.
- Trzy warianty `answer`: string (CENZURA, mp3, robotid, ulica/miasto), dict (JSON, kategorie, arxiv), oraz nietypowe: `POST` form-data z `username`/`password`/`answer` (s01e01) i własny protokół `{"text","msgID"}` (s01e02).
- Powtarzalne pułapki: duplikat `apikey` w `answer` (s01e03), pominięcie katalogu `facts` (s02e04), zerowanie ID pytań (s02e05), wstrzykiwanie klucza API w ścieżkę pliku, klucz w formacie `AI_DEVS_API_KEY`.
- Stack bazowy: `requests` + `python-dotenv` + `bs4` + `zipfile`/`base64`; modele: `gpt-4o-mini`, `gpt-4o`, `whisper-1`, `dall-e-3`, `text-embedding-3-small` (nieużywany w tych zadaniach).
