"""
AI_MATCHER z pre-filtrem po numerze modelu + globalny rate limiter
"""

import json
import asyncio
import re
from anthropic import AsyncAnthropic
from models import SessionLocal, Product, MatchedProduct, FilterRule
from datetime import datetime, timezone
from dotenv import load_dotenv
import os
import time

load_dotenv(dotenv_path="../.env")
client = AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

CONFIDENCE_THRESHOLD = 0.95
PARALLEL_CALLS = 5
MODEL = "claude-haiku-4-5-20251001"

SKIP_KEYWORDS = [
    "kółka", "kólka", "wózek", "wozek", "ślizg", "slizg", "obejma",
    "śrubki", "srubki", "przymiar", "pulley", "pully", "cage",
    "klocki", "klocek", "okładziny", "okladziny", "linka", "pancerz",
    "płyn", "plyn", "zestaw do odpowietrzania", "seal kit", "spare",
    "bolt", "screw", "plate", "set for", "puly", "kolka", "wozek",
    "przerzutka przednia", "przednia shimano", "fd-", "kółko przerzutki",
    "tarcza", "rotor", "oneloc", "manetka blokady", "suntour", "sr suntour",
    "sora", "cs-hg50", "rock shox 35", "rockshox 35", "rock shox recon",
    "recon silver", "recon gold", "paragon", "domain", "microshift", "rd-t", "advent"
]

BRAND_KEYWORDS = {
    "SHIMANO": ["SHIMANO", "DEORE", "SLX", "XTR"],
    "SRAM": ["SRAM", "GX", "NX", "XX1", "X01", "EAGLE"],
    "ROCKSHOX": ["ROCKSHOX", "ROCK SHOX", "PIKE", "LYRIK", "ZEB", "SID", "JUDY", "REVELATION", "REBA", "YARI"],
    "FOX": ["FOX"],
}

CATEGORY_MAP = {"amortyzatory": "widelce"}


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
            if brand_lower in name_lower or brand_lower in (url or "").lower():
                return True
            if rule.brand == "ROCKSHOX" and ("rock shox" in name_lower or "rock-shox" in (url or "").lower()):
                return True
        else:
            if rule.model_keyword in name_lower:
                return True
    return False


def extract_brand(name: str, url: str = "") -> str:
    url_lower = (url or "").lower()
    brand_url_map = {
        "fox-racing": "FOX",
        "rock-shox": "ROCKSHOX",
        "rockshox": "ROCKSHOX",
        "shimano": "SHIMANO",
        "sram": "SRAM",
        "fox": "FOX",
    }
    for k, v in brand_url_map.items():
        if k in url_lower:
            return v
    name_upper = name.upper().replace("ROCK SHOX", "ROCKSHOX")
    for brand, kws in BRAND_KEYWORDS.items():
        if any(kw in name_upper for kw in kws):
            return brand
    return "OTHER"


def extract_model_numbers(name: str) -> list[str]:
    """Wyciąga wszystkie numery modeli np. BL-M9220, BR-M9200, RD-M6100"""
    name_upper = name.upper()
    results = re.findall(r'[A-Z]{1,3}-[A-Z]?\d{3,5}', name_upper)
    # SRAM cassette numbers: XG-1275 etc.
    results += re.findall(r'X[GS]-\d{4}', name_upper)
    # Short codes: DB8, M6100
    results += re.findall(r'\b(DB\d+|M\d{4})\b', name_upper)
    return list(set(results))


async def are_same_product(name_cr: str, name_bd: str, category: str) -> tuple[bool, float]:
    prompt = f"""Are these the exact same bike component model? Focus on model numbers AND product type.
Category: {category}
P1: {name_cr}
P2: {name_bd}
Rules:
- Model numbers must match
- Product type must match (single caliper ≠ brake set, front ≠ rear)
- A brake set (lever + caliper) can match a product listing both parts (e.g. BL-M9220/BR-M9200)
- Ignore cable length, color and speed count (11-speed, 12-speed) when model number matches
JSON only: {{"same": true/false, "confidence": 0.0-1.0}}"""

    for attempt in range(3):
        try:
            resp = await client.messages.create(
                model=MODEL,
                max_tokens=50,
                messages=[{"role": "user", "content": prompt}]
            )
            raw = resp.content[0].text
            match = re.search(r'\{[^}]+\}', raw)
            if match:
                result = json.loads(match.group())
                return result.get("same", False), result.get("confidence", 0.0)
            return False, 0.0
        except Exception as e:
            print(f"  ⚠️ Claude err {attempt+1}: {e}")
            await asyncio.sleep(2.0 * (2 ** attempt))
    return False, 0.0


