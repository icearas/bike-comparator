"""
Scraper bikeinn.com — Elasticsearch API (sr.tradeinn.com)
Bez Playwright. POST do sr.tradeinn.com z paginacją from/size.

Struktura API:
  POST https://sr.tradeinn.com/
  Filtr po familia (4003=napęd/hamulce, 11227=zawieszenie) + match marca
  Cena PLN: precio_win_158
  URL produktu: https://www.tradeinn.com/bikeinn/pl/{slug}/{id_modelo}/p/
"""

import asyncio
import re
import httpx

BASE_URL = "https://www.tradeinn.com/bikeinn/pl"
API_URL = "https://sr.tradeinn.com/"

HEADERS = {
    "Content-Type": "application/json",
    "Origin": "https://www.tradeinn.com",
    "Referer": "https://www.tradeinn.com/bikeinn/pl",
    "Accept-Language": "pl-PL,pl;q=0.9,en-US;q=0.8",
}

# id_familia: 4003=napęd+hamulce, 11227=zawieszenie+ramy
CATEGORIES = {
    "przerzutki": {"familia": "4003",  "keywords": ["rear derailleur"],  "brands": ["Shimano", "SRAM"]},
    "kasety":     {"familia": "4003",  "keywords": ["cassette"],          "brands": ["Shimano", "SRAM"]},
    "lancuchy":   {"familia": "4003",  "keywords": ["chain"],             "brands": ["Shimano", "SRAM"]},
    "hamulce":    {"familia": "4003",  "keywords": ["brake"],             "brands": ["Shimano", "SRAM"]},
    "widelce":    {"familia": "11227", "keywords": ["fork", "Float"],     "brands": ["RockShox", "Fox"]},
}

ALLOWED_GROUPS = {
    "przerzutki": [
        "deore", "slx", "xt ", "xtr", "saint",
        "rd-m6100", "rd-m6120", "rd-m7100", "rd-m7120",
        "rd-m8100", "rd-m8120", "rd-m8130", "rd-m9100", "rd-m9120", "rd-m8250",
        "gx eagle", "x01 eagle", "xx1 eagle",
    ],
    "kasety": [
        "deore", "slx", "xt ", "xtr",
        "cs-m6", "cs-m7", "cs-m8", "cs-m9",
        "x01 eagle", "xx1 eagle", "xg-1", "xs-1",
    ],
    "lancuchy": [
        "deore", "slx", "xt ", "xtr",
        "cn-m6", "cn-m7", "cn-m8", "cn-m9",
        "gx eagle", "x01 eagle", "xx1 eagle", "nx eagle",
    ],
    "hamulce": [
        "deore", "slx", "xt ", "xtr", "saint",
        "bl-m", "br-m",
        "m6100", "m7100", "m8100", "m8120", "m9100",
        "guide", "maven", "db8",
    ],
}

DRIVETRAIN_SKIP = [
    "kółka", "jockey", "wózek", "cage", "spare",
    "pulley", "linka", "spinka", "quick link", "missing link",
    "szosowy", "szosowa", "bleed", "mineral",
    "spring", "rebound", "service", "rebuild",
    "pad", "klocek", "disc", "rotor",
    "crank", "chainring", "chainset",
]

SUSPENSION_SKIP = [
    "spring", "mudfender", "adapter", "deluxe", "monarch",
    "revelation", "reba", "rudy", "judy", "fox 32", "fox 34",
    "rebuild", "upgrade kit", "fluid", "pump", "bushing",
    "flight attendant", "bolt", "sealhead", "cartridge", "damper",
    "lower leg", "lower legs", "lowers", "crown", "arch",
    "steerer", "axle", "maxle",
]

SUSPENSION_KEYWORDS = [
    "pike", "lyrik", "zeb", "yari", "psylo",
    "fox 36", "fox 38", "fox 40",
    "36 ", "38 ", "40 ",
    "super deluxe", "vivid", "coil", "charger", "debonair",
]

SHIMANO_OLD_MODELS = {
    "M7000", "M8000", "M781", "M772", "M786", "M670", "M660",
    "M615", "M610", "M6000", "M5000", "M530", "M521", "M510",
    "HG400", "HG50", "HG31", "M785", "M675", "M596", "M592",
}


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def build_url(marca: str, model_eng: str, id_modelo: str) -> str:
    slug = slugify(f"{marca} {model_eng}")
    return f"{BASE_URL}/{slug}/{id_modelo}/p/"


def is_current_shimano(name: str) -> bool:
    name_upper = name.upper()
    if not any(k in name_upper for k in [
        "SHIMANO", "DEORE", "SLX", "XT ", "XTR", "SAINT",
        "CN-", "CS-", "BL-", "BR-", "RD-",
    ]):
        return True
    return not any(old in name_upper for old in SHIMANO_OLD_MODELS)


