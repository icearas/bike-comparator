# 🗄 Bike Comparator — Projekt bazy danych (SQL)

Dokument opisuje docelowy schemat relacyjnej bazy danych dla aplikacji bike-comparator.
Zastępuje obecne podejście pairwise (CR↔BD w SQLite, CR↔RW w CSV) ujednoliconym
modelem wielu sklepów z kanonicznym katalogiem produktów.

---

## Cel i motywacja

Obecny schemat ma dwa problemy:

| Problem | Obecny stan | Cel |
|---------|-------------|-----|
| Nazwy produktów | 3 różne nazwy tego samego produktu (CR/BD/RW) | Jedna kanoniczna nazwa |
| Skalowalność | Nowy sklep = nowy matcher + nowy CSV | Nowy sklep = nowe wiersze w `shop_listings` |

---

## Diagram ER

```
brands ──────────────────────────────────────────────┐
  id (PK)                                            │
  name                                               │
  slug                                               │
                                                     ▼
categories          canonical_products ◄──── shop_listings
  id (PK)             id (PK)                id (PK)
  name                canonical_name         canonical_product_id (FK, nullable)
  slug                brand_id (FK) ─────►   shop_id (FK) ──────────► shops
                      category_id (FK) ──►   raw_name                   id (PK)
                      grade                  price                      name
                      model_code             currency                   slug
                      created_at             url                        currency
                                             match_confidence           country
                                             match_method
                                             scraped_at
                                                 │
                                                 ▼
                                           price_history
                                             id (PK)
                                             shop_listing_id (FK)
                                             price
                                             recorded_at
```

---

## Tabele

### `brands`

Słownik marek. Zmiana nazwy marki w jednym miejscu aktualizuje cały katalog.

```sql
CREATE TABLE brands (
    id   SERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,   -- "RockShox", "Shimano", "SRAM", "FOX"
    slug TEXT NOT NULL UNIQUE    -- "rockshox", "shimano", "sram", "fox"
);
```

---

### `categories`

Słownik kategorii. Niezależny od języka — slug jest kluczem wewnętrznym.

```sql
CREATE TABLE categories (
    id          SERIAL PRIMARY KEY,
    name        TEXT NOT NULL UNIQUE,   -- "Widelce", "Hamulce", "Kasety"...
    slug        TEXT NOT NULL UNIQUE    -- "widelce", "hamulce", "kasety"...
);
```

---

### `shops`

Jeden wiersz na sklep. Dodanie nowego sklepu nie wymaga zmian schematu.

```sql
CREATE TABLE shops (
    id       SERIAL PRIMARY KEY,
    name     TEXT NOT NULL UNIQUE,   -- "centrumrowerowe.pl", "bike-discount.de", "mtbiker.pl", "bikeinn.com"
    slug     TEXT NOT NULL UNIQUE,   -- "cr", "bd", "mtb", "bi"
    currency CHAR(3) NOT NULL,       -- "PLN", "EUR"
    country  CHAR(2) NOT NULL        -- "PL", "DE"
);
```

---

### `canonical_products`

**Serce schematu.** Jeden wiersz = jeden unikalny model części rowerowej.
Kanoniczna nazwa jest niezależna od języka i nazewnictwa sklepu.

```sql
CREATE TABLE canonical_products (
    id             SERIAL PRIMARY KEY,
    canonical_name TEXT NOT NULL,             -- "RockShox ZEB Ultimate Charger 3.1 29\" 160mm"
    brand_id       INTEGER NOT NULL REFERENCES brands(id),
    category_id    INTEGER NOT NULL REFERENCES categories(id),
    model_code     TEXT,                      -- "RD-M8100", "ZEB-ULT" — pomocnicze
    grade          TEXT,                      -- "Ultimate", "Factory", "Performance" — dla zawieszeń
    created_at     TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE (canonical_name, brand_id)
);

CREATE INDEX idx_cp_brand    ON canonical_products(brand_id);
CREATE INDEX idx_cp_category ON canonical_products(category_id);
CREATE INDEX idx_cp_grade    ON canonical_products(grade);
```

**Przykładowe wiersze:**

