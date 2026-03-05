"""
Scraper mtbiker.pl — Playwright + paginacja URL
Uruchamiaj z katalogu backend/: python scrapers/mtbiker.py

Struktura HTML:
  div.product-item          — kontener kafelka
  p.product-name > a.link-dark — nazwa + href
  strong.shop-list-price    — cena (np. "44,99 zł" lub "od 44,99 zł")
"""

import asyncio
import re
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup


BASE_URL = "https://www.mtbiker.pl"

CATEGORIES = {
    "hamulce":    "/shop/komponenty/hamulce",
    "kasety":     "/shop/komponenty/kasety-i-zebatki",
    "lancuchy":   "/shop/komponenty/lancuchy",
    "przerzutki": "/shop/komponenty/przerzutki-tylne",
    "widelce":    "/shop/komponenty/widelce-i-amortyzatory",
}

# Filtrowanie po marce w kodzie (brand filter URL nie działa)
BRAND_KEYWORDS = {
    "hamulce":    ["shimano", "sram", "deore", "slx", "xt", "xtr", "saint", "guide", "maven", "db8"],
    "kasety":     ["shimano", "sram", "deore", "slx", "xt", "xtr"],
    "lancuchy":   ["shimano", "sram", "deore", "slx", "xt", "xtr"],
    "przerzutki": ["shimano", "sram", "deore", "slx", "xt", "xtr", "saint"],
    "widelce":    ["rockshox", "rock shox", "fox", "pike", "lyrik", "zeb", "yari", "psylo"],
}

ALLOWED_GROUPS = {
    "przerzutki": [
        "deore", "slx", "xt ", "xtr", "saint",
        "rd-m6100", "rd-m6120", "rd-m7100", "rd-m7120",
        "rd-m8100", "rd-m8120", "rd-m8130", "rd-m9100", "rd-m9120", "rd-m8250",
        "gx eagle", "x01 eagle", "xx1 eagle",
        "gx ", "x01 ", "xx1 ",
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

SUSPENSION_SKIP = [
    "sprężyna", "spring", "osłona", "mudfender", "adapter",
    "deluxe", "monarch", "revelation", "reba", "rudy", "judy",
    "fox 32", "fox 34",
    "rebuild", "upgrade kit", "fluid", "pump", "bushing",
    "flight attendant", "bolt", "sealhead", "cartridge",
]

DRIVETRAIN_SKIP = [
    "kółka", "kółko", "jockey",
    "wózek", "cage",
    "spare", "części zamienne", "serwisowy",
    "pulley", "puly", "ślizg",
    "linka", "pancerz",
    "spinka", "quick link", "missing link",
    "szosowy", "szosowa",
    "bleed", "mineral", "płyn",
    " + ",
]

SHIMANO_OLD_MODELS = {
    "M7000", "M8000", "M781", "M772", "M786", "M670", "M660",
    "M615", "M610", "M6000", "M5000", "M530", "M521", "M510",
    "HG400", "HG50", "HG31", "M785", "M675", "M596", "M592",
}

SUSPENSION_KEYWORDS = [
    "pike", "lyrik", "zeb", "yari", "psylo",
    "fox 36", "fox 38", "fox 40",
    "36 ", "38 ", "40 ",
    "super deluxe", "vivid", "coil",
    "charger", "debonair",
]


def parse_price(text: str) -> float | None:
    text = re.sub(r'^[Oo]d\s+', '', text.strip())
    text = text.replace("\xa0", " ").replace("zł", "").replace("PLN", "").strip()
    text = text.replace(" ", "").replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return None


def is_correct_brand(name: str, category: str) -> bool:
    name_lower = name.lower()
    return any(kw in name_lower for kw in BRAND_KEYWORDS.get(category, []))


def is_current_shimano(name: str) -> bool:
    name_upper = name.upper()
    if not any(k in name_upper for k in [
        "SHIMANO", "DEORE", "SLX", "XT ", "XTR", "SAINT", "ZEE",
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
        "widelec", "fork", "pike", "lyrik", "zeb", "yari", "psylo", "fox 36", "fox 38", "fox 40"
    ])


def build_url(category_path: str, page: int) -> str:
    page_segment = f"/page-{page}" if page > 1 else ""
    return f"{BASE_URL}{category_path}{page_segment}/"


async def scrape_category(category: str, max_pages: int = 8) -> list[dict]:
    path = CATEGORIES.get(category)
    if not path:
        raise ValueError(f"Nieznana kategoria: {category}")

    products = []
    seen_urls: set[str] = set()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page_obj = await browser.new_page(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )

        for page_num in range(1, max_pages + 1):
            url = build_url(path, page_num)
            print(f"  Strona {page_num}: {url}")

            try:
                await page_obj.goto(url, wait_until="networkidle", timeout=30000)
                await page_obj.wait_for_timeout(1500)
            except Exception as e:
                print(f"  Błąd ładowania strony {page_num}: {e}")
                break

            html = await page_obj.content()
            soup = BeautifulSoup(html, "html.parser")

            items = soup.select("div.product-item")
            if not items:
                print(f"  Brak produktów na stronie {page_num} — koniec paginacji")
                break

            page_products = 0
            for item in items:
                try:
                    # Nazwa i URL z a.link-dark wewnątrz p.product-name
                    name_tag = item.select_one("p.product-name a.link-dark")
                    if not name_tag:
                        continue
                    name = name_tag.get_text(strip=True)
                    href = name_tag.get("href", "")
                    if not href:
                        continue
                    if not href.startswith("http"):
                        href = BASE_URL + href
                    href = href.split("?")[0]

                    if href in seen_urls:
                        continue
                    seen_urls.add(href)

                    if not name or len(name) < 5:
                        continue

                    # Filtracja po marce
                    if not is_correct_brand(name, category):
                        continue

                    # Cena z strong.shop-list-price
                    price_el = item.select_one("strong.shop-list-price")
                    if not price_el:
                        continue
                    price = parse_price(price_el.get_text())
                    if price is None or price <= 0:
                        continue

                    # Filtracja po kategorii
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
                        "price": price,
                        "currency": "PLN",
                        "category": actual_category,
                        "shop": "mtbiker.pl",
                        "url": href,
                    })
                    page_products += 1

                except Exception as e:
                    print(f"  Błąd parsowania: {e}")
                    continue

            print(f"  Strona {page_num}: {page_products} produktów po filtrach ({len(items)} kafelków)")

        await browser.close()

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
