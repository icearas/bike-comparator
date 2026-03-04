# 🚵 Bike Parts Price Comparator

Narzędzie do porównywania cen części rowerowych między sklepami internetowymi. Automatycznie scrape'uje produkty, dopasowuje je przy użyciu AI i prezentuje różnice cenowe w aplikacji webowej Streamlit.

---

## 🛒 Obsługiwane sklepy

| Sklep | Waluta | Rola |
|-------|--------|------|
| centrumrowerowe.pl | PLN | baza katalogu (CR) |
| bike-discount.de | EUR | porównanie (BD) |
| rowerowy.com | PLN | porównanie (RW) |

---

## 📦 Obsługiwane kategorie i marki

| Kategoria | Marka | Grupy |
|-----------|-------|-------|
| Przerzutki tylne | Shimano | Deore, SLX, XT, XTR, Saint |
| Przerzutki tylne | SRAM | Eagle 70/90, GX, NX, X01, XX1 |
| Hamulce tarczowe | Shimano | Deore, SLX, XT, XTR, Saint |
| Hamulce tarczowe | SRAM | Guide, Maven, DB8 |
| Kasety | Shimano | Deore, SLX, XT, XTR |
| Kasety | SRAM | Eagle 70/90, GX, NX, X01, XX1 |
| Łańcuchy | Shimano | Deore, SLX, XT, XTR |
| Łańcuchy | SRAM | Eagle (wszystkie) |
| Widelce | RockShox | Wszystkie modele |
| Widelce | FOX | Wszystkie modele |
| Dampery | RockShox | Wszystkie modele |
| Dampery | FOX | Wszystkie modele |

---

## 🗂 Struktura projektu

```
bike-comparator/
├── .env                        # Klucz API Anthropic (nie commitować!)
├── app.py                      # Aplikacja Streamlit (frontend)
├── requirements.txt            # Zależności dla Streamlit Cloud
├── data/
│   ├── cr_all.csv             # Pełny katalog CR po filtrach (generowany przez export_cr.py)
│   ├── matched_products.csv   # Dopasowania CR↔BD (generowane przez ai_matcher.py)
│   └── rw_matched.csv         # Dopasowania CR↔RW (generowane przez rw_matcher.py)
└── backend/
    ├── models.py               # Modele SQLAlchemy (SQLite)
    ├── main.py                 # Orkiestracja scrapingu (CR + BD + RW)
    ├── seed_rules.py           # Wypełnienie reguł filtrowania
    ├── ai_matcher.py           # Dopasowywanie CR↔BD przez AI → DB
    ├── rw_matcher.py           # Dopasowywanie CR↔RW przez AI → data/rw_matched.csv
    ├── export_cr.py            # Eksport filtrowanych produktów CR z DB → data/cr_all.csv
    └── scrapers/
        ├── centrum_rowerowe.py # Scraper centrumrowerowe.pl
        ├── bike_discount.py    # Scraper bike-discount.de
        └── rowerowy.py         # Scraper rowerowy.com (infinite scroll, Playwright)
```

---

## 🗄 Baza danych

SQLite (`backend/bike_comparator.db`) z tabelami:

| Tabela | Opis |
|--------|------|
| `products` | Produkty ze wszystkich sklepów |
| `matched_products` | Dopasowane pary produktów między sklepami |
| `filter_rules` | Reguły filtrowania (marki i grupy do śledzenia) |

---

## ⚙️ Setup

### Wymagania

- Python 3.12+

### Instalacja

```bash
# Sklonuj repo
git clone <repo-url>
cd bike-comparator

# Utwórz venv i zainstaluj zależności
python3.12 -m venv .venv
source .venv/bin/activate
pip install playwright beautifulsoup4 sqlalchemy httpx anthropic python-dotenv requests streamlit pandas

# Zainstaluj Chromium dla Playwright
playwright install chromium

# Ustaw klucz API
echo "ANTHROPIC_API_KEY=sk-ant-..." > .env
```

---

## 🚀 Uruchomienie

### Pierwsze uruchomienie (od zera)

```bash
cd backend
source ../.venv/bin/activate

# Utwórz bazę danych
python models.py

# Wypełnij reguły filtrowania
python seed_rules.py

# Uruchom scraping wszystkich 3 sklepów (kilka–kilkanaście minut)
python main.py

# Dopasuj CR↔BD (zapisuje do DB)
python ai_matcher.py

# Dopasuj CR↔RW (zapisuje do data/rw_matched.csv)
python rw_matcher.py

# Eksportuj katalog CR do CSV
python export_cr.py

# Eksportuj dopasowania CR↔BD do CSV (patrz Przydatne komendy)
```

### Kolejne uruchomienia (odświeżenie cen)

