import asyncio
import time
from models import SessionLocal, Product, init_db
from scrapers.centrum_rowerowe import scrape_category as scrape_cr
from scrapers.bike_discount import scrape_category as scrape_bd
from scrapers.mtbiker import scrape_category as scrape_mtb
from scrapers.bikeinn import scrape_category as scrape_bi
from datetime import datetime


def save_products(products: list[dict]):
    db = SessionLocal()
    saved = 0
    updated = 0
    for p in products:
        existing = db.query(Product).filter_by(name=p.get("name"), shop=p.get("shop")).first()
        if existing:
            # Aktualizuj cenę jeśli produkt już istnieje
            existing.price = p.get("price")
            existing.scraped_at = datetime.utcnow()
            updated += 1
        else:
            product = Product(
                name=p.get("name"),
                sku=p.get("sku"),
                brand=p.get("brand"),
                price=p.get("price"),
                currency=p.get("currency", "PLN"),
                shop=p.get("shop"),
                category=p.get("category"),
                url=p.get("url"),
            )
            db.add(product)
            saved += 1
    db.commit()
    db.close()
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
    init_db()
    asyncio.run(scrape_all())