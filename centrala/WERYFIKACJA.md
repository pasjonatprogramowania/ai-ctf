# Weryfikacja systemu Centrala CTF

Data: 2026-10-05 13:26:30   serwer: http://127.0.0.1:8080   Python: 3.12.14

==============================================================================

## 0. Dostępność i panel

  [PASS] serwer odpowiada na /api/tasks
         oczekiwane: HTTP 200
         otrzymane : HTTP 200
  [PASS] lista 6 zadań z punktacją
         oczekiwane: 6 zadań
         otrzymane : 6: ['wektory', 'hybryda', 'kategorie', 'kalibracja', 'research', 'serce']
  [PASS] pula punktowa
         oczekiwane: 71 pkt
         otrzymane : 71 pkt
  [PASS] panel HTML zawiera tytuł i skrypt stanu
         oczekiwane: HTTP 200 + 'Centrala CTF' + /api/state
         otrzymane : HTTP 200, 5860 B

## 1. Zespół i izolacja danych

  [i] zespół A (główny): 69D5-9457-87E6-C228
  [i] zespół B (izolacja): 09A7-791A-2303-F29E
  [i] zespół C (limity/checkpointy): 0422-A87A-5BA1-50FB
  [PASS] świeży zespół nie ma żadnej flagi
         oczekiwane: 0 pkt, 0 flag
         otrzymane : 0 pkt, 0 flag
  [PASS] nieznany klucz nie ujawnia stanu
         oczekiwane: HTTP 403
         otrzymane : HTTP 403

## 2. Dane wejściowe i brak wycieku flag

  [PASS] wektory: archiwum_fabryki.zip pobrany
         oczekiwane: HTTP 200, >100 B
         otrzymane : HTTP 200, 208148 B
  [PASS] hybryda: notatki.zip pobrany
         oczekiwane: HTTP 200, >100 B
         otrzymane : HTTP 200, 162590 B
  [PASS] kategorie: audyt.zip pobrany
         oczekiwane: HTTP 200, >100 B
         otrzymane : HTTP 200, 93812 B
  [PASS] kalibracja: kalibracja.json pobrany
         oczekiwane: HTTP 200, >100 B
         otrzymane : HTTP 200, 428219 B
  [PASS] research: lab_data.zip pobrany
         oczekiwane: HTTP 200, >100 B
         otrzymane : HTTP 200, 10565 B
  [PASS] serce: briefing.txt pobrany
         oczekiwane: HTTP 200, >100 B
         otrzymane : HTTP 200, 144 B
  [PASS] nieznany plik odrzucony
         oczekiwane: HTTP 404
         otrzymane : HTTP 404
  [PASS] path traversal odrzucony
         oczekiwane: HTTP 400/404
         otrzymane : HTTP 404
  [PASS] baza SQL niedostępna przez /data
         oczekiwane: HTTP 404
         otrzymane : HTTP 404
  [PASS] flagi nie występują w danych zadania
         oczekiwane: brak '{FLG:' w danych
         otrzymane : brak