```bash
cd backend
source ../.venv/bin/activate

# Odśwież ceny (wszystkie 3 sklepy)
python main.py

# Wyczyść stare dopasowania CR↔BD i dopasuj ponownie
python3 -c "from models import SessionLocal, MatchedProduct; db = SessionLocal(); db.query(MatchedProduct).delete(); db.commit(); db.close()"
python ai_matcher.py

# Dopasuj ponownie CR↔RW (nadpisuje rw_matched.csv)
python rw_matcher.py

# Eksportuj katalog CR do CSV
python export_cr.py

# Eksportuj dopasowania CR↔BD do data/matched_products.csv (patrz Przydatne komendy)
```

> ⚠️ Dopasowywanie AI wymaga stabilnego połączenia z Anthropic API. W razie problemów z siecią domową użyj mobilnego hotspotu.

### Reset matcha — pełne odświeżenie produktów (gdy zmieniły się reguły scrapera)

Jeśli zmieniły się wykluczenia w scraper'ze (np. `SHIMANO_OLD_MODELS`, `SKIP_KEYWORDS`) i chcesz, żeby baza odzwierciedlała aktualny stan — **samo `python main.py` nie wystarczy**, bo `save_products()` używa upsert (nie usuwa starych rekordów).

Wymagana kolejność:

```bash
# 1. Wyczyść dopasowania i stare produkty CR
sqlite3 /Users/arkadiuszmichnej/bike-comparator/backend/bike_comparator.db \
  "DELETE FROM matched_products; DELETE FROM products WHERE shop = 'centrumrowerowe.pl';"

# 2. Sprawdź czy DELETE poszło (oba wyniki powinny być 0)
sqlite3 /Users/arkadiuszmichnej/bike-comparator/backend/bike_comparator.db \
  "SELECT COUNT(*) FROM matched_products; SELECT COUNT(*) FROM products WHERE shop = 'centrumrowerowe.pl';"

# 3. Re-scrape CR
cd backend
python main.py

# 4. Re-match
python ai_matcher.py

# 5. Eksportuj katalog CR do CSV
python export_cr.py

# 6. Eksportuj dopasowania do data/matched_products.csv (patrz Przydatne komendy)
```

> ⚠️ Jeśli zmieniły się reguły w scraperze BD (np. `SUSPENSION_SKIP`, `ALLOWED_GROUPS`) — należy wyczyścić i ponownie zescrapować również produkty BD, zastępując `centrumrowerowe.pl` przez `bike-discount.de` w krokach powyżej.

---

## 🖥 Aplikacja Streamlit

### Uruchomienie lokalne

```bash
source .venv/bin/activate
streamlit run app.py
```

Aplikacja otworzy się w przeglądarce pod adresem `http://localhost:8501`.

### Funkcje aplikacji

- **Pełny katalog CR** — baza to wszystkie produkty z centrumrowerowe.pl po filtrach (136 produktów); BD i RW match pokazywany tam gdzie istnieje
- **Wyszukiwarka** — pole tekstowe filtruje po nazwie produktu CR, BD lub RW
- **Filtr kategorii** — pokaż tylko wybraną kategorię części
- **Kurs EUR/PLN** — automatycznie pobierany z API NBP (kurs średni tabela A, odświeżany co 1h); można ręcznie nadpisać
- **Filtr kategorii** — pokaż tylko wybraną kategorię części
- **Filtr marki** — multiselect: Shimano, SRAM, RockShox, FOX
- **Wyszukiwarka** — pole tekstowe filtruje po nazwie produktu (CR, BD lub RW)
- **Tabela z linkami** — kolumny BD i RW obok siebie; linki do produktu we wszystkich 3 sklepach

### Deploy na Streamlit Community Cloud (bezpłatny)

