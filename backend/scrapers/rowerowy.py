"""
Scraper rowerowy.com — Playwright + infinite scroll
Uruchamiaj z katalogu backend/: python scrapers/rowerowy.py
"""

import asyncio
import re
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup


CATEGORIES = {
    "hamulce":      "https://rowerowy.com/sklep/czesci/hamulce/tarczowe-hydrauliczne?filter=producer:Shimano%7CSRAM",
    "amortyzatory": "https://rowerowy.com/sklep/czesci/amortyzatory",
    "dampery":      "https://rowerowy.com/sklep/czesci/dampery",
    "kasety":       "https://rowerowy.com/sklep/czesci/kasety-drivery?filter=producer:Shimano%7CSRAM",
    "lancuchy":     "https://rowerowy.com/sklep/czesci/lancuchy?filter=producer:Shimano%7CSRAM",
    "przerzutki":   "https://rowerowy.com/sklep/czesci/przerzutka-tyl?filter=producer:Shimano%7CSRAM",
}

# URL filter już wyciął marki — sprawdzamy tylko grupy produktowe
ALLOWED_GROUPS = {
    "przerzutki": [
        "deore", "slx", "xt ", "xtr", "saint",
        "rd-m6100", "rd-m6120", "rd-m7100", "rd-m7120",
        "rd-m8100", "rd-m8120", "rd-m8130", "rd-m9100", "rd-m9120", "rd-m8250",
        "gx eagle", "x01 eagle", "xx1 eagle", "eagle 70", "eagle 90",
        "gx ", "x01 ", "xx1 ",  # rowerowy.com często pomija "eagle"
    ],
    "kasety": [
        "deore", "slx", "xt ", "xtr",
        "cs-m6", "cs-m7", "cs-m8", "cs-m9",
        "x01 eagle", "xx1 eagle", "eagle 70", "eagle 90", "xg-1", "xs-1",
    ],
    "lancuchy": [
        "deore", "slx", "xt ", "xtr",
        "cn-m6", "cn-m7", "cn-m8", "cn-m9",
        "gx eagle", "x01 eagle", "xx1 eagle", "nx eagle", "eagle",
    ],
    "hamulce": [
        "deore", "slx", "xt ", "xtr", "saint",
        "bl-m", "br-m",
        "m6100", "m7100", "m8100", "m8120", "m9100",
        "guide", "maven", "db8",
    ],
}

SUSPENSION_SKIP = [
    "sprężyna", "sprezyna", "spring",
    "osłona", "mudfender",
    "adapter",
    "deluxe", "monarch",
    "revelation", "reba", "rudy", "judy",
    "fox 32", "fox 34",
    "tool", "rebuild", "upgrade kit", "fluid", "pump",
    "bushing", "flight attendant",
]

DRIVETRAIN_SKIP = [
    "kółka", "kółko", "kólka", "kolka",  # kółka przerzutki (jockey wheels)
    "wózek", "wozek", "cage",             # klatka przerzutki
    "części zamienne", "czesci zamienne", # spare parts
    "zestaw naprawczy", "zestaw serwisowy",
    "puly", "pulley",
    "ślizg", "slizg",
    "obejma",
    "linka", "pancerz",
    "płyn", "plyn",
    "spinka",                             # spinki do łańcucha (chain links)
    "szosowy", "szosowa",                 # szosowe (road bike) produkty
    " + ",                                # combo zestawy
]

SHIMANO_OLD_MODELS = {
    "M7000", "M8000", "M781", "M772", "M786", "M670", "M660",
    "M615", "M610", "M6000", "M5000", "M530", "M521", "M510",
    "HG400", "HG50", "HG31", "M785", "M675", "M596", "M592",
}