_last_call = 0.0
_rate_lock = asyncio.Lock()


async def rate_limited_call(name_cr: str, name_bd: str, category: str) -> tuple[bool, float]:
    global _last_call
    async with _rate_lock:
        now = time.time()
        wait = 1.3 - (now - _last_call)
        if wait > 0:
            await asyncio.sleep(wait)
        _last_call = time.time()
    return await are_same_product(name_cr, name_bd, category)


async def match_with_ai(limit: int = 300):
    start = time.time()
    print(f"🚀 MATCHER | Limit: {limit} | Start: {time.strftime('%H:%M:%S')}")

    db = SessionLocal()
    rules = load_filter_rules(db)

    cr_products = db.query(Product).filter_by(shop="centrumrowerowe.pl").all()
    bd_products = db.query(Product).filter_by(shop="bike-discount.de").all()

    cr_main = [p for p in cr_products if is_main_product(p.name, p.category, rules, p.url or "")]
    bd_main = [p for p in bd_products if is_main_product(p.name, p.category, rules, p.url or "")]

    print(f"CR po filtrowaniu: {len(cr_main)} | BD po filtrowaniu: {len(bd_main)}")

    bd_by_brand_cat = {}
    for bd in bd_main:
        brand = extract_brand(bd.name, bd.url)
        key = (brand, bd.category)
        bd_by_brand_cat.setdefault(key, []).append(bd)

    semaphore = asyncio.Semaphore(PARALLEL_CALLS)
    matched = 0

    async def process_cr(i: int, cr: Product):
        nonlocal matched
        async with semaphore:
            existing = db.query(MatchedProduct).filter_by(cr_product_id=cr.id).first()
            if existing:
                return

            cr_brand = extract_brand(cr.name, cr.url)
            bd_category = CATEGORY_MAP.get(cr.category, cr.category)

            if cr.category in ("widelce", "dampery"):
                candidates = (
                    bd_by_brand_cat.get(("ROCKSHOX", bd_category), []) +
                    bd_by_brand_cat.get(("FOX", bd_category), [])
                )
            else:
                candidates = bd_by_brand_cat.get((cr_brand, bd_category), [])

            if not candidates:
                print(f"❌ [{i+1}] {cr.name[:50]} - brak kandydatów")
                return

            # Pre-filter po numerach modelu (obsługa wielu numerów np. BL-M9220 + BR-M9200)
            cr_models = extract_model_numbers(cr.name)
            if cr_models:
                filtered = [bd for bd in candidates if any(m in bd.name.upper() for m in cr_models)]
                if filtered:
                    candidates = filtered[:3]
                    print(f"🔍 [{i+1}] Pre-filter: {cr_models} → {len(candidates)} kandydatów")
                else:
                    candidates = candidates[:8]
            else:
                candidates = candidates[:8]

            # Sekwencyjne sprawdzanie - stop na pewnym matchu
            best_match = None
            best_confidence = 0.0
            for bd in candidates:
                is_same, confidence = await rate_limited_call(cr.name, bd.name, cr.category)
                if is_same and confidence >= CONFIDENCE_THRESHOLD:
                    if confidence > best_confidence:
                        best_match = bd
                        best_confidence = confidence
                    if confidence >= 0.99:
                        break

            if best_match:
                existing_match = db.query(MatchedProduct).filter_by(
                    cr_product_id=cr.id,
                    bd_product_id=best_match.id
                ).first()
                if not existing_match:
                    match_obj = MatchedProduct(
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
                        match_method="ai_model_prefilter",
                        match_confidence=best_confidence,
                        matched_at=datetime.now(timezone.utc)
                    )
                    db.add(match_obj)
                    db.commit()
                    matched += 1
                    print(f"✅ [{i+1}] {cr.name[:40]} → {best_match.name[:40]} ({best_confidence:.0%})")
            else:
                print(f"❌ [{i+1}] {cr.name[:50]} - brak matcha")

    tasks = [process_cr(i, cr) for i, cr in enumerate(cr_main[:limit])]
    await asyncio.gather(*tasks)

    db.close()

    elapsed_min = (time.time() - start) / 60
    print(f"\n🎯 WYNIK: {matched} matchów | {elapsed_min:.1f} min")


if __name__ == "__main__":
    asyncio.run(match_with_ai())