import asyncio
import time
from db import get_conn, SHOP_NAME_TO_SLUG, SHOP_IDS
from scrapers.centrum_rowerowe import scrape_category as scrape_cr
from scrapers.bike_discount import scrape_category as scrape_bd
from scrapers.mtbiker import scrape_category as scrape_mtb
from scrapers.bikeinn import scrape_category as scrape_bi


def save_products(products: list[dict]):
    conn = get_conn()
    cur = conn.cursor()
    saved = 0
    updated = 0
    for p in products:
        slug = SHOP_NAME_TO_SLUG.get(p.get("shop", ""))
        if not slug:
            continue
        url = p.get("url")
        if not url:
            continue
        shop_id = SHOP_IDS[slug]
        cur.execute("""
            INSERT INTO shop_listings (shop_id, raw_name, price, currency, url, raw_category, scraped_at)
            VALUES (%s, %s, %s, %s, %s, %s, NOW())
            ON CONFLICT (shop_id, url) DO UPDATE SET
                raw_name     = EXCLUDED.raw_name,
                price        = EXCLUDED.price,
                raw_category = EXCLUDED.raw_category,
                scraped_at   = NOW()
            RETURNING (xmax = 0)
        """, (shop_id, p.get("name"), p.get("price"), p.get("currency", "PLN"),
              url, p.get("category", "")))
        row = cur.fetchone()
        if row and row[0]:
            saved += 1
        else:
            updated += 1
    conn.commit()
    cur.close()
    conn.close()
    print(f"Zapisano {saved} nowych, zaktualizowano {updated} produktów.")


async def scrape_all():
    cr_categories  = ["przerzutki", "hamulce", "kasety", "lancuchy", "manetki", "amortyzatory", "widelce", "dampery"]
    bd_categories  = ["przerzutki", "hamulce", "kasety", "lancuchy", "widelce", "dampery"]
    mtb_categories = ["przerzutki", "hamulce", "kasety", "lancuchy", "widelce"]
    bi_categories  = ["przerzutki", "hamulce", "kasety", "lancuchy", "widelce"]

    total_start = time.time()

    all_categories = sorted(set(cr_categories + bd_categories + mtb_categories + bi_categories))
    for category in all_categories:
        print(f"\n=== Scrapuję kategorię: {category} ===")
        cat_start = time.time()

        if category in cr_categories:
            try:
                products = await scrape_cr(category, max_pages=15)
                save_products(products)
            except Exception as e:
                print(f"Błąd CR ({category}): {e}")

        if category in bd_categories:
            try:
                products = await scrape_bd(category, max_pages=10)
                save_products(products)
            except Exception as e:
                print(f"Błąd BD ({category}): {e}")

        if category in mtb_categories:
            try:
                products = await scrape_mtb(category)
                save_products(products)
            except Exception as e:
                print(f"Błąd MTB ({category}): {e}")

        if category in bi_categories:
            try:
                products = await scrape_bi(category)
                save_products(products)
            except Exception as e:
                print(f"Błąd BI ({category}): {e}")

        cat_time = time.time() - cat_start
        print(f"⏱️  {category}: {cat_time:.1f}s")

    total_time = time.time() - total_start
    print(f"\n✅ Łączny czas: {total_time:.1f}s ({total_time/60:.1f} min)")


if __name__ == "__main__":
    asyncio.run(scrape_all())