def is_valid_drivetrain(name: str, category: str) -> bool:
    name_lower = name.lower()
    if any(skip in name_lower for skip in DRIVETRAIN_SKIP):
        return False
    if category in ALLOWED_GROUPS:
        if not any(kw in name_lower for kw in ALLOWED_GROUPS[category]):
            return False
    return is_current_shimano(name)


def is_valid_suspension(name: str) -> bool:
    name_lower = name.lower()
    if any(skip in name_lower for skip in SUSPENSION_SKIP):
        return False
    return any(kw in name_lower for kw in SUSPENSION_KEYWORDS)


def is_fork(name: str) -> bool:
    name_lower = name.lower()
    return any(kw in name_lower for kw in [
        "fork", "pike", "lyrik", "zeb", "yari", "psylo", "fox 36", "fox 38", "fox 40"
    ])


def build_query(familia: str, brand: str, keywords: list[str], from_: int, size: int = 40) -> dict:
    keyword_clause = (
        {"match": {"model.eng": keywords[0]}}
        if len(keywords) == 1
        else {"bool": {"should": [{"match": {"model.eng": kw}} for kw in keywords], "minimum_should_match": 1}}
    )
    return {
        "from": from_,
        "size": size,
        "query": {"bool": {
            "must": [{"match": {"marca": brand}}, keyword_clause],
            "filter": [
                {"exists": {"field": "precio_win_158"}},
                {"nested": {"path": "familias", "query": {"term": {"familias.id_familia": familia}}}},
            ],
        }},
        "_source": {"includes": ["id_modelo", "marca", "model", "precio_win_158"]},
    }


async def scrape_category(category: str, max_pages: int = 10) -> list[dict]:
    cfg = CATEGORIES.get(category)
    if not cfg:
        raise ValueError(f"Nieznana kategoria: {category}")

    products = []
    seen_ids: set[str] = set()

    async with httpx.AsyncClient(headers=HEADERS, timeout=20) as client:
        for brand in cfg["brands"]:
            from_ = 0
            page = 0
            while page < max_pages:
                query = build_query(cfg["familia"], brand, cfg["keywords"], from_)
                try:
                    r = await client.post(API_URL, json=query)
                    r.raise_for_status()
                except Exception as e:
                    print(f"  Błąd API ({brand} s.{page+1}): {e}")
                    break

                data = r.json()
                hits = data.get("hits", {}).get("hits", [])
                total = data.get("hits", {}).get("total", {}).get("value", 0)

                if not hits:
                    break

                page_count = 0
                for hit in hits:
                    s = hit.get("_source", {})
                    id_modelo = s.get("id_modelo", "")
                    if not id_modelo or id_modelo in seen_ids:
                        continue
                    seen_ids.add(id_modelo)

                    name = s.get("model", {}).get("eng", "").strip()
                    if not name or len(name) < 5:
                        continue

                    price = s.get("precio_win_158")
                    if not price or price <= 0:
                        continue

                    marca = s.get("marca", "")
                    url = build_url(marca, name, id_modelo)

                    actual_category = category
                    if category == "widelce":
                        if not is_valid_suspension(name):
                            continue
                        actual_category = "widelce" if is_fork(name) else "dampery"
                    else:
                        if not is_valid_drivetrain(name, category):
                            continue

                    products.append({
                        "name": name,
                        "price": round(float(price), 2),
                        "currency": "PLN",
                        "category": actual_category,
                        "shop": "bikeinn.com",
                        "url": url,
                    })
                    page_count += 1

                print(f"  [{brand}] strona {page+1}/{-(-total//40)}: {page_count} produktów ({from_+len(hits)}/{total})")

                from_ += len(hits)
                if from_ >= total:
                    break
                page += 1

    print(f"  [{category}] Łącznie: {len(products)} produktów")
    return products


async def main():
    all_products = []
    for cat in CATEGORIES:
        print(f"\n=== {cat} ===")
        products = await scrape_category(cat)
        all_products.extend(products)

    print(f"\n=== PODSUMOWANIE: {len(all_products)} produktów ===")
    by_cat: dict[str, list] = {}
    for p in all_products:
        by_cat.setdefault(p["category"], []).append(p)
    for cat, prods in sorted(by_cat.items()):
        print(f"  {cat}: {len(prods)}")
    print("\nPierwsze 15 produktów:")
    for p in all_products[:15]:
        print(f"  [{p['category']}] {p['name'][:55]:<55} {p['price']:>8.2f} PLN")


if __name__ == "__main__":
    asyncio.run(main())
