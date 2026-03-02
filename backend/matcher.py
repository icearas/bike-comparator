import re
from models import SessionLocal, Product, MatchedProduct
from datetime import datetime


def extract_code(name: str) -> str | None:
    """Wyciąga kod produktu z nazwy, np. RD-M8100, M8100, GX Eagle."""
    name_upper = name.upper()
    
    # Shimano kody: RD-M8100, FD-M310, BR-M8100 itp.
    shimano = re.search(r'[A-Z]{2}-[A-Z]\d{4,5}', name_upper)
    if shimano:
        return shimano.group()
    
    # SRAM serie: GX EAGLE, XX1 EAGLE, NX EAGLE itp.
    sram = re.search(r'(GX|NX|XX1|X01|SX|X0|XX)\s*(EAGLE)?', name_upper)
    if sram:
        return sram.group().strip()
    
    # RockShox modele: ZEB, LYRIK, PIKE, SID, RECON itp.
    rockshox = re.search(r'(ZEB|LYRIK|PIKE|SID|RECON|REVELATION|JUDY|DOMAIN|PARAGON|35 GOLD|35 SILVER)', name_upper)
    if rockshox:
        return rockshox.group().strip()
    
    return None


def normalize_name(name: str) -> str:
    """Normalizuje nazwę do porównania."""
    name = name.upper()
    name = name.replace("ROCK SHOX", "ROCKSHOX")
    name = re.sub(r'\s+', ' ', name)
    name = re.sub(r'[^A-Z0-9 -]', '', name)
    return name.strip()


def match_products():
    db = SessionLocal()
    
    # Pobierz wszystkie produkty z obu sklepów
    cr_products = db.query(Product).filter_by(shop="centrumrowerowe.pl").all()
    bd_products = db.query(Product).filter_by(shop="bike-discount.de").all()
    
    print(f"CR: {len(cr_products)} produktów")
    print(f"BD: {len(bd_products)} produktów")
    
    matched = 0
    
    for cr in cr_products:
        cr_code = extract_code(cr.name)
        cr_norm = normalize_name(cr.name)
        
        best_match = None
        best_method = None
        
        for bd in bd_products:
            # Tylko ta sama kategoria
            if cr.category != bd.category:
                # Wyjątek dla zawieszenia
                if not (cr.category == "amortyzatory" and bd.category in ["widelce", "dampery"]):
                    continue
            
            bd_code = extract_code(bd.name)
            bd_norm = normalize_name(bd.name)
            
            # Match po kodzie produktu (najlepszy)
            if cr_code and bd_code and cr_code == bd_code:
                best_match = bd
                best_method = "code"
                break
            
            # Match po fragmentach nazwy
            cr_words = set(cr_norm.split())
            bd_words = set(bd_norm.split())
            common = cr_words & bd_words
            
            # Przynajmniej 3 wspólne słowa (bez krótkich)
            meaningful = [w for w in common if len(w) > 2]
            if len(meaningful) >= 3:
                best_match = bd
                best_method = "name"
        
        if best_match:
            # Sprawdź czy match już istnieje
            existing = db.query(MatchedProduct).filter_by(
                cr_product_id=cr.id,
                bd_product_id=best_match.id
            ).first()
            
            if not existing:
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
                    match_method=best_method,
                    match_confidence=1.0 if best_method == "code" else 0.7,
                    matched_at=datetime.utcnow()
                )
                db.add(match)
                matched += 1
    
    db.commit()
    db.close()
    print(f"\nZdopasowano {matched} par produktów.")


if __name__ == "__main__":
    match_products()