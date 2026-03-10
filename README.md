# 🚵 Bike Parts Price Comparator

Narzędzie do porównywania cen części rowerowych między sklepami internetowymi. Automatycznie scrape'uje produkty, dopasowuje je przy użyciu AI i prezentuje różnice cenowe w aplikacji webowej Streamlit.

**Live:** https://bike-comparator-bhwfr2hvgau63gr6cbfvse.streamlit.app

---

## 🛒 Obsługiwane sklepy

| Sklep | Slug | Waluta |
|-------|------|--------|
| centrumrowerowe.pl | `cr` | PLN |
| bike-discount.de | `bd` | EUR |
| mtbiker.pl | `mtb` | PLN |
| bikeinn.com | `bi` | PLN |

---

## 📦 Obsługiwane kategorie i marki

| Kategoria | Marki |
|-----------|-------|
| Przerzutki tylne | Shimano (Deore–XTR), SRAM (Eagle 70–XX) |
| Hamulce tarczowe | Shimano (Deore–XTR, Saint), SRAM (DB8, Guide, Maven) |
| Kasety | Shimano (SLX–XTR), SRAM (GX–XX Eagle) |
| Łańcuchy | Shimano, SRAM Eagle |
| Widelce | RockShox, FOX |
| Dampery | RockShox, FOX |

---

## 🗂 Struktura projektu

```
bike-comparator/
├── app.py                      # Aplikacja Streamlit (frontend)
├── requirements.txt            # Zależności dla Streamlit Cloud
├── backend/
│   ├── models.py               # Modele SQLAlchemy (PostgreSQL)
│   ├── main.py                 # Orkiestracja scrapingu
│   ├── seed_rules.py           # Wypełnienie reguł filtrowania
│   ├── ai_matcher.py           # Dopasowywanie produktów przez AI (Claude Haiku)
│   └── scrapers/
│       ├── centrum_rowerowe.py # Scraper centrumrowerowe.pl
│       ├── bike_discount.py    # Scraper bike-discount.de
│       ├── mtbiker.py          # Scraper mtbiker.pl
│       └── bikeinn.py          # Scraper bikeinn.com
```

---

## 🗄 Baza danych

PostgreSQL (`bike_tracker`) z tabelami:

| Tabela | Opis |
|--------|------|
| `brands` | Marki (Shimano, SRAM, RockShox, FOX, Magura) |
| `categories` | Kategorie (widelce, hamulce, kasety, przerzutki, łańcuchy, amortyzatory) |
| `shops` | Sklepy (cr, bd, mtb, bi) |
| `canonical_products` | Kanoniczne nazwy produktów |
| `shop_listings` | Ceny produktów per sklep |
| `price_history` | Historia cen |

Widok `v_price_comparison` — gotowe zestawienie cen per produkt (używane przez `app.py`).

### Lokalna baza

```bash
# Stwórz bazę
createdb bike_tracker

# Utwórz schemat + seed danych
cd backend
python models.py
python seed_rules.py
```

### Supabase (produkcja)

Baza w chmurze na Supabase. Połączenie przez **Session Pooler** (IPv4, port 5432).
`DATABASE_URL` ustawiony jako secret na Streamlit Cloud.

Eksport lokalnej bazy do Supabase:

```bash
pg_dump -U arkadiuszmichnej bike_tracker \
  --no-owner --no-acl --no-privileges \
  --format=plain --inserts \
  2>/dev/null | grep -v '^\\' > bike_tracker_supabase.sql
```

---

## ⚙️ Setup

### Wymagania

- Python 3.12+
- PostgreSQL
- Playwright (dla scraperów)

### Instalacja

```bash
git clone <repo-url>
cd bike-comparator

python3.12 -m venv .venv
source .venv/bin/activate
pip install playwright beautifulsoup4 sqlalchemy psycopg2-binary httpx anthropic python-dotenv requests streamlit pandas

playwright install chromium

# Klucz API Anthropic
echo "ANTHROPIC_API_KEY=sk-ant-..." > .env

# Lokalna baza PG
export DATABASE_URL="postgresql://localhost/bike_tracker"
```

---

## 🚀 Uruchomienie

### Scraping i matching

```bash
cd backend
source ../.venv/bin/activate

# Scraping wszystkich sklepów
python main.py

# Dopasowanie AI
python ai_matcher.py
```

### Aplikacja lokalna

```bash
source .venv/bin/activate
streamlit run app.py
```

---

## 🤖 Jak działa dopasowywanie AI

1. Produkty filtrowane przez reguły z `filter_rules` (marki, grupy)
2. Części serwisowe odrzucane przez `SKIP_KEYWORDS`
3. Pre-filter po numerach modelu (np. `RD-M8100`) — max 3 kandydatów
4. Pre-filter po grade zawieszenia (Factory ≠ Performance ≠ Rhythm)
5. Claude Haiku ocenia czy to ten sam produkt (JSON: `same` + `confidence`)
6. Dopasowania z confidence ≥ 95% zapisywane do `shop_listings`

| Parametr | Wartość |
|----------|---------|
| `CONFIDENCE_THRESHOLD` | 0.95 |
| `PARALLEL_CALLS` | 3 |
| Model | claude-haiku-4-5 |

---

## 🌐 Deploy

- **Streamlit Cloud:** `https://bike-comparator-bhwfr2hvgau63gr6cbfvse.streamlit.app`
- Repo prywatne — Streamlit ma dostęp przez GitHub OAuth (`icearas`)
- Secret `DATABASE_URL` wskazuje na Supabase (Session Pooler, IPv4)

### Uwagi
- `requirements.txt` musi zawierać `psycopg2-binary`
- psycopg2 zwraca `Decimal` dla kolumn `numeric` — konwertowane przez `pd.to_numeric()` w `app.py`
- Linki używają `rel="noreferrer noopener"` — centrumrowerowe.pl blokuje ruch z referrerem `streamlit.app`

---

## 📝 TODO

- [ ] **Wyprostować matching** — jeden `canonical_product` powinien mieć `shop_listings` ze wszystkich sklepów gdzie produkt istnieje (np. ZEB Ultimate Charger 3.1 → jeden wpis z linkami do CR + BD + MTB + BI)
- [ ] Automatyczne odświeżanie cen (GitHub Actions / cron)
- [ ] Pobieranie kursu EUR/PLN z API (aktualnie NBP)
- [ ] Więcej matchowań (aktualnie ~136 produktów kanonicznych)
- [ ] Dodać scraper sprint-rowery.pl
