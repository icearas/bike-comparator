# 🚵 Bike Parts Price Comparator

Narzędzie do porównywania cen części rowerowych między sklepami internetowymi. Automatycznie scrape'uje produkty, dopasowuje je między sklepami przy użyciu AI i prezentuje różnice cenowe.

## Obsługiwane sklepy

- **centrumrowerowe.pl** (ceny w PLN)
- **bike-discount.de** (ceny w EUR)

## Obsługiwane kategorie

- Przerzutki tylne
- Hamulce
- Kasety
- Łańcuchy
- Manetki
- Amortyzatory / Dampery
- Widelce

## Obsługiwane marki i grupy

| Marka | Grupy |
|-------|-------|
| Shimano | Deore, SLX, XT, XTR |
| SRAM | Eagle 70, Eagle 90, GX, X0, XX, NX, X01, XX1 |
| RockShox | Wszystkie modele (ZEB, Pike, Lyrik, SID, Judy...) |
| FOX | Wszystkie modele |
| SRAM (hamulce) | Guide, Maven, DB8 |

## Struktura projektu

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

## Baza danych

SQLite (`backend/bike_comparator.db`) z tabelami:

- **products** – produkty ze wszystkich sklepów
- **matched_products** – dopasowane pary produktów między sklepami
- **filter_rules** – reguły filtrowania (jakie marki/grupy śledzić)

## Setup

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

### Kolejne uruchomienia

```bash
# Odśwież ceny (scraping)
python main.py

# Wyczyść stare dopasowania i dopasuj ponownie
python3 -c "from models import SessionLocal, MatchedProduct; db = SessionLocal(); db.query(MatchedProduct).delete(); db.commit(); db.close()"
python ai_matcher.py
```

## Jak działa dopasowywanie

1. Produkty są filtrowane przez reguły z tabeli `filter_rules` (tylko wybrane marki i grupy)
2. Akcesoria (klocki, linki, płyny itp.) są odrzucane przez listę `SKIP_KEYWORDS`
3. Dla każdego produktu z CR szukamy kandydatów z BD tej samej marki i kategorii
4. Claude Haiku ocenia czy dwa produkty to ten sam produkt (zwraca JSON z `same` i `confidence`)
5. Dopasowania z confidence ≥ 85% są zapisywane do bazy

## Zarządzanie regułami filtrowania

Reguły filtrowania są w tabeli `filter_rules`. Możesz je edytować bezpośrednio w bazie lub modyfikować `seed_rules.py` i uruchomić ponownie:

```bash
python seed_rules.py
```

Struktura reguły:
- `category` – kategoria produktu (przerzutki, hamulce, kasety...)
- `brand` – marka (SHIMANO, SRAM, ROCKSHOX, FOX)
- `model_keyword` – słowo kluczowe w nazwie (np. "deore xt", "gx eagle") lub `NULL` = wszystkie modele marki
- `active` – 1/0 czy reguła jest aktywna

## Znane problemy

- **bike-discount.de** nie podaje marki w nazwie produktu – marka jest wyciągana z URL
- Kategorie różnią się między sklepami: CR używa `amortyzatory`, BD używa `dampery`
- Wymagane stabilne połączenie internetowe podczas dopasowywania AI (Anthropic API)

## TODO

- [ ] Dodać widelce do scrapora centrumrowerowe.pl
- [ ] Dodać trzeci sklep: bikeinn.com
- [ ] dodac czwarty sklep: sprint-rowery.pl
- [ ] Zbudować FastAPI backend z endpointami
- [ ] Zbudować React frontend z tabelą porównań
- [ ] Dodać automatyczne odświeżanie cen (cron)
- [ ] Dodać kursy walut PLN/EUR
- [ ] dodac banner z buy a coffe 

## CSV file download

cd ~/bike-comparator/backend
python3 -c "
import sqlite3
import csv

conn = sqlite3.connect('bike_comparator.db')
cursor = conn.cursor()

cursor.execute('''
    SELECT name, category, price 
    FROM products 
    WHERE shop=\"centrumrowerowe.pl\"
    ORDER BY category, name
''')
with open('cr_products.csv', 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerow(['name', 'category', 'price_pln'])
    writer.writerows(cursor.fetchall())

cursor.execute('''
    SELECT name, category, price
    FROM products
    WHERE shop=\"bike-discount.de\"
    ORDER BY category, name
''')
with open('bd_products.csv', 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerow(['name', 'category', 'price_eur'])
    writer.writerows(cursor.fetchall())

conn.close()
print('Gotowe: cr_products.csv i bd_products.csv')
"

## Czyszczenie bazy i puszczanie sracpu od nowa

python3 -c "
from models import SessionLocal, Product
db = SessionLocal()
db.query(Product).delete()
db.commit()
db.close()
print('Wyczyszczono')
"
python main.py