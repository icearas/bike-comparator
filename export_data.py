"""
Eksportuje matched_products z SQLite do CSV dla Streamlit.
Uruchamiaj lokalnie po każdym nowym matchu, a potem push do repo.

    python export_data.py
"""

import sqlite3
import csv
from pathlib import Path

DB_PATH = Path(__file__).parent / "backend" / "bike_comparator.db"
OUT_PATH = Path(__file__).parent / "data" / "matched_products.csv"

OUT_PATH.parent.mkdir(exist_ok=True)

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

cursor.execute("""
    SELECT
        category,
        cr_name,
        cr_price_pln,
        cr_url,
        bd_name,
        bd_price_eur,
        bd_url,
        match_confidence,
        matched_at
    FROM matched_products
    ORDER BY category, cr_name
""")

rows = cursor.fetchall()
conn.close()

with open(OUT_PATH, "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow([
        "category",
        "cr_name", "cr_price_pln", "cr_url",
        "bd_name", "bd_price_eur", "bd_url",
        "match_confidence", "matched_at",
    ])
    writer.writerows(rows)

print(f"✅ Wyeksportowano {len(rows)} dopasowań → {OUT_PATH}")
