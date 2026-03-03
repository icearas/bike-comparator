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
PARALLEL_CALLS = 3
MODEL = "claude-haiku-4-5-20251001"

SKIP_KEYWORDS = [
    "kółka", "kólka", "wózek", "wozek", "ślizg", "slizg", "obejma",
    "śrubki", "srubki", "przymiar", "pulley", "pully", "cage",
    "klocki", "klocek", "okładziny", "okladziny", "linka", "pancerz",
    "płyn", "plyn", "zestaw do odpowietrzania", "seal kit", "spare",
    "bolt", "screw", "plate", "set for", "puly", "kolka",  # "wozek" usunięty — duplikat
    "przerzutka przednia", "przednia shimano", "fd-", "kółko przerzutki",
    "tarcza", "rotor", "oneloc", "manetka blokady", "suntour", "sr suntour",
    "sora", "cs-hg50", "rock shox 35", "rockshox 35", "rock shox recon",
    "recon silver", "recon gold", "paragon", "domain", "microshift", "rd-t", "advent",
    " + ",  # produkty combo (np. kaseta + łańcuch) — nie mają odpowiednika w BD
    # BD: narzędzia serwisowe
    "tool",
    # BD: zestawy do napraw i ulepszeń
    "rebuild", "upgrade kit", "service kit",
    # BD: płyny, pompy
    "fluid", "pump",
    # BD: małe części serwisowe zawieszeń
    "wiper", "bushing", "lower leg", "crush washer",
    # BD: tokeny powietrzne i spejsery objętości
    "token", "volume spacer",
    # BD: naklejki/kosmetyka
    "decal", "sticker",
    # BD: komponenty osi powietrznej
    "air shaft", "air cap",
    # BD: zawieszenie pod konkretne modele rowerów (nie mają odpowiednika w CR)
    "flight attendant",
    # BD: pojedyncze zębatki (nie całe kasety)
    "sprocket",
    # BD: lockringi z dystansami (części serwisowe)
    "lock ring with",
    # BD: zestawy zużycia (kaseta + łańcuch combo)
    "wear and tear",
    # BD: jednostki osi przerzutek (części)
    "axle unit",
    # CR: Fox 32/34 — BD nie ma tych modeli (odfiltrowane po stronie BD)
    "fox racing shox 32", "fox racing shox 34",
    # CR: części serwisowe zawieszenia przez polskie nazwy
    "tokeny", "zestaw naprawczy", "zestaw montażowy", "zestaw czujników",
    "pokrętło", "podkładka", "tuleje", "tulejka", "uchwyt", "spacer kit",
    "upgrade kit fox", "kapa rock",
    "odbojniki",                             # CR: odbojniki amortyzatora — akcesorium, nie widelec
    "kontroler elektroniczny",               # CR: kontroler AXS/Flight Attendant — elektronika
    # BD: części serwisowe zawieszenia, które ominęły SUSPENSION_SKIP (różne formy zapisu)
    "servicekit",                            # "Fork ServiceKit" (bez spacji)
    "vise block",                            # "Charger Vise Blocks", "SIDLuxe Vise Blocks"
    "sealhead",                              # "Charger 2.1 Sealhead"
    "seal head",                             # "ZEB DebonAir C1 Seal Head"
    "knob",                                  # "Charger 3 RC2 Rebound Damper Knob"
    "assy",                                  # "36/38 Grip Damper Shaft Assy"
    "cartridge",                             # "Float GripX2 Cartridge"
    "bumper stop",                           # "BoXXer Bumper Stop Kit", "40 Bumper Steering Stop"
    "for deft", "for jab",                   # BD: zawieszenia pod konkretne rowery e-bike
    # Modele poza zakresem — brak odpowiednika w BD lub celowo wykluczone
    "revelation", "reba", "rudy", "judy",
    "rock shox sid", "sid sl", "sidluxe",   # SID widelce i damper
    "deluxe", "monarch",                     # stare/wykluczone szoki RS
    "nx eagle",                              # SRAM NX — budżetowa linia poza zakresem
]

