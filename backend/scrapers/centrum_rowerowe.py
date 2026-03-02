import asyncio
import json
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup


CATEGORIES = {
    "hamulce": "https://www.centrumrowerowe.pl/czesci/hamulce-rowerowe/hamulce-tarczowe/",
    "amortyzatory": "https://www.centrumrowerowe.pl/czesci/amortyzatory-rowerowe/",
    "dampery": "https://www.centrumrowerowe.pl/czesci/amortyzatory-rowerowe/tylne-dampery/",
    "kasety": "https://www.centrumrowerowe.pl/czesci/lancuchy-kasety-wolnobiegi/kasety-rowerowe/",
    "lancuchy": "https://www.centrumrowerowe.pl/czesci/lancuchy-kasety-wolnobiegi/lancuchy-rowerowe/",
    "manetki": "https://www.centrumrowerowe.pl/czesci/manetki-klamkomanetki/",
    "przerzutki": "https://www.centrumrowerowe.pl/czesci/przerzutki-rowerowe/tylne/",
}

SUSPENSION_BRANDS = ["ROCK SHOX", "FOX RACING SHOX", "FOX", "ROCKSHOX"]

SUSPENSION_SKIP = [
    "naklejki", "sticker", "decal", "manetka", "uszczelka", "seal",
    "olej", "oil", "serwis", "service", "pianka", "foam",
    "sprężyna", "sprezyna", "spring", "błotnik", "kapsel", "komplet",
    "zestaw serwisowy", "zestaw uszczelek", "śruby", "tłumik"
]

ALLOWED_BRANDS = {
    "przerzutki": ["shimano", "sram"],
    "kasety": ["shimano", "sram"],
    "lancuchy": ["shimano", "sram"],
    "hamulce": ["shimano", "sram"],
    "manetki": ["shimano", "sram"],
}

ALLOWED_GROUPS = {
    "przerzutki": [
        "deore", "slx", "xt ", "xtr", "saint",
        "rd-m6100", "rd-m6120", "rd-m7100", "rd-m7120",
        "rd-m8100", "rd-m8120", "rd-m8130", "rd-m9100", "rd-m9120", "rd-m8250",
        "gx eagle", "nx eagle", "x01 eagle", "xx1 eagle", "eagle 70", "eagle 90",
    ],
    "kasety": [
        "deore", "slx", "xt ", "xtr",
        "cs-m6", "cs-m7", "cs-m8", "cs-m9",
        "gx eagle", "nx eagle", "x01 eagle", "xx1 eagle",
        "eagle 70", "eagle 90", "xg-1", "xs-1",
    ],
    "lancuchy": [
        "deore", "slx", "xt ", "xtr",
        "cn-m6", "cn-m7", "cn-m8", "cn-m9",
        "gx eagle", "nx eagle", "xx1 eagle", "eagle",
    ],
    "hamulce": [
        "deore", "slx", "xt ", "xtr", "saint",
        "bl-m6100", "bl-m6110", "bl-m7100", "bl-m8100", "bl-m8120", "bl-m9100",
        "br-m6100", "br-m6120", "br-m7100", "br-m8100", "br-m8120", "br-m9100",
        "guide", "maven", "db8",
    ],
    "manetki": [
        "deore", "slx", "xt ", "xtr", "saint",
        "sl-m6100", "sl-m7100", "sl-m8100", "sl-m9100",
        "gx eagle", "nx eagle", "x01 eagle", "xx1 eagle",
        "eagle 70", "eagle 90",
    ],
}


def is_valid_suspension(name: str) -> bool:
    name_upper = name.upper()
    name_lower = name.lower()

    if not any(brand in name_upper for brand in SUSPENSION_BRANDS):
        return False

    if any(skip in name_lower for skip in SUSPENSION_SKIP):
        return False

    return True


def is_valid_product(name: str, category: str) -> bool:
    name_lower = name.lower()

    # 1. Sprawdź markę
    if category in ALLOWED_BRANDS:
        if not any(brand in name_lower for brand in ALLOWED_BRANDS[category]):
            return False

    # 2. Sprawdź grupę
    if category in ALLOWED_GROUPS:
        if not any(kw in name_lower for kw in ALLOWED_GROUPS[category]):
            return False

    return True


async def scrape_category(category: str, max_pages: int = 15) -> list[dict]:
    url = CATEGORIES.get(category)
    if not url:
        raise ValueError(f"Nieznana kategoria: {category}")

    products = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        for page_num in range(1, max_pages + 1):
            page_url = f"{url}?page={page_num}" if page_num > 1 else url
            print(f"Scrapuję: {page_url}")

            await page.goto(page_url, wait_until="networkidle")
            await page.wait_for_timeout(2000)

            html = await page.content()
            soup = BeautifulSoup(html, "html.parser")

            items = soup.select("input[name='dataLayerItem']")

            if not items:
                print(f"Brak produktów na stronie {page_num}, kończę.")
                break

            for item in items:
                try:
                    data = json.loads(item["value"])
                    href = item.find_parent("div", attrs={"data-href": True})
                    url_path = href["data-href"] if href else ""

                    name = data.get("item_name", "")

                    # Filtr dla kategorii napędowych
                    if category in ALLOWED_BRANDS:
                        if not is_valid_product(name, category):
                            continue

                    # Filtr dla zawieszenia
                    actual_category = category
                    if category == "amortyzatory":
                        if not is_valid_suspension(name):
                            continue
                        actual_category = "widelce"
                    elif category == "dampery":
                        if not is_valid_suspension(name):
                            continue

                    products.append({
                        "name": name,
                        "price": float(data.get("price", 0)),
                        "currency": data.get("currency", "PLN"),
                        "brand": data.get("item_brand", ""),
                        "category": actual_category,
                        "shop": "centrumrowerowe.pl",
                        "url": "https://www.centrumrowerowe.pl" + url_path,
                    })
                except Exception as e:
                    print(f"Błąd: {e}")
                    continue

        await browser.close()

    print(f"Znaleziono {len(products)} produktów w kategorii '{category}'")
    return products


async def main():
    products = await scrape_category("hamulce", max_pages=15)
    for p in products[:10]:
        print(f"{p['category']}: {p['name']}")


if __name__ == "__main__":
    asyncio.run(main())