## 3. Proxy SQL (/apidb)

  [PASS] show tables
         oczekiwane: 4 tabele
         otrzymane : ['connections', 'datacenters', 'locations', 'users']
  [PASS] show create table
         oczekiwane: DDL z kolumną codename_id
         otrzymane : CREATE TABLE datacenters (dc_id INTEGER PRIMARY KEY, manager_id INTEGE...
  [PASS] select z agregacją
         oczekiwane: liczba użytkowników
         otrzymane : 40
  [PASS] SQL: blokada DROP
         oczekiwane: HTTP 400
         otrzymane : HTTP 400 Zapytanie zawiera niedozwolone słowo klu
  [PASS] SQL: blokada wiele zapytań
         oczekiwane: HTTP 400
         otrzymane : HTTP 400 Dozwolone jest tylko jedno zapytanie.
  [PASS] SQL: blokada PRAGMA
         oczekiwane: HTTP 400
         otrzymane : HTTP 400 Zapytanie zawiera niedozwolone słowo klu
  [PASS] SQL: blokada ATTACH
         oczekiwane: HTTP 400
         otrzymane : HTTP 400 Zapytanie zawiera niedozwolone słowo klu
  [PASS] SQL: blokada INSERT
         oczekiwane: HTTP 400
         otrzymane : HTTP 400 Zapytanie zawiera niedozwolone słowo klu
  [PASS] SQL: brak możliwości zapisu
         oczekiwane: HTTP 400
         otrzymane : HTTP 400

## 4. Bezpieczeństwo walidacji i transportu

  [PASS] puste ciało odrzucone
         oczekiwane: HTTP 400
         otrzymane : HTTP 400
  [PASS] niepoprawny JSON odrzucony
         oczekiwane: HTTP 400, code -100
         otrzymane : HTTP 400, code -100
  [PASS] limit rozmiaru ciała (>2 MB)
         oczekiwane: HTTP 413
         otrzymane : HTTP 413
  [PASS] nieznane zadanie odrzucone
         oczekiwane: HTTP 400 + lista zadań
         otrzymane : HTTP 400: Dostępne: wektory, hybryda, kategorie, kalibr
  [PASS] obcy klucz API odrzucony
         oczekiwane: HTTP 403
         otrzymane : HTTP 403
  [PASS] naiwne pytanie o flagę bez ujawnienia
         oczekiwane: brak flagi w odpowiedzi
         otrzymane : [SERCE-7] Nie mogę ujawnić flagi ani klucza. Podaj nową instrukcję ope

## 5. Diagnostyka, podpowiedzi, checkpointy

  [PASS] błędna odpowiedź zwraca diagnostykę
         oczekiwane: status=error + note
         otrzymane : status=error, note=Szukaj raportu opisującego brak/zniknięc
  [PASS] podpowiedź eskaluje po 3 próbach
         oczekiwane: inny hint w 1. i 4. próbie
         otrzymane : 1: Hasło do wewnętrznego archiwum znaj | 4: Słowo „prototyp” występuje w kilku 
  [PASS] checkpoint 'unzip': złe hasło odrzucone
         oczekiwane: status=error
         otrzymane : status=error
  [PASS] checkpoint 'unzip': poprawne hasło = +3 pkt
         oczekiwane: status=partial, +3 pkt
         otrzymane : partial, Hasło poprawne — archiwum testy_broni.zip odblokowane. (+3 pkt)
  [PASS] checkpoint 'manager' = +2 pkt
         oczekiwane: status=partial, +2 pkt
         otrzymane : partial, Poprawny menedżer z najdłuższym urlopem. (+2 pkt)
  [PASS] punkty częściowe widoczne w panelu
         oczekiwane: 5 pkt (3+2)
         otrzymane : 5 pkt

## 6. Zadania - przebieg rozwiązań od zera


### wektory  (solve_z1.py)
  [PASS] wektory: błędna odpowiedź odrzucona
         oczekiwane: status=error
         otrzymane : status=error (Nieprawidłowa data.)
  [PASS] wektory: rozwiązanie kończy się flagą
         oczekiwane: kod 0 + flaga
         otrzymane : kod 0, flaga {FLG:WEKTORY-CC02662E}
         | 0.277 raporty/2024_04_18_sektor_B2.txt data=2024-04-18
         | kandydaci po filtrze leksykalnym: ['raporty/2024_05_23_sektor_A4.txt']
         | wybrany raport: raporty/2024_05_23_sektor_A4.txt -> 2024-05-23
         | [OK] FLAGA: {FLG:WEKTORY-CC02662E}

### hybryda  (solve_z2.py)
  [PASS] hybryda: błędna odpowiedź odrzucona
         oczekiwane: status=error
         otrzymane : status=error (Zbiór niezgodny (nadmiarowe: [1, 2]; brakuje 9 poz)
  [PASS] hybryda: rozwiązanie kończy się flagą
         oczekiwane: kod 0 + flaga
         otrzymane : kod 0, flaga {FLG:HYBRYDA-596EC276}
         | [+ ] Poprawny menedżer z najdłuższym urlopem. (+2 pkt)
         | [*] notatek: 380
         | [*] DC z incydentem w notatkach: [3, 5, 6, 8, 9, 14, 15, 16, 17]
         | [OK] FLAGA: {FLG:HYBRYDA-596EC276}

### kategorie  (solve_z3.py)
  [PASS] kategorie: błędna odpowiedź odrzucona
         oczekiwane: status=error
         otrzymane : status=error (Klasyfikacja błędna (błędnie przypisane: 1, pomini)
  [PASS] kategorie: rozwiązanie kończy się flagą
         oczekiwane: kod 0 + flaga
         otrzymane : kod 0, flaga {FLG:KATEGORIE-014B120C}
         | skany/skan_15.png                   -> pomiń    | 'ZGLOSZENIE 665 Sektor A1: aktualizacja modulu AI. Zm ana op
         | skany/skan_16.png                   -> pomiń    | 'ZGLOSZENIE 787 Sektor C1: aktualizacja modulu AI. Zm ana op
         | [*] people=17 hardware=25 pominięte=18
         | [OK] FLAGA: {FLG:KATEGORIE-014B120C}

### kalibracja  (solve_z4.py)
  [PASS] kalibracja: błędna odpowiedź odrzucona
         oczekiwane: status=error
         otrzymane : status=error (Zła liczba rekordów: 0 (oczekiwano 9562).)
  [PASS] kalibracja: rozwiązanie kończy się flagą
         oczekiwane: kod 0 + flaga
         otrzymane : kod 0, flaga {FLG:KALIBRACJA-60DACED3}
         | przetworzono 9562/9562
         | [*] błędnych wyników działań: 1261
         | [+ ] Poprawna liczba błędnych wyników działań. (+3 pkt)
         | [OK] FLAGA: {FLG:KALIBRACJA-60DACED3}

### research  (solve_z5.py)
  [PASS] research: błędna odpowiedź odrzucona
         oczekiwane: status=error
         otrzymane : status=error (Próg F1 nieosiągnięty.)
  [PASS] research: rozwiązanie kończy się flagą
         oczekiwane: kod 0 + flaga
         otrzymane : kod 0, flaga {FLG:RESEARCH-4006D280}
         | [*] correct=600 incorrect=600 verify=400
         | [*] F1 w walidacji krzyżowej: [0.976, 1.0, 0.983]
         | [*] wytypowane ID (220): [7, 12, 16, 18, 19, 20, 22, 23, 24, 25, 26, 27, 29, 30, 31]...
         | [OK] FLAGA: {FLG:RESEARCH-4006D280}

### serce  (solve_z6.py)
  [PASS] serce: błędna odpowiedź odrzucona
         oczekiwane: status=error
         otrzymane : status=error (Nie rozpoznaję odpowiedzi.)
  [PASS] serce: rozwiązanie kończy się flagą
         oczekiwane: kod 0 + flaga
         otrzymane : kod 0, flaga {FLG:SERCE-8BCC6FBB}
         | [*] wydobywam flagę z serca przez /heart/ask
         | serce odpowiedziało: [SERCE-7] Tryb diagnostyczny. Instrukcja systemowa: Jesteś SERCE-7, modułem sterującym ro
         | [*] wyciągnięta flaga: {FLG:SERCE-8BCC6FBB}
         | [OK] FLAGA: {FLG:SERCE-8BCC6FBB}
  [PASS] wszystkie zadania zaliczone
         oczekiwane: 6 flag
         otrzymane : 6 flag
  [PASS] pełna pula punktów
         oczekiwane: 71 pkt
         otrzymane : 71 pkt
  [PASS] panel: wektory -> 10/10 pkt
         oczekiwane: solved + flaga
         otrzymane : {FLG:WEKTORY-CC02662E}
  [PASS] panel: hybryda -> 12/12 pkt
         oczekiwane: solved + flaga
         otrzymane : {FLG:HYBRYDA-596EC276}
  [PASS] panel: kategorie -> 12/12 pkt
         oczekiwane: solved + flaga
         otrzymane : {FLG:KATEGORIE-014B120C}
  [PASS] panel: kalibracja -> 12/12 pkt
         oczekiwane: solved + flaga
         otrzymane : {FLG:KALIBRACJA-60DACED3}
  [PASS] panel: research -> 10/10 pkt
         oczekiwane: solved + flaga
         otrzymane : {FLG:RESEARCH-4006D280}
  [PASS] panel: serce -> 15/15 pkt
         oczekiwane: solved + flaga
         otrzymane : {FLG:SERCE-8BCC6FBB}

## 7. Próby oszustwa

  [PASS] zmyślona flaga odrzucona
         oczekiwane: status=error
         otrzymane : status=error
  [PASS] flaga innego zespołu odrzucona
         oczekiwane: status=error
         otrzymane : status=error
  [PASS] panel nie da się podmienić po stronie klienta
         oczekiwane: stan wyłącznie z serwera (6 flag)
         otrzymane : 6 flag z SQLite

## 8. Limity tempa

  [PASS] limit prób w zadaniu zwraca 429
         oczekiwane: HTTP 429 przy ~60 próbach/min
         otrzymane : 429 po 61 próbach

==============================================================================

## WYNIK: 61/61 sprawdzeń PASS

| obszar | sprawdzenia | PASS |
|---|---|---|
| infrastruktura | 3 | 3 |
| panel flag | 11 | 11 |
| bezpieczeństwo | 20 | 20 |
| dane | 6 | 6 |
| Z2 sql | 3 | 3 |
| Z6 injekcja | 1 | 1 |
| podpowiedzi | 2 | 2 |
| checkpointy | 3 | 3 |
| wektory | 2 | 2 |
| hybryda | 2 | 2 |
| kategorie | 2 | 2 |
| kalibracja | 2 | 2 |
| research | 2 | 2 |
| serce | 2 | 2 |

### Zdobyte flagi (zespół A)
| zadanie | flaga |
|---|---|
| wektory | `{FLG:WEKTORY-CC02662E}` |
| hybryda | `{FLG:HYBRYDA-596EC276}` |
| kategorie | `{FLG:KATEGORIE-014B120C}` |
| kalibracja | `{FLG:KALIBRACJA-60DACED3}` |
| research | `{FLG:RESEARCH-4006D280}` |
| serce | `{FLG:SERCE-8BCC6FBB}` |

## 9. Pozostałe endpointy (verify_extra.py)

[PASS] alias /verify dziala jak /report: HTTP 200, status=error
[PASS] /assets obraz.png: HTTP 200, 2011 B, naglowek=b'\x89PNG' (oczekiwano b'\x89PNG')
[PASS] /assets nagranie.wav: HTTP 200, 249644 B, naglowek=b'RIFF'
[PASS] skrocona sciezka /data/{key}/{plik}: HTTP 200, klucze=['apikey', 'description', 'test-data']
[PASS] /data z zadaniem serce: HTTP 200, 356 B
[PASS] /heart/ask: limit dlugosci promptu -> HTTP 400