# Słowa kluczowe modeli zawieszenia — używane do pre-filtrowania kandydatów
# Kolejność ważna: dłuższe frazy przed krótszymi (float x2 przed float x)
SUSPENSION_MODEL_KEYWORDS = [
    "float x2", "float dps", "float sl", "float x",
    "dhx2", "dhx",
    "vivid",
    "boxxer",
    "pike", "lyrik", "zeb", "yari", "psylo",
]

BRAND_KEYWORDS = {
    "SHIMANO": ["SHIMANO", "DEORE", "SLX", "XTR"],
    "SRAM": ["SRAM", "GX", "NX", "XX1", "X01", "EAGLE"],
    "ROCKSHOX": ["ROCKSHOX", "ROCK SHOX", "PIKE", "LYRIK", "ZEB", "SID", "JUDY", "REVELATION", "REBA", "YARI"],
    "FOX": ["FOX"],
}

CATEGORY_MAP = {"amortyzatory": "widelce"}

# FOX grades (od najwyższego): Factory > Performance Elite > Performance E-Optimized > Performance > Rhythm
# RockShox grades (od najwyższego): Ultimate > Select+ > Select > R
FOX_GRADES = ["factory", "performance elite", "e-optimized", "performance", "rhythm"]
RS_GRADES = ["ultimate", "select+", "select"]


