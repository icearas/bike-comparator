"""
PostgreSQL connection + shared lookup tables.
DATABASE_URL env var (lub Streamlit secrets) — fallback: localhost/bike_tracker
"""

import os
import psycopg2
import psycopg2.extras

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://arkadiuszmichnej@localhost/bike_tracker")

# Statyczne ID (zgodne z danymi seed w bike_tracker)
SHOP_IDS = {"cr": 1, "bd": 2, "mtb": 3, "bi": 4}

SHOP_NAME_TO_SLUG = {
    "centrumrowerowe.pl": "cr",
    "bike-discount.de":   "bd",
    "mtbiker.pl":         "mtb",
    "bikeinn.com":        "bi",
}

CATEGORY_IDS = {
    "widelce":      1,
    "hamulce":      2,
    "kasety":       3,
    "przerzutki":   4,
    "lancuchy":     5,
    "amortyzatory": 6,
    "dampery":      6,   # dampery = tylne amortyzatory → id 6
}

# Mapowanie kategorii CR na canonical (do tworzenia canonical_products)
CATEGORY_CANONICAL = {
    "amortyzatory": "widelce",   # CR "amortyzatory" to widelce (widelce przód)
    "dampery":      "amortyzatory",  # CR "dampery" to tylne amortyzatory
}

BRAND_IDS = {
    "ROCKSHOX": 1,
    "SHIMANO":  2,
    "SRAM":     3,
    "FOX":      4,
    "MAGURA":   5,
}


def get_conn():
    return psycopg2.connect(DATABASE_URL)


def assign_match(conn, cr_listing_id: int, other_listing_id: int,
                 cr_name: str, category: str, brand: str,
                 confidence: float, method: str = "ai") -> int:
    """
    Łączy dwa shop_listings przez canonical_product.
    Jeśli CR listing już ma canonical_product_id — używa tego samego.
    Zwraca canonical_product_id.
    """
    cur = conn.cursor()

    # Sprawdź czy CR listing ma już canonical_product_id
    cur.execute("SELECT canonical_product_id FROM shop_listings WHERE id = %s", (cr_listing_id,))
    row = cur.fetchone()
    cp_id = row[0] if row else None

    if not cp_id:
        # Wyznacz category_id i brand_id
        cat_key = CATEGORY_CANONICAL.get(category, category)
        cat_id = CATEGORY_IDS.get(cat_key) or CATEGORY_IDS.get(category, 4)
        brand_id = BRAND_IDS.get(brand, 3)

        # Find-or-create canonical_product (upsert)
        cur.execute("""
            INSERT INTO canonical_products (canonical_name, brand_id, category_id)
            VALUES (%s, %s, %s)
            ON CONFLICT (canonical_name, brand_id) DO UPDATE
                SET canonical_name = EXCLUDED.canonical_name
            RETURNING id
        """, (cr_name, brand_id, cat_id))
        cp_id = cur.fetchone()[0]

        # Przypisz do CR listing
        cur.execute("""
            UPDATE shop_listings SET canonical_product_id = %s, match_method = %s
            WHERE id = %s AND canonical_product_id IS NULL
        """, (cp_id, method, cr_listing_id))

    # Przypisz do drugiego listingu
    cur.execute("""
        UPDATE shop_listings
        SET canonical_product_id = %s, match_confidence = %s, match_method = %s
        WHERE id = %s
    """, (cp_id, confidence, method, other_listing_id))

    conn.commit()
    cur.close()
    return cp_id
