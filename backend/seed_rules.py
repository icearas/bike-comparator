cat > seed_rules.py << 'EOF'
from models import SessionLocal, FilterRule, init_db

def seed_rules():
    db = SessionLocal()
    db.query(FilterRule).delete()
    
    rules = [
        # PRZERZUTKI - Shimano
        {"category": "przerzutki", "brand": "SHIMANO", "model_keyword": "rd-m6100"},
        {"category": "przerzutki", "brand": "SHIMANO", "model_keyword": "rd-m6120"},
        {"category": "przerzutki", "brand": "SHIMANO", "model_keyword": "rd-m7100"},
        {"category": "przerzutki", "brand": "SHIMANO", "model_keyword": "rd-m7120"},
        {"category": "przerzutki", "brand": "SHIMANO", "model_keyword": "rd-m8100"},
        {"category": "przerzutki", "brand": "SHIMANO", "model_keyword": "rd-m8120"},
        {"category": "przerzutki", "brand": "SHIMANO", "model_keyword": "rd-m8130"},
        {"category": "przerzutki", "brand": "SHIMANO", "model_keyword": "rd-m9100"},
        {"category": "przerzutki", "brand": "SHIMANO", "model_keyword": "rd-m9120"},
        {"category": "przerzutki", "brand": "SHIMANO", "model_keyword": "rd-m8250"},
        # PRZERZUTKI - SRAM
        {"category": "przerzutki", "brand": "SRAM", "model_keyword": "gx eagle"},
        {"category": "przerzutki", "brand": "SRAM", "model_keyword": "nx eagle"},
        {"category": "przerzutki", "brand": "SRAM", "model_keyword": "x01 eagle"},
        {"category": "przerzutki", "brand": "SRAM", "model_keyword": "xx1 eagle"},
        {"category": "przerzutki", "brand": "SRAM", "model_keyword": "xx eagle"},
        {"category": "przerzutki", "brand": "SRAM", "model_keyword": "x0 eagle"},
        {"category": "przerzutki", "brand": "SRAM", "model_keyword": "eagle 70"},
        {"category": "przerzutki", "brand": "SRAM", "model_keyword": "eagle 90"},
        # HAMULCE - Shimano
        {"category": "hamulce", "brand": "SHIMANO", "model_keyword": "deore xt"},
        {"category": "hamulce", "brand": "SHIMANO", "model_keyword": "br-m8"},
        {"category": "hamulce", "brand": "SHIMANO", "model_keyword": "slx"},
        {"category": "hamulce", "brand": "SHIMANO", "model_keyword": "br-m7"},
        {"category": "hamulce", "brand": "SHIMANO", "model_keyword": "deore br"},
        {"category": "hamulce", "brand": "SHIMANO", "model_keyword": "br-m6"},
        {"category": "hamulce", "brand": "SHIMANO", "model_keyword": "xtr"},
        {"category": "hamulce", "brand": "SHIMANO", "model_keyword": "br-m9"},
        # HAMULCE - SRAM
        {"category": "hamulce", "brand": "SRAM", "model_keyword": "guide"},
        {"category": "hamulce", "brand": "SRAM", "model_keyword": "maven"},
        {"category": "hamulce", "brand": "SRAM", "model_keyword": "db8"},
        {"category": "hamulce", "brand": "SRAM", "model_keyword": "db 8"},
        # KASETY - Shimano
        {"category": "kasety", "brand": "SHIMANO", "model_keyword": "cs-m8"},
        {"category": "kasety", "brand": "SHIMANO", "model_keyword": "cs-m7"},
        {"category": "kasety", "brand": "SHIMANO", "model_keyword": "cs-m6"},
        {"category": "kasety", "brand": "SHIMANO", "model_keyword": "cs-m9"},
        {"category": "kasety", "brand": "SHIMANO", "model_keyword": "deore xt"},
        {"category": "kasety", "brand": "SHIMANO", "model_keyword": "slx"},
        {"category": "kasety", "brand": "SHIMANO", "model_keyword": "xtr"},
        # KASETY - SRAM
        {"category": "kasety", "brand": "SRAM", "model_keyword": "gx eagle"},
        {"category": "kasety", "brand": "SRAM", "model_keyword": "nx eagle"},
        {"category": "kasety", "brand": "SRAM", "model_keyword": "x01 eagle"},
        {"category": "kasety", "brand": "SRAM", "model_keyword": "xx1 eagle"},
        {"category": "kasety", "brand": "SRAM", "model_keyword": "xx eagle"},
        {"category": "kasety", "brand": "SRAM", "model_keyword": "x0 eagle"},
        {"category": "kasety", "brand": "SRAM", "model_keyword": "eagle 70"},
        {"category": "kasety", "brand": "SRAM", "model_keyword": "eagle 90"},
        # ŁAŃCUCHY - Shimano
        {"category": "lancuchy", "brand": "SHIMANO", "model_keyword": "cn-m8"},
        {"category": "lancuchy", "brand": "SHIMANO", "model_keyword": "cn-m7"},
        {"category": "lancuchy", "brand": "SHIMANO", "model_keyword": "cn-m6"},
        {"category": "lancuchy", "brand": "SHIMANO", "model_keyword": "cn-m9"},
        {"category": "lancuchy", "brand": "SHIMANO", "model_keyword": "deore xt"},
        {"category": "lancuchy", "brand": "SHIMANO", "model_keyword": "slx"},
        {"category": "lancuchy", "brand": "SHIMANO", "model_keyword": "xtr"},
        # ŁAŃCUCHY - SRAM
        {"category": "lancuchy", "brand": "SRAM", "model_keyword": "gx eagle"},
        {"category": "lancuchy", "brand": "SRAM", "model_keyword": "nx eagle"},
        {"category": "lancuchy", "brand": "SRAM", "model_keyword": "xx1 eagle"},
        {"category": "lancuchy", "brand": "SRAM", "model_keyword": "eagle"},
        # WIDELCE - wszystkie modele
        {"category": "widelce", "brand": "ROCKSHOX", "model_keyword": None},
        {"category": "widelce", "brand": "FOX", "model_keyword": None},
        # AMORTYZATORY - wszystkie modele
        {"category": "amortyzatory", "brand": "ROCKSHOX", "model_keyword": None},
        {"category": "amortyzatory", "brand": "FOX", "model_keyword": None},
        # DAMPERY - wszystkie modele
        {"category": "dampery", "brand": "ROCKSHOX", "model_keyword": None},
        {"category": "dampery", "brand": "FOX", "model_keyword": None},
    ]

    for r in rules:
        db.add(FilterRule(**r))
    
    db.commit()
    db.close()
    print(f"Dodano {len(rules)} reguł filtrowania.")


if __name__ == "__main__":
    init_db()
    seed_rules()
EOF
python seed_rules.py