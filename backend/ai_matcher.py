import anthropic
import json
from models import SessionLocal, Product, MatchedProduct, FilterRule
from datetime import datetime, timezone
from dotenv import load_dotenv
import os
import time
import re

load_dotenv(dotenv_path="../.env")

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

SKIP_KEYWORDS = [
    "kółka", "kólka", "wózek", "wozek", "ślizg", "slizg", "obejma",
    "śrubki", "srubki", "przymiar", "pulley", "pully", "cage",
    "klocki", "klocek", "okładziny", "okladziny", "linka", "pancerz",
    "płyn", "plyn", "zestaw do odpowietrzania", "seal kit", "spare",
    "bolt", "screw", "plate", "set for", "puly", "kolka", "wozek",
    "przerzutka przednia", "przednia shimano", "fd-", "kółko przerzutki", "kolko przerzutki",
    "tarcza", "rotor", "oneloc", "manetka blokady",
    "suntour", "sr suntour", "sora", "cs-hg50", "rock shox 35", "rockshox 35", "rock shox recon", "rockshox recon", "recon silver", "recon gold",
    "paragon", "domain", "microshift", "rd-t", "advent"
]

BRAND_KEYWORDS = {
    "SHIMANO": ["SHIMANO", "DEORE", "SLX", "XTR"],
    "SRAM": ["SRAM", "GX", "NX", "XX1", "X01", "EAGLE"],
    "ROCKSHOX": ["ROCKSHOX", "ROCK SHOX", "RECON", "REVELATION", "PIKE", "LYRIK",
                 "ZEB", "SID", "JUDY", "DOMAIN", "PARAGON"],
    "FOX": ["FOX"],
    "MAGURA": ["MAGURA"],
    "TEKTRO": ["TEKTRO"],
}

CATEGORY_MAP = {
    "amortyzatory": "widelce",
}


def load_filter_rules(db) -> list:
    return db.query(FilterRule).filter_by(active=1).all()


def is_main_product(name: str, category: str, rules: list, url: str = "") -> bool:
    name_lower = name.lower()

    for keyword in SKIP_KEYWORDS:
        if keyword in name_lower:
            return False

    for rule in rules:
        if rule.category != category:
            continue
        if rule.model_keyword is None:
            brand_lower = rule.brand.lower()
            if brand_lower in name_lower:
                return True
            if brand_lower in url.lower():
                return True
            if rule.brand == "ROCKSHOX" and ("rock shox" in name_lower or "rock-shox" in url.lower()):
                return True
        else:
            if rule.model_keyword in name_lower:
                return True

    return False


def extract_brand(name: str, url: str = "") -> str | None:
    url_lower = url.lower()
    brand_url_map = {
        "fox-racing": "FOX",
        "rock-shox": "ROCKSHOX",
        "rockshox": "ROCKSHOX",
        "shimano": "SHIMANO",
        "sram": "SRAM",
        "fox": "FOX",
    }
    for brand_key, brand_val in brand_url_map.items():
        if brand_key in url_lower:
            return brand_val

    name_upper = name.upper().replace("ROCK SHOX", "ROCKSHOX")
    for brand, keywords in BRAND_KEYWORDS.items():
        for keyword in keywords:
            if keyword in name_upper:
                return brand
    return None


def are_same_product(name_cr: str, name_bd: str, category: str) -> tuple[bool, float]:
    for attempt in range(3):
        try:
            response = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=50,
                messages=[{
                    "role": "user",
                    "content": f"""Same bike product? Category: {category}
P1: {name_cr}
P2: {name_bd}
JSON only: {{"same": true/false, "confidence": 0.0-1.0}}"""
                }]
            )
            raw = response.content[0].text
            match = re.search(r'\{[^}]+\}', raw)
            if match:
                result = json.loads(match.group())
                return result["same"], result["confidence"]
            return False, 0.0
        except Exception as e:
            print(f"  ⚠️ Błąd API (próba {attempt+1}/3): {e}")
            time.sleep(2 ** attempt)
    return False, 0.0


def match_with_ai(confidence_threshold: float = 0.92, limit: int = 200):
    db = SessionLocal()
    rules = load_filter_rules(db)

    cr_products = db.query(Product).filter_by(shop="centrumrowerowe.pl").all()
    bd_products = db.query(Product).filter_by(shop="bike-discount.de").all()

    cr_main = [p for p in cr_products if is_main_product(p.name, p.category, rules, p.url or "")]
    bd_main = [p for p in bd_products if is_main_product(p.name, p.category, rules, p.url or "")]

    print(f"CR po filtrowaniu: {len(cr_main)} produktów")
    print(f"BD po filtrowaniu: {len(bd_main)} produktów")

    bd_by_brand_cat = {}
    for bd in bd_main:
        brand = extract_brand(bd.name, bd.url) or "OTHER"
        key = (brand, bd.category)
        if key not in bd_by_brand_cat:
            bd_by_brand_cat[key] = []
        bd_by_brand_cat[key].append(bd)

    print("Marki BD:", {k: len(v) for k, v in bd_by_brand_cat.items()})

    matched = 0
    checked = 0

    for i, cr in enumerate(cr_main[:limit]):
        existing = db.query(MatchedProduct).filter_by(cr_product_id=cr.id).first()
        if existing:
            continue

        cr_brand = extract_brand(cr.name, cr.url) or "OTHER"
        bd_category = CATEGORY_MAP.get(cr.category, cr.category)

        if cr.category in ("widelce", "dampery"):
            candidates = (
                bd_by_brand_cat.get(("ROCKSHOX", bd_category), []) +
                bd_by_brand_cat.get(("FOX", bd_category), [])
            )
            max_candidates = 30
            local_threshold = 0.95
        else:
            candidates = bd_by_brand_cat.get((cr_brand, bd_category), [])
            max_candidates = 15
            local_threshold = confidence_threshold

        best_match = None
        best_confidence = 0.0

        for bd in candidates[:max_candidates]:
            checked += 1
            is_same, confidence = are_same_product(cr.name, bd.name, cr.category)

            if is_same and confidence >= local_threshold:
                if confidence > best_confidence:
                    best_match = bd
                    best_confidence = confidence

        if best_match:
            existing_match = db.query(MatchedProduct).filter_by(
                cr_product_id=cr.id,
                bd_product_id=best_match.id
            ).first()

            if not existing_match:
                match = MatchedProduct(
                    name_normalized=cr.name,
                    category=cr.category,
                    cr_product_id=cr.id,
                    cr_name=cr.name,
                    cr_price_pln=cr.price,
                    cr_url=cr.url,
                    bd_product_id=best_match.id,
                    bd_name=best_match.name,
                    bd_price_eur=best_match.price,
                    bd_url=best_match.url,
                    match_method="ai",
                    match_confidence=best_confidence,
                    matched_at=datetime.now(timezone.utc)
                )
                db.add(match)
                matched += 1
                print(f"✅ [{i+1}] {cr.name} → {best_match.name} ({best_confidence:.0%})")

        else:
            print(f"❌ [{i+1}] {cr.name[:50]} - brak matcha")

    db.commit()
    db.close()
    print(f"\nSprawdzono {checked} par, dopasowano {matched} produktów.")


if __name__ == "__main__":
    match_with_ai()