1. Upewnij się, że w repo są aktualne `data/cr_all.csv` i `data/matched_products.csv`
2. Wejdź na [share.streamlit.io](https://share.streamlit.io) i zaloguj się przez GitHub
3. Kliknij **New app** → wskaż repo → ustaw **Main file path**: `app.py`
4. Kliknij **Deploy**

> Po każdym odświeżeniu cen: uruchom `python export_cr.py`, `python rw_matcher.py` i wyeksportuj `matched_products.csv`, zacommituj wszystkie trzy pliki CSV i pushuj — Streamlit Cloud automatycznie pobierze nowe dane.

---

## 🤖 Jak działa dopasowywanie AI

Dwa niezależne matchery: `ai_matcher.py` (CR↔BD, wyniki w DB) i `rw_matcher.py` (CR↔RW, wyniki w `data/rw_matched.csv`). Oba działają identycznie:

1. Produkty są filtrowane przez reguły z tabeli `filter_rules` (tylko wybrane marki i grupy)
2. Części serwisowe, narzędzia i akcesoria (klocki, linki, rebuild kity, narzędzia, tokeny, płyny itp.) są odrzucane przez rozszerzoną listę `SKIP_KEYWORDS`
3. Dla każdego produktu z CR szukamy kandydatów z BD/RW tej samej marki i kategorii
4. Pre-filter po **grade zawieszenia** — FOX (Factory/Performance Elite/E-Optimized/Performance/Rhythm) i RockShox (Ultimate/Select+/Select/R) — zapobiega krzyżowaniu grade'ów; FOX bez grade'u (`fox_ungraded`) nie jest matchowany
5. Pre-filter po numerach modelu (np. `RD-M8100`, `BL-M9220`) zawęża kandydatów do max 3 przed wywołaniem AI
6. Claude Haiku ocenia czy dwa produkty to ten sam produkt (zwraca JSON z `same` i `confidence`); wersje dampera (Charger 3 vs Charger 3.1) traktowane jako różne produkty
7. Dopasowania z confidence ≥ 95% są zapisywane (CR↔BD → DB, CR↔RW → CSV)

**Parametry matchera** (`ai_matcher.py`):

| Parametr | Wartość | Opis |
|----------|---------|------|
| `CONFIDENCE_THRESHOLD` | 0.95 | Minimalny próg pewności dopasowania |
| `PARALLEL_CALLS` | 3 | Liczba równoległych wywołań Claude API |
| `MODEL` | claude-haiku-4-5 | Model używany do porównań |

---

## 🛠 Przydatne komendy

### Eksport danych do CSV (dla Streamlit)

```bash
cd ~/bike-comparator/backend
source ../.venv/bin/activate

# Eksport katalogu CR (przefiltrowane produkty z URLami)
python export_cr.py

# Eksport dopasowań CR↔BD
python3 -c "
import csv
from models import SessionLocal, MatchedProduct
from datetime import timezone

db = SessionLocal()
rows = db.query(MatchedProduct).all()
db.close()

with open('../data/matched_products.csv', 'w', newline='', encoding='utf-8') as f:
    w = csv.writer(f)
    w.writerow(['category','cr_name','cr_price_pln','cr_url','bd_name','bd_price_eur','bd_url','match_confidence','matched_at'])
    for r in rows:
        w.writerow([r.category, r.cr_name, r.cr_price_pln, r.cr_url, r.bd_name, r.bd_price_eur, r.bd_url, r.match_confidence, r.matched_at])
print(f'Wyeksportowano {len(rows)} dopasowań')
"
```

### Eksport surowych produktów do CSV (diagnostyka)

```bash
cd ~/bike-comparator/backend
python3 -c "
import sqlite3, csv

conn = sqlite3.connect('bike_comparator.db')
cursor = conn.cursor()

cursor.execute(\"SELECT name, category, price FROM products WHERE shop='centrumrowerowe.pl' ORDER BY category, name\")
with open('cr_products.csv', 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerow(['name', 'category', 'price_pln'])
    writer.writerows(cursor.fetchall())

cursor.execute(\"SELECT name, category, price FROM products WHERE shop='bike-discount.de' ORDER BY category, name\")
with open('bd_products.csv', 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerow(['name', 'category', 'price_eur'])
    writer.writerows(cursor.fetchall())

conn.close()
print('Gotowe: cr_products.csv i bd_products.csv')
"
```

### Wyczyszczenie bazy i scraping od nowa

```bash
python3 -c "
from models import SessionLocal, Product
db = SessionLocal()
db.query(Product).delete()
db.commit()
db.close()
print('Wyczyszczono')
"
python main.py
```

---

## 🌐 Deploy

Aplikacja działa na Streamlit Community Cloud:
`https://bike-comparator-bhwfr2hvgau63gr6cbfvse.streamlit.app`

Repo jest **prywatne** — Streamlit ma dostęp przez GitHub OAuth (połączone konto `icearas`).
Apka jest publiczna (Settings → Sharing → Public w panelu Streamlit).

### Uwagi deployment
- `uv.lock` **nie jest w repo** — Streamlit używa tylko `requirements.txt`
- `.python-version` = `3.12`, `pyproject.toml` `requires-python = ">=3.12"`
- Linki w tabeli używają `rel="noreferrer noopener"` — centrumrowerowe.pl blokuje ruch z referrerem `streamlit.app`

---

## 📝 TODO

- [ ] Dodać czwarty sklep: bikeinn.com lub sprint-rowery.pl
- [ ] Ujednolicić nazwy produktów między sklepami (normalizacja nazw) — CR używa pełnych polskich nazw, RW skraca (np. "Przerzutka XT RD-M8100"), BD używa angielskich; utrudnia to matching i prezentację
- [ ] Poprawić matchowanie — więcej dopasowanych produktów (szczególnie hamulce w RW)
- [ ] Dodać grupę Shimano GRX (gravel) i jej odpowiedniki SRAM (Rival eTap AXS / Force eTap AXS) — scraper + reguły filtrowania + matching
- [ ] Dodać czwarty sklep: bikeinn.com lub sprint-rowery.pl
- [ ] Dodać automatyczne odświeżanie cen (cron / GitHub Actions)
- [ ] Refaktor DB — generyczny model dopasowań par sklepów (gdy pojawi się 4. sklep)
