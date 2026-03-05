"""
BI_MATCHER — dopasowywanie CR ↔ bikeinn.com przez AI
Wyniki zapisywane do data/bi_matched.csv
"""

import csv
import json
import asyncio
import re
import time
from pathlib import Path
from datetime import datetime, timezone
from anthropic import AsyncAnthropic
from dotenv import load_dotenv
import os

from models import SessionLocal, Product
from ai_matcher import (
    SKIP_KEYWORDS, CATEGORY_MAP, CONFIDENCE_THRESHOLD, MODEL, PARALLEL_CALLS,
    extract_suspension_grade, load_filter_rules, is_main_product,
    extract_brand, extract_model_numbers, SUSPENSION_MODEL_KEYWORDS,
)

load_dotenv(dotenv_path="../.env")
client = AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

OUT_PATH = Path(__file__).parent.parent / "data" / "bi_matched.csv"

_last_call = 0.0
_rate_lock = asyncio.Lock()


async def are_same_product(name_cr: str, name_bi: str, category: str) -> tuple[bool, float]:
    prompt = f"""Are these the exact same bike component model? Focus on model numbers AND product type.
Category: {category}
P1: {name_cr}
P2: {name_bi}
Rules:
- Model numbers must match
- Product type must match (single caliper ≠ brake set, front ≠ rear)
- A brake set (lever + caliper) can match a product listing both parts (e.g. BL-M9220/BR-M9200)
- Ignore cable length, color and speed count (11-speed, 12-speed) when model number matches
- For suspension (forks/shocks): grade must match exactly — RockShox: Select ≠ Select+ ≠ Ultimate ≠ R; FOX: Factory ≠ Performance Elite ≠ Performance ≠ Performance E-Optimized ≠ Rhythm; ignore wheel size (27.5"/29") and travel (mm) when model AND grade match; damper/cartridge version differences (e.g. Charger 3 vs Charger 3.1) count as different products
Respond only with JSON, no explanation: {{"same": true/false, "confidence": 0.0-1.0}}"""

    for attempt in range(5):
        try:
            resp = await asyncio.wait_for(
                client.messages.create(
                    model=MODEL,
                    max_tokens=50,
                    messages=[{"role": "user", "content": prompt}]
                ),
                timeout=30.0
            )
            raw = resp.content[0].text
            match = re.search(r'\{[^}]+\}', raw)
            if match:
                result = json.loads(match.group())
                return result.get("same", False), result.get("confidence", 0.0)
            return False, 0.0
        except asyncio.TimeoutError:
            wait_sec = 5.0 * (attempt + 1)
            print(f"  ⚠️ Claude err {attempt+1} (timeout 30s) — czekam {wait_sec:.0f}s")
            await asyncio.sleep(wait_sec)
        except Exception as e:
            err_str = str(e)
            if "429" in err_str or "rate_limit" in err_str.lower() or "concurrent" in err_str.lower():
                wait_sec = 20.0 + attempt * 10
                print(f"  ⚠️ Claude err {attempt+1} (rate limit) — czekam {wait_sec:.0f}s")
            elif "529" in err_str or "overloaded" in err_str.lower():
                wait_sec = 30.0 + attempt * 15
                print(f"  ⚠️ Claude err {attempt+1} (overloaded) — czekam {wait_sec:.0f}s")
            elif "500" in err_str:
                wait_sec = 10.0 * (attempt + 1)
                print(f"  ⚠️ Claude err {attempt+1} (server error) — czekam {wait_sec:.0f}s")
            else:
                wait_sec = 2.0 * (2 ** attempt)
                print(f"  ⚠️ Claude err {attempt+1}: {e}")
            await asyncio.sleep(wait_sec)
    return False, 0.0


async def rate_limited_call(name_cr: str, name_bi: str, category: str) -> tuple[bool, float]:
    global _last_call
    async with _rate_lock:
        now = time.time()
        scheduled_at = max(now, _last_call + 1.3)
        _last_call = scheduled_at
    sleep_time = scheduled_at - time.time()
    if sleep_time > 0:
        await asyncio.sleep(sleep_time)
    return await are_same_product(name_cr, name_bi, category)