| id | canonical_name | brand | category | grade |
|----|----------------|-------|----------|-------|
| 1 | RockShox ZEB Ultimate Charger 3.1 29" | RockShox | widelce | Ultimate |
| 2 | Shimano XT RD-M8100 | Shimano | przerzutki | — |
| 3 | SRAM GX Eagle | SRAM | kasety | — |

---

### `shop_listings`

Surowe dane ze skraperów. Jeden wiersz = jeden produkt w jednym sklepie.
`canonical_product_id` jest nullable — produkt ze sklepu może jeszcze nie być
dopasowany do katalogu.

```sql
CREATE TABLE shop_listings (
    id                     SERIAL PRIMARY KEY,
    canonical_product_id   INTEGER REFERENCES canonical_products(id) ON DELETE SET NULL,
    shop_id                INTEGER NOT NULL REFERENCES shops(id),
    raw_name               TEXT NOT NULL,          -- nazwa dokładnie jak w sklepie
    price                  NUMERIC(10, 2) NOT NULL,
    currency               CHAR(3) NOT NULL,       -- zgodna z shops.currency
    url                    TEXT NOT NULL,
    match_confidence       NUMERIC(4, 3),          -- 0.000 – 1.000
    match_method           TEXT                    -- 'ai', 'manual', 'code'
        CHECK (match_method IN ('ai', 'manual', 'code', NULL)),
    scraped_at             TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE (shop_id, url)   -- ten sam URL w tym samym sklepie = jeden wiersz
);

CREATE INDEX idx_sl_canonical ON shop_listings(canonical_product_id);
CREATE INDEX idx_sl_shop      ON shop_listings(shop_id);
CREATE INDEX idx_sl_scraped   ON shop_listings(scraped_at DESC);
```

---

### `price_history`

Historia cen — zapisuj nowy wiersz przy każdym scrapingu jeśli cena się zmieniła.
Umożliwia śledzenie trendów cenowych.

```sql
CREATE TABLE price_history (
    id              SERIAL PRIMARY KEY,
    shop_listing_id INTEGER NOT NULL REFERENCES shop_listings(id) ON DELETE CASCADE,
    price           NUMERIC(10, 2) NOT NULL,
    currency        CHAR(3) NOT NULL,
    recorded_at     TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_ph_listing  ON price_history(shop_listing_id);
CREATE INDEX idx_ph_recorded ON price_history(recorded_at DESC);
```

---

## Widoki (Views)

### `v_price_comparison`

Główny widok używany przez aplikację — zastępuje join po CSV w `app.py`.

```sql
CREATE VIEW v_price_comparison AS
SELECT
    cp.id                  AS product_id,
    cp.canonical_name,
    cp.grade,
    cat.slug               AS category,
    cat.name               AS category_label,
    b.name                 AS brand,

    -- Centrum Rowerowe (PLN)
    cr_sl.price            AS cr_price_pln,
    cr_sl.url              AS cr_url,
    cr_sl.raw_name         AS cr_raw_name,

    -- Bike Discount (EUR)
    bd_sl.price            AS bd_price_eur,
    bd_sl.url              AS bd_url,
    bd_sl.raw_name         AS bd_raw_name,

    -- mtbiker.pl (PLN)
    mtb_sl.price           AS mtb_price_pln,
    mtb_sl.url             AS mtb_url,
    mtb_sl.raw_name        AS mtb_raw_name,

    -- bikeinn.com (PLN)
    bi_sl.price            AS bi_price_pln,
    bi_sl.url              AS bi_url,
    bi_sl.raw_name         AS bi_raw_name,

    GREATEST(cr_sl.scraped_at, bd_sl.scraped_at, mtb_sl.scraped_at, bi_sl.scraped_at) AS last_updated

FROM canonical_products cp
JOIN brands     b   ON b.id   = cp.brand_id
JOIN categories cat ON cat.id = cp.category_id

LEFT JOIN shop_listings cr_sl  ON cr_sl.canonical_product_id  = cp.id
    AND cr_sl.shop_id  = (SELECT id FROM shops WHERE slug = 'cr')
LEFT JOIN shop_listings bd_sl  ON bd_sl.canonical_product_id  = cp.id
    AND bd_sl.shop_id  = (SELECT id FROM shops WHERE slug = 'bd')
LEFT JOIN shop_listings mtb_sl ON mtb_sl.canonical_product_id = cp.id
    AND mtb_sl.shop_id = (SELECT id FROM shops WHERE slug = 'mtb')
LEFT JOIN shop_listings bi_sl  ON bi_sl.canonical_product_id  = cp.id
    AND bi_sl.shop_id  = (SELECT id FROM shops WHERE slug = 'bi');
```