def extract_suspension_grade(name: str) -> str | None:
    """Wyciąga grade produktu zawieszenia. Zwraca None jeśli nie rozpoznano."""
    name_lower = name.lower()
    if "fox" in name_lower:
        for grade in FOX_GRADES:
            if grade in name_lower:
                return f"fox_{grade.replace(' ', '_')}"
        return "fox_ungraded"  # FOX bez grade → nie matchuj do żadnego konkretnego grade'u
    # RockShox — sprawdź dłuższe frazy przed krótszymi
    for grade in RS_GRADES:
        if grade in name_lower:
            return f"rs_{grade.replace('+', 'plus').replace(' ', '_')}"
    # Standalone "R" na końcu (np. "ZEB R", "Pike R") — bez fałszywych trafień
    if re.search(r'\bR\b', name.upper()):
        return "rs_r"
    return None


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
    """Wyciąga numery modeli (Shimano/SRAM) oraz nazwy modeli zawieszenia (Pike, Lyrik, ZEB itp.)"""
    name_upper = name.upper()
    # Standard: RD-M6100, BL-M9220, BR-M820 (0-1 litera po myślniku)
    results = re.findall(r'[A-Z]{1,3}-[A-Z]?\d{3,5}', name_upper)
    # Dwuliterowe prefiksy: BR-MT520, CN-HG601, CS-HG81 (dokładnie 2 litery po myślniku)
    results += re.findall(r'[A-Z]{1,3}-[A-Z]{2}\d{2,5}', name_upper)
    # SRAM cassette numbers: XG-1275 etc.
    results += re.findall(r'X[GS]-\d{4}', name_upper)
    # Short codes: DB8, M6100
    results += re.findall(r'\b(DB\d+|M\d{4})\b', name_upper)
    # Fox fork sizes: "FOX RACING SHOX 36 Float" → "36"
    if "FOX" in name_upper:
        fox_size = re.search(r'\b(36|38|40)\b', name_upper)
        if fox_size:
            results.append(fox_size.group(1))
    # Suspension model keywords: Pike, Lyrik, ZEB, SIDLuxe, Vivid, Float X2 itp.
    name_lower = name.lower()
    for model in SUSPENSION_MODEL_KEYWORDS:
        if model in name_lower:
            results.append(model.upper())
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
- For suspension (forks/shocks): grade must match exactly — RockShox: Select ≠ Select+ ≠ Ultimate ≠ R; FOX: Factory ≠ Performance Elite ≠ Performance ≠ Performance E-Optimized ≠ Rhythm; ignore wheel size (27.5"/29") and travel (mm) when model AND grade match; damper/cartridge version differences (e.g. Charger 3 vs Charger 3.1) count as different products
Respond only with JSON, no explanation: {{"same": true/false, "confidence": 0.0-1.0}}"""

    for attempt in range(5):
        try:
            # FIX: timeout 30s — zapobiega nieskończonemu wiszeniu przy braku odpowiedzi API
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


_last_call = 0.0
_rate_lock = asyncio.Lock()


async def rate_limited_call(name_cr: str, name_bd: str, category: str) -> tuple[bool, float]:
    global _last_call
    # FIX: "ticket scheduling" — lock trzymany tylko przez chwilę (bez sleep w środku!)
    # Każdy call dostaje zaplanowany czas startu, potem śpi poza lockiem
    # → do PARALLEL_CALLS callów może spać równolegle i startować jednocześnie
    async with _rate_lock:
        now = time.time()
        scheduled_at = max(now, _last_call + 1.3)
        _last_call = scheduled_at
    sleep_time = scheduled_at - time.time()
    if sleep_time > 0:
        await asyncio.sleep(sleep_time)  # sleep POZA lockiem — prawdziwy równoległy start
    return await are_same_product(name_cr, name_bd, category)


async def match_with_ai(limit: int = 300):
    start = time.time()
    print(f"🚀 MATCHER | Limit: {limit} | Start: {time.strftime('%H:%M:%S')}")

    db = SessionLocal()
    try:
        rules = load_filter_rules(db)
        cr_products = db.query(Product).filter_by(shop="centrumrowerowe.pl").all()
        bd_products = db.query(Product).filter_by(shop="bike-discount.de").all()

        cr_main = [p for p in cr_products if is_main_product(p.name, p.category, rules, p.url or "")]
        bd_main = [p for p in bd_products if is_main_product(p.name, p.category, rules, p.url or "")]
    finally:
        db.close()

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

        # Semafora wokół całej funkcji — limituje do PARALLEL_CALLS równoległych tasków
        # (nie 181 jednocześnie), ale ticket scheduling w rate_limited_call zapewnia
        # że te 3 taski naprawdę startują API calle równolegle co 1.3s
        async with semaphore:
            task_db = SessionLocal()
            try:
                existing = task_db.query(MatchedProduct).filter_by(cr_product_id=cr.id).first()
                if existing:
                    return

                cr_brand = extract_brand(cr.name, cr.url)
                bd_category = CATEGORY_MAP.get(cr.category, cr.category)

                if cr.category in ("widelce", "dampery"):
                    # CR przechowuje szoki (dampery) jako "widelce" (z amortyzatory scrape)
                    # → szukamy w OBIE kategoriach BD: widelce i dampery
                    candidates = (
                        bd_by_brand_cat.get((cr_brand, "widelce"), []) +
                        bd_by_brand_cat.get((cr_brand, "dampery"), [])
                    )
                    # Pre-filter po grade (Factory ≠ Performance ≠ Rhythm, Select ≠ Ultimate ≠ R)
                    cr_grade = extract_suspension_grade(cr.name)
                    if cr_grade:
                        grade_filtered = [bd for bd in candidates if extract_suspension_grade(bd.name) == cr_grade]
                        if grade_filtered:
                            candidates = grade_filtered
                        else:
                            # BD nie ma tego grade'u — brak matcha
                            print(f"❌ [{i+1}] {cr.name[:50]} - BD nie ma grade '{cr_grade}'")
                            return
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
                        candidates = candidates[:5]
                else:
                    candidates = candidates[:5]

                best_match = None
                best_confidence = 0.0
                for bd in candidates:
                    is_same, confidence = await rate_limited_call(cr.name, bd.name, cr.category)
                    if is_same and confidence >= CONFIDENCE_THRESHOLD:
                        best_match = bd
                        best_confidence = confidence
                        break  # pierwszy dobry match wystarczy — pre-filter już wybrał kandydatów

                if best_match:
                    existing_match = task_db.query(MatchedProduct).filter_by(
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
                        task_db.add(match_obj)
                        task_db.commit()
                        matched += 1
                        print(f"✅ [{i+1}] {cr.name[:40]} → {best_match.name[:40]} ({best_confidence:.0%})")
                else:
                    print(f"❌ [{i+1}] {cr.name[:50]} - brak matcha")
            finally:
                task_db.close()

    tasks = [process_cr(i, cr) for i, cr in enumerate(cr_main[:limit])]
    await asyncio.gather(*tasks)

    elapsed_min = (time.time() - start) / 60
    print(f"\n🎯 WYNIK: {matched} matchów | {elapsed_min:.1f} min")


if __name__ == "__main__":
    asyncio.run(match_with_ai())
