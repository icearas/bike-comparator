"""
Statyczne reguły filtrowania produktów (zastąpienie tabeli filter_rules z SQLite).
Używane przez is_main_product() w ai_matcher.py, mtb_matcher.py, bi_matcher.py.
"""

from types import SimpleNamespace


def _r(category, brand, model_keyword=None):
    return SimpleNamespace(category=category, brand=brand, model_keyword=model_keyword)


FILTER_RULES = [
    # PRZERZUTKI - Shimano
    _r("przerzutki", "SHIMANO", "rd-m6100"),
    _r("przerzutki", "SHIMANO", "rd-m6120"),
    _r("przerzutki", "SHIMANO", "rd-m6250"),
    _r("przerzutki", "SHIMANO", "rd-m6260"),
    _r("przerzutki", "SHIMANO", "rd-m7100"),
    _r("przerzutki", "SHIMANO", "rd-m7120"),
    _r("przerzutki", "SHIMANO", "rd-m8100"),
    _r("przerzutki", "SHIMANO", "rd-m8120"),
    _r("przerzutki", "SHIMANO", "rd-m8130"),
    _r("przerzutki", "SHIMANO", "rd-m8150"),
    _r("przerzutki", "SHIMANO", "rd-m8250"),
    _r("przerzutki", "SHIMANO", "rd-m8260"),
    _r("przerzutki", "SHIMANO", "rd-m9100"),
    _r("przerzutki", "SHIMANO", "rd-m9120"),
    _r("przerzutki", "SHIMANO", "rd-m9250"),
    _r("przerzutki", "SHIMANO", "rd-m9260"),
    # PRZERZUTKI - SRAM
    _r("przerzutki", "SRAM", "gx eagle"),
    _r("przerzutki", "SRAM", "x01 eagle"),
    _r("przerzutki", "SRAM", "xx1 eagle"),
    _r("przerzutki", "SRAM", "xx eagle"),
    _r("przerzutki", "SRAM", "x0 eagle"),
    _r("przerzutki", "SRAM", "eagle 70"),
    _r("przerzutki", "SRAM", "eagle 90"),
    # HAMULCE - Shimano
    _r("hamulce", "SHIMANO", "deore xt"),
    _r("hamulce", "SHIMANO", "br-m8"),
    _r("hamulce", "SHIMANO", "slx"),
    _r("hamulce", "SHIMANO", "br-m7"),
    _r("hamulce", "SHIMANO", "deore br"),
    _r("hamulce", "SHIMANO", "br-m6"),
    _r("hamulce", "SHIMANO", "xtr"),
    _r("hamulce", "SHIMANO", "br-m9"),
    # HAMULCE - SRAM
    _r("hamulce", "SRAM", "guide"),
    _r("hamulce", "SRAM", "maven"),
    _r("hamulce", "SRAM", "db8"),
    _r("hamulce", "SRAM", "db 8"),
    # KASETY - Shimano
    _r("kasety", "SHIMANO", "cs-m8"),
    _r("kasety", "SHIMANO", "cs-m7"),
    _r("kasety", "SHIMANO", "cs-m6"),
    _r("kasety", "SHIMANO", "cs-m9"),
    _r("kasety", "SHIMANO", "deore xt"),
    _r("kasety", "SHIMANO", "slx"),
    _r("kasety", "SHIMANO", "xtr"),
    # KASETY - SRAM
    _r("kasety", "SRAM", "gx eagle"),
    _r("kasety", "SRAM", "x01 eagle"),
    _r("kasety", "SRAM", "xx1 eagle"),
    _r("kasety", "SRAM", "xx eagle"),
    _r("kasety", "SRAM", "x0 eagle"),
    _r("kasety", "SRAM", "eagle 70"),
    _r("kasety", "SRAM", "eagle 90"),
    # ŁAŃCUCHY - Shimano
    _r("lancuchy", "SHIMANO", "cn-m8"),
    _r("lancuchy", "SHIMANO", "cn-m7"),
    _r("lancuchy", "SHIMANO", "cn-m6"),
    _r("lancuchy", "SHIMANO", "cn-m9"),
    _r("lancuchy", "SHIMANO", "deore xt"),
    _r("lancuchy", "SHIMANO", "slx"),
    _r("lancuchy", "SHIMANO", "xtr"),
    # ŁAŃCUCHY - SRAM
    _r("lancuchy", "SRAM", "gx eagle"),
    _r("lancuchy", "SRAM", "xx1 eagle"),
    _r("lancuchy", "SRAM", "eagle"),
    # WIDELCE - wszystkie modele
    _r("widelce", "ROCKSHOX"),
    _r("widelce", "FOX"),
    # AMORTYZATORY - wszystkie modele (widelce z CR)
    _r("amortyzatory", "ROCKSHOX"),
    _r("amortyzatory", "FOX"),
    # DAMPERY - tylne amortyzatory
    _r("dampery", "ROCKSHOX"),
    _r("dampery", "FOX"),
]
