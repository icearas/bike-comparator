# 🚵 Bike Parts Price Comparator

Narzędzie do porównywania cen części rowerowych między sklepami internetowymi. Automatycznie scrape'uje produkty, dopasowuje je przy użyciu AI i prezentuje różnice cenowe.

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
| Manetki | Shimano | Deore, SLX, XT, XTR, Saint |
| Manetki | SRAM | Eagle 70/90, GX, NX, X01, XX1 |
| Widelce | RockShox | Wszystkie modele |
| Widelce | FOX | Wszystkie modele |
| Dampery | RockShox | Wszystkie modele |
| Dampery | FOX | Wszystkie modele |

---

## 🗂 Struktura projektu

```
bike-comparator/
├── .env                        # Klucz API Anthropic (nie commitować!)
├── backend/
│   ├── models.py               # Modele SQLAlchemy (SQLite)
│   ├── main.py                 # Orkiestracja scrapingu
│   ├── seed_rules.py           # Wypełnienie reguł filtrowania
│   ├── ai_matcher.py           # Dopasowywanie produktów przez AI
│   └── scrapers/
│       ├── centrum_rowerowe.py # Scraper centrumrowerowe.pl
│       └── bike_discount.py    # Scraper bike-discount.de
└── frontend/                   # (w budowie)
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
- Node.js 25+

### Instalacja

```bash
# Sklonuj repo
git clone <repo-url>
cd bike-comparator

# Utwórz venv i zainstaluj zależności
python3.12 -m venv .venv
source .venv/bin/activate
pip install playwright beautifulsoup4 fastapi uvicorn sqlalchemy httpx anthropic python-dotenv requests

# Zainstaluj Chromium dla Playwright
playwright install chromium

# Ustaw klucz API
echo "ANTHROPIC_API_KEY=sk-ant-..." > .env
```

---

## 🚀 Uruchomienie

### Pierwsze uruchomienie

```bash
cd backend

# Utwórz bazę danych
python models.py

# Wypełnij reguły filtrowania
python seed_rules.py

# Uruchom scraping (zajmuje kilka minut)
python main.py

# Uruchom dopasowywanie AI
python ai_matcher.py
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
```

> ⚠️ Dopasowywanie AI wymaga stabilnego połączenia z Anthropic API. W razie problemów z siecią domową użyj mobilnego hotspotu.

### Reset matcha — pełne odświeżenie CR (gdy zmieniły się reguły scrapera)

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
```

> ⚠️ Produkty BD (`bike-discount.de`) nie wymagają czyszczenia — ich reguły nie zmieniają się.

---

## 🤖 Jak działa dopasowywanie AI

1. Produkty są filtrowane przez reguły z tabeli `filter_rules` (tylko wybrane marki i grupy)
2. Akcesoria (klocki, linki, płyny itp.) są odrzucane przez listę `SKIP_KEYWORDS`
3. Dla każdego produktu z CR szukamy kandydatów z BD tej samej marki i kategorii
4. Claude Haiku ocenia czy dwa produkty to ten sam produkt (zwraca JSON z `same` i `confidence`)
5. Dopasowania z confidence ≥ 92% są zapisywane do bazy

---

## 🛠 Przydatne komendy

### Eksport produktów do CSV

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

## 📝 TODO

- [ ] Dodać trzeci sklep: bikeinn.com
- [ ] Dodać czwarty sklep: sprint-rowery.pl
- [ ] Zbudować FastAPI backend z endpointami
- [ ] Zbudować React frontend z tabelą porównań
- [ ] Dodać automatyczne odświeżanie cen (cron)
- [ ] Dodać kursy walut PLN/EUR
- [ ] Dodać banner "Buy me a coffee"
- [ ] zamiast FastAPI uzyc Streamlit