---

## Przykładowe zapytania

### Najtańszy sklep dla każdego produktu

```sql
SELECT
    canonical_name,
    category,
    cr_price_pln,
    ROUND(bd_price_eur * 4.23, 2) AS bd_price_pln,
    mtb_price_pln,
    bi_price_pln,
    LEAST(
        cr_price_pln,
        ROUND(bd_price_eur * 4.23, 2),
        mtb_price_pln,
        bi_price_pln
    ) AS min_price
FROM v_price_comparison
WHERE cr_price_pln IS NOT NULL
ORDER BY min_price;
```

---

### Produkty niedopasowane (jeszcze bez canonical_product_id)

```sql
SELECT
    s.name AS shop,
    sl.raw_name,
    sl.price,
    sl.currency,
    sl.scraped_at
FROM shop_listings sl
JOIN shops s ON s.id = sl.shop_id
WHERE sl.canonical_product_id IS NULL
ORDER BY s.name, sl.raw_name;
```

---

### Historia cen dla konkretnego produktu w BD

```sql
SELECT
    cp.canonical_name,
    ph.price,
    ph.currency,
    ph.recorded_at
FROM price_history ph
JOIN shop_listings sl ON sl.id = ph.shop_listing_id
JOIN shops s          ON s.id  = sl.shop_id
JOIN canonical_products cp ON cp.id = sl.canonical_product_id
WHERE s.slug = 'bd'
  AND cp.canonical_name ILIKE '%ZEB Ultimate%'
ORDER BY ph.recorded_at DESC;
```

---

### Upsert ceny przy scrapingu (ON CONFLICT)

```sql
INSERT INTO shop_listings (shop_id, url, raw_name, price, currency, scraped_at)
VALUES (2, 'https://bike-discount.de/...', 'RockShox ZEB Ultimate...', 899.00, 'EUR', NOW())
ON CONFLICT (shop_id, url)
DO UPDATE SET
    price      = EXCLUDED.price,
    raw_name   = EXCLUDED.raw_name,
    scraped_at = EXCLUDED.scraped_at;
```

---

## Normalizacja — poziomy

| Forma | Spełniona? | Dlaczego |
|-------|-----------|----------|
| **1NF** | ✅ | Każda kolumna atomowa, brak list w polach |
| **2NF** | ✅ | Każda kolumna zależy od całego PK (brak częściowych zależności) |
| **3NF** | ✅ | Brak zależności przechodnich — `brand_id`, `category_id` zamiast tekstu |
| **BCNF** | ✅ | Każdy wyznacznik jest kluczem kandydującym |

---

## Migracja z obecnego schematu

| Obecna tabela | Docelowe miejsce |
|---------------|-----------------|
| `products` (shop=centrumrowerowe.pl) | `shop_listings` + `canonical_products` |
| `products` (shop=bike-discount.de) | `shop_listings` |
| `products` (shop=mtbiker.pl) | `shop_listings` |
| `products` (shop=bikeinn.com) | `shop_listings` |
| `matched_products` | połączone w `canonical_product_id` w `shop_listings` |
| `filter_rules` | bez zmiany lub jako kolumna `tracked BOOLEAN` w `canonical_products` |
| `data/matched_products.csv` | wchłonięte przez `shop_listings` |
| `data/mtb_matched.csv` | wchłonięte przez `shop_listings` |
| `data/bi_matched.csv` | wchłonięte przez `shop_listings` |

---

## Stack techniczny (propozycja)

| Warstwa | Opcja A (nauka) | Opcja B (produkcja) |
|---------|-----------------|---------------------|
| Baza | PostgreSQL 16 | PostgreSQL 16 (Supabase free tier) |
| ORM | SQLAlchemy 2.x | SQLAlchemy 2.x |
| Migracje | Alembic | Alembic |
| Dane testowe | Python `faker` + skrypt seed | — |