def parse_price(text: str) -> float | None:
    text = text.strip()
    text = re.sub(r'^[Oo]d\s+', '', text)          # usuń prefix "Od "
    text = text.replace("\xa0", " ").replace("zł", "").strip()
    text = text.replace(" ", "").replace(",", ".")  # sep. tysięcy = spacja, decimal = przecinek
    try:
        return float(text)
    except ValueError:
        return None


def url_brand(url: str) -> str | None:
    """Wyciąga brand z URL slugu produktu (bo rowerowy.com nie podaje brandu w nazwie)."""
    if "/prod/" not in url:
        return None
    slug = url.split("/prod/")[-1].split("?")[0].lower()
    if slug.startswith("rock-shox"):
        return "ROCKSHOX"
    if slug.startswith("rs-"):
        return "ROCKSHOX"
    if slug.startswith("fox"):
        return "FOX"
    return None


def is_current_shimano(name: str) -> bool:
    name_upper = name.upper()
    # Sprawdź czy to w ogóle produkt Shimano (rowerowy.com często pomija słowo "Shimano")
    if not any(k in name_upper for k in ["SHIMANO", "DEORE", "SLX", "XT ", "XTR", "SAINT", "ZEE", "CN-", "CS-", "BL-", "BR-", "RD-"]):
        return True
    if any(old in name_upper for old in SHIMANO_OLD_MODELS):
        return False
    return True


def is_valid_suspension(name: str, url: str) -> bool:
    if url_brand(url) not in ("ROCKSHOX", "FOX"):
        return False
    name_lower = name.lower()
    if any(skip in name_lower for skip in SUSPENSION_SKIP):
        return False
    return True


def is_valid_drivetrain(name: str, category: str) -> bool:
    name_lower = name.lower()
    if any(skip in name_lower for skip in DRIVETRAIN_SKIP):
        return False
    if category in ALLOWED_GROUPS:
        if not any(kw in name_lower for kw in ALLOWED_GROUPS[category]):
            return False
    if not is_current_shimano(name):
        return False
    return True


async def scrape_category(category: str) -> list[dict]:
    url = CATEGORIES.get(category)
    if not url:
        raise ValueError(f"Nieznana kategoria: {category}")

    products = []
    seen_urls: set[str] = set()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )

        print(f"Scrapuję: {url}")
        await page.goto(url, wait_until="networkidle")
        await page.wait_for_timeout(2000)

        # Infinite scroll — kilka przewinięć żeby załadować wszystkie produkty
        prev_count = 0
        for _ in range(6):
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await page.wait_for_timeout(1500)
            count = await page.eval_on_selector_all('a[href*="/prod/"]', "els => els.length")
            if count == prev_count:
                break
            prev_count = count

        html = await page.content()
        await browser.close()

    soup = BeautifulSoup(html, "html.parser")
    links = soup.select('a[href*="/prod/"]')
    print(f"  Elementów na stronie: {len(links)}")

    for a in links:
        try:
            name = a.get("title", "").strip()
            if not name:
                continue

            href = a.get("href", "")
            clean_href = href.split("?")[0]
            full_url = "https://rowerowy.com" + clean_href

            if full_url in seen_urls:
                continue
            seen_urls.add(full_url)

            ib = a.find("ib-price")
            strong = ib.find("strong") if ib else None
            if not strong:
                continue
            price = parse_price(strong.get_text())
            if price is None or price <= 0:
                continue

            actual_category = category
            if category in ("amortyzatory", "dampery"):
                actual_category = "widelce" if category == "amortyzatory" else "dampery"
                if not is_valid_suspension(name, full_url):
                    continue
            else:
                if not is_valid_drivetrain(name, category):
                    continue

            products.append({
                "name": name,
                "price": price,
                "currency": "PLN",
                "category": actual_category,
                "shop": "rowerowy.com",
                "url": full_url,
            })

        except Exception as e:
            print(f"  Błąd: {e}")
            continue

    print(f"  Produktów po filtrach: {len(products)}")
    return products


async def main():
    all_products = []
    for cat in CATEGORIES:
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
