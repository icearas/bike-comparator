# 🚵 Bike Parts Price Comparator

Narzędzie do porównywania cen części rowerowych między sklepami internetowymi. Automatycznie scrape'uje produkty, dopasowuje je przy użyciu AI i prezentuje różnice cenowe w aplikacji webowej Streamlit.

---

## 🛒 Obsługiwane sklepy

| Sklep | Waluta |
|-------|--------|
| centrumrowerowe.pl | PLN |
| bike-discount.de | EUR |

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
├── export_data.py              # Eksport dopasowań z SQLite → CSV
├── requirements.txt            # Zależności dla Streamlit Cloud
├── data/
│   └── matched_products.csv   # Dane do aplikacji (generowane przez export_data.py)
└── backend/
    ├── models.py               # Modele SQLAlchemy (SQLite)
    ├── main.py                 # Orkiestracja scrapingu
    ├── seed_rules.py           # Wypełnienie reguł filtrowania
    ├── ai_matcher.py           # Dopasowywanie produktów przez AI
    └── scrapers/
        ├── centrum_rowerowe.py # Scraper centrumrowerowe.pl
        └── bike_discount.py    # Scraper bike-discount.de
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

# Uruchom scraping (zajmuje kilka minut)
python main.py

# Uruchom dopasowywanie AI
python ai_matcher.py

# Eksportuj dopasowania do CSV
cd ..
python export_data.py
```

### Kolejne uruchomienia (odświeżenie cen)

```bash
cd backend
source ../.venv/bin/activate

# Odśwież ceny
python main.py

# Wyczyść stare dopasowania i dopasuj ponownie
python3 -c "from models import SessionLocal, MatchedProduct; db = SessionLocal(); db.query(MatchedProduct).delete(); db.commit(); db.close()"
python ai_matcher.py

# Eksportuj do CSV
cd ..
python export_data.py
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

# 5. Eksportuj do CSV
cd ..
python export_data.py
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

- **Filtr kategorii** — pokaż tylko wybraną kategorię części
- **Kurs EUR/PLN** — przelicz ceny BD na złotówki po aktualnym kursie
- **Min. oszczędność (%)** — ukryj produkty poniżej zadanego progu
- **Tylko tańsze w BD** — pokaż wyłącznie produkty opłacalne do zamówienia z Niemiec
- **Metryki** — liczba dopasowań, ile taniej w BD, średnia i max oszczędność
- **Tabela z linkami** — bezpośrednie linki do produktu na obu sklepach

### Deploy na Streamlit Community Cloud (bezpłatny)

1. Upewnij się, że w repo jest aktualny `data/matched_products.csv` (wygenerowany przez `export_data.py`)
2. Wejdź na [share.streamlit.io](https://share.streamlit.io) i zaloguj się przez GitHub
3. Kliknij **New app** → wskaż repo → ustaw **Main file path**: `app.py`
4. Kliknij **Deploy**

> Po każdym odświeżeniu cen: uruchom `python export_data.py`, zacommituj i pushuj zaktualizowany CSV — Streamlit Cloud automatycznie pobierze nowe dane.

---

## 🤖 Jak działa dopasowywanie AI

1. Produkty są filtrowane przez reguły z tabeli `filter_rules` (tylko wybrane marki i grupy)
2. Części serwisowe, narzędzia i akcesoria (klocki, linki, rebuild kity, narzędzia, tokeny, płyny itp.) są odrzucane przez rozszerzoną listę `SKIP_KEYWORDS`
3. Dla każdego produktu z CR szukamy kandydatów z BD tej samej marki i kategorii
4. Pre-filter po numerach modelu (np. `RD-M8100`, `BL-M9220`) zawęża kandydatów do max 3 przed wywołaniem AI
5. Claude Haiku ocenia czy dwa produkty to ten sam produkt (zwraca JSON z `same` i `confidence`)
6. Dopasowania z confidence ≥ 95% są zapisywane do bazy

**Parametry matchera** (`ai_matcher.py`):

| Parametr | Wartość | Opis |
|----------|---------|------|
| `CONFIDENCE_THRESHOLD` | 0.95 | Minimalny próg pewności dopasowania |
| `PARALLEL_CALLS` | 3 | Liczba równoległych wywołań Claude API |
| `MODEL` | claude-haiku-4-5 | Model używany do porównań |

---

## 🛠 Przydatne komendy

### Eksport dopasowań do CSV (dla Streamlit)

```bash
cd ~/bike-comparator
source .venv/bin/activate
python export_data.py
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

- [ ] Dodać trzeci sklep: bikeinn.com
- [ ] Dodać czwarty sklep: sprint-rowery.pl
- [ ] Poprawić matchowanie — więcej dopasowanych produktów
- [ ] Dodać automatyczne odświeżanie cen (cron / GitHub Actions)
- [ ] Dodać pobieranie aktualnego kursu EUR/PLN z API
