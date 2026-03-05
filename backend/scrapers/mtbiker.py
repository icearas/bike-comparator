"""
Scraper mtbiker.pl — Playwright + paginacja URL
Uruchamiaj z katalogu backend/: python scrapers/mtbiker.py
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

BRANDS_PARAM = {
    "hamulce":    "shimano,sram",
    "kasety":     "shimano,sram",
    "lancuchy":   "shimano,sram",
    "przerzutki": "shimano,sram",
    "widelce":    "rockshox,fox",
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
    "kółka", "kółko", "kólka", "kółko", "jockey",
    "wózek", "cage",
    "spare", "części zamienne", "serwisowy",
    "pulley", "puly", "ślizg",
    "linka", "pancerz",
    "spinka", "quick link", "missing link",
    "szosowy", "szosowa", "gravel",
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
    text = text.strip()
    text = re.sub(r'^[Oo]d\s+', '', text)
    text = text.replace("\xa0", " ").replace("zł", "").replace("PLN", "").strip()
    text = text.replace(" ", "").replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return None


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
    return any(kw in name_lower for kw in ["widelec", "fork", "pike", "lyrik", "zeb", "yari", "psylo", "fox 36", "fox 38", "fox 40"])


def build_url(category_path: str, brands: str, page: int) -> str:
    page_segment = f"/page-{page}" if page > 1 else ""
    return f"{BASE_URL}{category_path}{page_segment}/?brands={brands}"


async def scrape_category(category: str, max_pages: int = 8) -> list[dict]:
    path = CATEGORIES.get(category)
    if not path:
        raise ValueError(f"Nieznana kategoria: {category}")

    brands = BRANDS_PARAM.get(category, "shimano,sram")
    products = []
    seen_urls: set[str] = set()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page_obj = await browser.new_page(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )

        for page_num in range(1, max_pages + 1):
            url = build_url(path, brands, page_num)
            print(f"  Strona {page_num}: {url}")

            try:
                await page_obj.goto(url, wait_until="networkidle", timeout=30000)
                await page_obj.wait_for_timeout(1500)
            except Exception as e:
                print(f"  Błąd ładowania strony {page_num}: {e}")
                break

            html = await page_obj.content()
            soup = BeautifulSoup(html, "html.parser")

            # Szukaj linków do produktów (-p{id}.html)
            product_links = soup.select('a[href*="-p"]')
            product_links = [a for a in product_links if re.search(r'-p\d+\.html', a.get("href", ""))]

            if not product_links:
                print(f"  Brak produktów na stronie {page_num} — koniec paginacji")
                break

            page_products = 0
            for a in product_links:
                try:
                    href = a.get("href", "")
                    if not href.startswith("http"):
                        href = BASE_URL + href
                    href = href.split("?")[0]

                    if href in seen_urls:
                        continue
                    seen_urls.add(href)

                    # Nazwa: szukaj span.product-name lub atrybut title lub tekst anchora
                    name_el = a.select_one("span.product-name, .product-name, [class*='name']")
                    if name_el:
                        name = name_el.get_text(strip=True)
                    else:
                        name = a.get("title", "").strip() or a.get_text(strip=True)[:100]

                    if not name or len(name) < 5:
                        continue

                    # Cena: szukaj span.price lub pierwszy element z "zł"
                    price_el = a.select_one("span.price, .price, [class*='price']")
                    if not price_el:
                        # fallback: szukaj tekstu z "zł"
                        text = a.get_text()
                        m = re.search(r'(\d[\d\s,]+)\s*zł', text)
                        price = float(m.group(1).replace(" ", "").replace(",", ".")) if m else None
                    else:
                        price = parse_price(price_el.get_text())

                    if price is None or price <= 0:
                        continue

                    # Filtracja
                    actual_category = category
                    if category == "widelce":
                        if is_fork(name):
                            actual_category = "widelce"
                        else:
                            actual_category = "dampery"
                        if not is_valid_suspension(name):
                            continue
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
                    print(f"  Błąd parsowania produktu: {e}")
                    continue

            print(f"  Strona {page_num}: {page_products} produktów po filtrach")

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
