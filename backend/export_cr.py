"""
Eksportuje przefiltrowane produkty CR z DB do data/cr_all.csv.
Uruchamiaj z katalogu backend/: python export_cr.py
"""

import csv
from pathlib import Path
from models import SessionLocal, Product
from ai_matcher import is_main_product, load_filter_rules

OUT_PATH = Path(__file__).parent.parent / "data" / "cr_all.csv"

db = SessionLocal()
try:
    rules = load_filter_rules(db)
    cr_products = db.query(Product).filter_by(shop="centrumrowerowe.pl").all()
    cr_main = [p for p in cr_products if is_main_product(p.name, p.category, rules, p.url or "")]
finally:
    db.close()

with open(OUT_PATH, "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(["name", "category", "price", "url"])
    for p in cr_main:
        writer.writerow([p.name, p.category, p.price, p.url or ""])

print(f"Wyeksportowano {len(cr_main)} produktów CR → {OUT_PATH}")
