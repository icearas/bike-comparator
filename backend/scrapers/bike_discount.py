import asyncio
import json
import re
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup


CATEGORIES = {
    "hamulce": [
        "https://www.bike-discount.de/en/bike/bike-parts/mountain-bike-parts/brakes/disc-brake-sets",
        "https://www.bike-discount.de/en/bike/bike-parts/mountain-bike-parts/brakes/disc-brakes-front-brakes",
        "https://www.bike-discount.de/en/bike/bike-parts/mountain-bike-parts/brakes/disc-brakes-rear-brakes",
    ],
    "widelce": "https://www.bike-discount.de/en/mtb-forks",
    "dampery": "https://www.bike-discount.de/en/bike/bike-parts/mountain-bike-parts/rear-shock",
    "lancuchy": "https://www.bike-discount.de/en/bike/bike-parts/mountain-bike-parts/chains",
    "kasety": "https://www.bike-discount.de/en/bike/bike-parts/mountain-bike-parts/cassettes",
    "przerzutki": "https://www.bike-discount.de/en/bike/bike-parts/mountain-bike-parts/rear-derailleurs",
}

ALLOWED_URL_BRANDS = {
    "przerzutki": ["shimano", "sram"],
    "kasety": ["shimano", "sram"],
    "lancuchy": ["shimano", "sram"],
    "hamulce": ["shimano", "sram"],
    "widelce": ["rockshox", "fox"],
    "dampery": ["rockshox", "fox"],
}

ALLOWED_GROUPS = {
    "przerzutki": [
        "deore", "slx", "xt ", "xtr", "saint",
        "rd-m6100", "rd-m6120", "rd-m7100", "rd-m7120",
        "rd-m8100", "rd-m8120", "rd-m8130", "rd-m9100", "rd-m9120", "rd-m8250",
        "gx eagle", "x01 eagle", "xx1 eagle", "eagle 70", "eagle 90",
    ],
    "kasety": [
        "deore", "slx", "xt ", "xtr",
        "cs-m6", "cs-m7", "cs-m8", "cs-m9",
        "x01 eagle", "xx1 eagle",
        "eagle 70", "eagle 90", "xg-1", "xs-1",
    ],
    "lancuchy": [
        "deore", "slx", "xt ", "xtr",
        "cn-m6", "cn-m7", "cn-m8", "cn-m9",
        "gx eagle", "x01 eagle", "xx1 eagle", "eagle",
    ],
    "hamulce": [
        "deore", "slx", "xt ", "xtr", "saint",
        "bl-m6100", "bl-m6110", "bl-m7100", "bl-m8100", "bl-m8120", "bl-m9100",
        "br-m6100", "br-m6120", "br-m7100", "br-m8100", "br-m8120", "br-m9100",
        "m6100", "m7100", "m8100", "m8120", "m9100",
        "guide", "maven", "db8",
    ],
}

SUSPENSION_SKIP = [
    "damper upgrade", "charger", "seal kit", "spare", "service kit",
    "oil", "grease", "bolt", "screw", "crown", "axle", "remote",
    "cable", "hose", "bleed", "spring", "foam ring",
    # Modele poza zakresem
    "revelation", "reba", "rudy", "judy",
    "deluxe", "monarch",
    "fox 32", "fox 34",
]

SHIMANO_OLD_MODELS = {
    "M7000", "M8000", "M781", "M772", "M786", "M670", "M660",
    "M615", "M610", "M6000", "M5000", "M530", "M521", "M510",
    "HG400", "HG50", "HG31", "M785", "M675", "M596", "M592",
}


def is_current_shimano(name: str) -> bool:
    name_upper = name.upper()
    if not any(k in name_upper for k in ["SHIMANO", "DEORE", "SLX", "XTR", "SAINT", "ZEE"]):
        return True
    if any(old in name_upper for old in SHIMANO_OLD_MODELS):
        return False
    return True


def is_valid_product(name: str, url: str, category: str) -> bool:
    url_lower = url.lower()
    name_lower = name.lower()

    if category in ALLOWED_URL_BRANDS:
        if not any(brand in url_lower for brand in ALLOWED_URL_BRANDS[category]):
            return False

    if category in ALLOWED_GROUPS:
        if not any(kw in name_lower for kw in ALLOWED_GROUPS[category]):
            return False

    if category in ("widelce", "dampery"):
        if any(skip in name_lower for skip in SUSPENSION_SKIP):
            return False

    if not is_current_shimano(name):
        return False

    return True


async def scrape_category(category: str, max_pages: int = 10) -> list[dict]:
    urls = CATEGORIES.get(category)
    if not urls:
        raise ValueError(f"Nieznana kategoria: {category}")

    if isinstance(urls, str):
        urls = [urls]

    products = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )

        for url in urls:
            for page_num in range(1, max_pages + 1):
                page_url = f"{url}?p={page_num}" if page_num > 1 else url
                print(f"Scrapuję: {page_url}")

                await page.goto(page_url, wait_until="networkidle")
                await page.wait_for_timeout(5000)

                html = await page.content()
                soup = BeautifulSoup(html, "html.parser")

                items = soup.select("div.card.product-box")
                print(f"Znaleziono elementów: {len(items)}")

                if not items:
                    print(f"Brak produktów na stronie {page_num}, kończę.")
                    break

                for item in items:
                    try:
                        data_raw = item.get("data-product-information", "{}")
                        data = json.loads(data_raw)
                        name = data.get("name", "")

                        price_el = item.select_one("span.product-price")
                        if not price_el:
                            continue

                        price_text = (
                            price_el.get_text(strip=True)
                            .replace("€", "")
                            .replace("\xa0", "")
                            .replace("RRP*", "")
                            .replace("from", "")
                            .strip()
                        )
                        price_text = re.sub(r'\.(?=\d{3})', '', price_text)
                        price_text = price_text.replace(",", ".")

                        numbers = [x.strip() for x in price_text.split() if x.strip().replace(".", "").isdigit()]
                        if not numbers:
                            continue
                        price = float(numbers[-1])

                        link_el = item.select_one("a.product-name, a[href*='/en/']")
                        link = link_el.get("href", "") if link_el else ""
                        if link and not link.startswith("http"):
                            link = "https://www.bike-discount.de" + link

                        product_id_el = item.select_one("input[name='product-name']")
                        sku = product_id_el.get("value", "") if product_id_el else ""

                        if not name:
                            continue

                        if not is_valid_product(name, link, category):
                            continue

                        products.append({
                            "name": name,
                            "sku": sku,
                            "price": price,
                            "currency": "EUR",
                            "shop": "bike-discount.de",
                            "category": category,
                            "url": link,
                        })

                    except Exception as e:
                        print(f"Błąd: {e}")
                        continue

        await browser.close()

    print(f"Znaleziono {len(products)} produktów w kategorii '{category}'")
    return products


async def main():
    products = await scrape_category("przerzutki", max_pages=2)
    for p in products[:10]:
        print(f"{p['name']} | {p['url']}")


if __name__ == "__main__":
    asyncio.run(main())