async def match_bi(limit: int = 300):
    start = time.time()
    print(f"🚀 BI MATCHER | Limit: {limit} | Start: {time.strftime('%H:%M:%S')}")

    db = SessionLocal()
    try:
        rules = load_filter_rules(db)
        cr_products = db.query(Product).filter_by(shop="centrumrowerowe.pl").all()
        bi_products = db.query(Product).filter_by(shop="bikeinn.com").all()
    finally:
        db.close()

    cr_main = [p for p in cr_products if is_main_product(p.name, p.category, rules, p.url or "")]
    bi_main = [p for p in bi_products if is_main_product(p.name, p.category, rules, p.url or "")]

    print(f"CR po filtrowaniu: {len(cr_main)} | BI po filtrowaniu: {len(bi_main)}")

    bi_by_brand_cat: dict[tuple, list] = {}
    for bi in bi_main:
        brand = extract_brand(bi.name, bi.url)
        key = (brand, bi.category)
        bi_by_brand_cat.setdefault(key, []).append(bi)

    semaphore = asyncio.Semaphore(PARALLEL_CALLS)
    results: list[dict] = []
    results_lock = asyncio.Lock()
    matched = 0

    async def process_cr(i: int, cr: Product):
        nonlocal matched
        async with semaphore:
            cr_brand = extract_brand(cr.name, cr.url)
            bi_category = CATEGORY_MAP.get(cr.category, cr.category)

            if cr.category in ("widelce", "dampery"):
                candidates = (
                    bi_by_brand_cat.get((cr_brand, "widelce"), []) +
                    bi_by_brand_cat.get((cr_brand, "dampery"), [])
                )
                cr_grade = extract_suspension_grade(cr.name)
                if cr_grade:
                    grade_filtered = [m for m in candidates if extract_suspension_grade(m.name) == cr_grade]
                    if grade_filtered:
                        candidates = grade_filtered
                    else:
                        print(f"❌ [{i+1}] {cr.name[:50]} - BI nie ma grade '{cr_grade}'")
                        return
            else:
                candidates = bi_by_brand_cat.get((cr_brand, bi_category), [])

            if not candidates:
                print(f"❌ [{i+1}] {cr.name[:50]} - brak kandydatów")
                return

            cr_models = extract_model_numbers(cr.name)
            if cr_models:
                filtered = [m for m in candidates if any(mod in m.name.upper() for mod in cr_models)]
                candidates = filtered[:3] if filtered else candidates[:5]
                if filtered:
                    print(f"🔍 [{i+1}] Pre-filter: {cr_models} → {len(candidates)} kandydatów")
            else:
                candidates = candidates[:5]

            best_match = None
            best_confidence = 0.0
            for bi in candidates:
                is_same, confidence = await rate_limited_call(cr.name, bi.name, cr.category)
                if is_same and confidence >= CONFIDENCE_THRESHOLD:
                    best_match = bi
                    best_confidence = confidence
                    break

            if best_match:
                async with results_lock:
                    results.append({
                        "category": cr.category,
                        "cr_name": cr.name,
                        "cr_price_pln": cr.price,
                        "cr_url": cr.url or "",
                        "bi_name": best_match.name,
                        "bi_price_pln": best_match.price,
                        "bi_url": best_match.url or "",
                        "match_confidence": best_confidence,
                        "matched_at": datetime.now(timezone.utc).isoformat(),
                    })
                    matched += 1
                print(f"✅ [{i+1}] {cr.name[:40]} → {best_match.name[:40]} ({best_confidence:.0%})")
            else:
                print(f"❌ [{i+1}] {cr.name[:50]} - brak matcha")

    tasks = [process_cr(i, cr) for i, cr in enumerate(cr_main[:limit])]
    await asyncio.gather(*tasks)

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "category", "cr_name", "cr_price_pln", "cr_url",
            "bi_name", "bi_price_pln", "bi_url",
            "match_confidence", "matched_at",
        ])
        writer.writeheader()
        writer.writerows(results)

    elapsed_min = (time.time() - start) / 60
    print(f"\n🎯 WYNIK: {matched} matchów | {elapsed_min:.1f} min")
    print(f"📄 Zapisano do: {OUT_PATH}")


if __name__ == "__main__":
    asyncio.run(match_bi())
