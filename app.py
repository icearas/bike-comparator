import streamlit as st
import pandas as pd
import psycopg2
import os
import urllib.request
import urllib.parse
import json


def _get_db_url() -> str:
    try:
        return st.secrets["DATABASE_URL"]
    except Exception:
        return os.getenv("DATABASE_URL", "postgresql://arkadiuszmichnej@localhost/bike_tracker")

CATEGORY_LABELS = {
    "hamulce": "Hamulce",
    "kasety": "Kasety",
    "lancuchy": "Łańcuchy",
    "przerzutki": "Przerzutki",
    "widelce": "Widelce",
    "dampery": "Dampery",
    "manetki": "Manetki",
}

st.set_page_config(
    page_title="Bike Parts Price Comparator",
    page_icon="🚵",
    layout="wide",
)

st.title("🚵 Bike Comparator")
st.caption("centrumrowerowe.pl  vs  bike-discount.de  vs  mtbiker.pl  vs  bikeinn.com")


def allegro_url(cr_name: str) -> str:
    # Wyciągnij numer modelu jeśli istnieje (np. RD-M8100, CS-M8100, BL-M9220)
    import re
    m = re.search(r'[A-Z]{2,3}-[A-Z]?\d{4,6}', cr_name.upper())
    query = m.group(0) if m else cr_name
    return f"https://allegro.pl/listing?string={urllib.parse.quote_plus(query)}&order=p&stan=nowe"


@st.cache_data(ttl=3600)
def fetch_eur_rate() -> float:
    try:
        url = "https://api.nbp.pl/api/exchangerates/rates/a/eur/?format=json"
        with urllib.request.urlopen(url, timeout=5) as resp:
            data = json.loads(resp.read())
        return round(data["rates"][0]["mid"], 4)
    except Exception:
        return 4.25


@st.cache_data(ttl=3600)
def load_data() -> pd.DataFrame:
    conn = psycopg2.connect(_get_db_url())
    cur = conn.cursor()
    cur.execute("SELECT * FROM v_price_comparison")
    cols = [desc[0] for desc in cur.description]
    rows = cur.fetchall()
    cur.close()
    conn.close()
    df = pd.DataFrame(rows, columns=cols)
    # Pomiń wiersze bez ceny CR (canonical produkt bez listingu CR)
    df = df[df["cr_price_pln"].notna()].copy()
    # psycopg2 zwraca Decimal dla numeric — konwertuj na float
    for col in ["cr_price_pln", "bd_price_eur", "mtb_price_pln", "bi_price_pln"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


df = load_data()
import datetime
_last_updated = df["last_updated"].max()
if pd.notna(_last_updated):
    last_updated = pd.Timestamp(_last_updated).strftime("%d.%m.%Y")
else:
    last_updated = "—"
st.caption(f"Ostatnia aktualizacja danych: {last_updated}")

st.markdown(
    """<a href="https://buycoffee.to/icearas" rel="noreferrer noopener" target="_blank">
    <img src="https://buycoffee.to/btn/buycoffeeto-btn-primary.svg" style="height:36px">
    </a>""",
    unsafe_allow_html=True,
)

# ── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Ustawienia")

    nbp_rate = fetch_eur_rate()
    eur_rate = st.number_input(
        "Kurs EUR → PLN",
        min_value=3.5,
        max_value=6.0,
        value=nbp_rate,
        step=0.05,
        format="%.4f",
        help=f"Kurs NBP z dnia dzisiejszego: {nbp_rate:.4f}. Możesz go ręcznie nadpisać.",
    )

    st.divider()
    st.header("🔍 Filtry")

    all_categories = sorted(df["category"].unique().tolist())
    category_display = ["Wszystkie"] + [CATEGORY_LABELS.get(c, c) for c in all_categories]
    category_map = {CATEGORY_LABELS.get(c, c): c for c in all_categories}

    selected_label = st.selectbox("Kategoria", category_display)

    BRANDS = ["Shimano", "SRAM", "RockShox", "FOX"]
    selected_brands = st.multiselect(
        "Marka",
        options=BRANDS,
        default=[],
        placeholder="Wszystkie marki",
    )

    SHOPS = ["centrumrowerowe.pl", "bike-discount.de", "mtbiker.pl", "bikeinn.com"]
    selected_shops = st.multiselect(
        "Dostępne w sklepie",
        options=SHOPS,
        default=[],
        placeholder="Wszystkie sklepy",
    )

search_query = st.text_input(
    "🔎 Szukaj produktu",
    placeholder="np. Shimano, FOX 36, XT...",
    help="Filtruje produkty po nazwie (CR lub BD).",
)

# ── Obliczenia ────────────────────────────────────────────────────────────────
filtered = df.copy()

if selected_label != "Wszystkie":
    filtered = filtered[filtered["category"] == category_map[selected_label]]

filtered["bd_price_pln"] = (filtered["bd_price_eur"] * eur_rate).round(2)
filtered["oszczednosc_pln"] = (filtered["cr_price_pln"] - filtered["bd_price_pln"]).round(2)
filtered["oszczednosc_pct"] = (
    filtered["oszczednosc_pln"] / filtered["cr_price_pln"] * 100
).round(1)

filtered["mtb_oszczednosc_pln"] = (filtered["cr_price_pln"] - filtered["mtb_price_pln"]).round(2)
filtered["mtb_oszczednosc_pct"] = (
    filtered["mtb_oszczednosc_pln"] / filtered["cr_price_pln"] * 100
).round(1)

filtered["bi_oszczednosc_pln"] = (filtered["cr_price_pln"] - filtered["bi_price_pln"]).round(2)
filtered["bi_oszczednosc_pct"] = (
    filtered["bi_oszczednosc_pln"] / filtered["cr_price_pln"] * 100
).round(1)

if search_query:
    q = search_query.strip().lower()
    filtered = filtered[filtered["canonical_name"].str.lower().str.contains(q, na=False)]

if selected_shops:
    shop_mask = pd.Series(False, index=filtered.index)
    if "centrumrowerowe.pl" in selected_shops:
        shop_mask |= pd.Series(True, index=filtered.index)
    if "bike-discount.de" in selected_shops:
        shop_mask |= filtered["bd_price_eur"].notna()
    if "mtbiker.pl" in selected_shops:
        shop_mask |= filtered["mtb_price_pln"].notna()
    if "bikeinn.com" in selected_shops:
        shop_mask |= filtered["bi_price_pln"].notna()
    filtered = filtered[shop_mask]

if selected_brands:
    filtered = filtered[filtered["brand"].isin(selected_brands)]

# Posortuj: zmatchowane (mające jakikolwiek match) najpierw, potem niezmatchowane — wg ceny CR malejąco
has_any_match = filtered["bd_price_eur"].notna() | filtered["mtb_price_pln"].notna() | filtered["bi_price_pln"].notna()
matched_rows = filtered[has_any_match].sort_values("cr_price_pln", ascending=False)
unmatched_rows = filtered[~has_any_match].sort_values("cr_price_pln", ascending=False)
filtered = pd.concat([matched_rows, unmatched_rows])


# ── Tabela ────────────────────────────────────────────────────────────────────
if len(filtered) == 0:
    st.info("Brak produktów spełniających wybrane kryteria.")
else:
    rows_html = []
    for _, row in filtered.iterrows():
        has_bd = pd.notna(row.get("bd_price_eur"))
        has_mtb = pd.notna(row.get("mtb_price_pln"))
        has_bi = pd.notna(row.get("bi_price_pln"))
        cr_link = f'<a href="{row["cr_url"]}" rel="noreferrer noopener" target="_blank">CR 🔗</a>' if row.get("cr_url") else "—"
        al_link = f'<a href="{allegro_url(row["canonical_name"])}" rel="noreferrer noopener" target="_blank">AL 🔗</a>'

        bd_eur = f"{row['bd_price_eur']:.2f} €" if has_bd else "—"
        bd_pln = f"{row['bd_price_pln']:.2f} zł" if has_bd else "—"
        bd_link = f'<a href="{row["bd_url"]}" rel="noreferrer noopener" target="_blank">BD 🔗</a>' if has_bd else '<span style="color:#aaa">—</span>'

        mtb_pln = f"{row['mtb_price_pln']:.2f} zł" if has_mtb else "—"
        mtb_link = f'<a href="{row["mtb_url"]}" rel="noreferrer noopener" target="_blank">MTB 🔗</a>' if has_mtb else '<span style="color:#aaa">—</span>'

        bi_pln = f"{row['bi_price_pln']:.2f} zł" if has_bi else "—"
        bi_link = f'<a href="{row["bi_url"]}" rel="noreferrer noopener" target="_blank">BI 🔗</a>' if has_bi else '<span style="color:#aaa">—</span>'

        rows_html.append(f"""
        <tr>
            <td>{CATEGORY_LABELS.get(row['category'], row['category'])}</td>
            <td>{row['canonical_name']}</td>
            <td style="text-align:right">{row['cr_price_pln']:.2f} zł</td>
            <td class="sep" style="text-align:right">{bd_eur}</td>
            <td style="text-align:right">{bd_pln}</td>
            <td class="sep" style="text-align:right">{mtb_pln}</td>
            <td class="sep" style="text-align:right">{bi_pln}</td>
            <td class="sep" style="text-align:center">{cr_link}</td>
            <td style="text-align:center">{bd_link}</td>
            <td style="text-align:center">{mtb_link}</td>
            <td style="text-align:center">{bi_link}</td>
            <td style="text-align:center">{al_link}</td>
        </tr>""")

    table_html = f"""
    <div style="padding: 0 1.5rem;">
    <style>
        .pt {{ width:100%; border-collapse:collapse; font-size:13px; }}
        .pt th {{ background:rgba(128,128,128,0.15); padding:8px 10px; text-align:left; border-bottom:2px solid rgba(128,128,128,0.3); white-space:nowrap; }}
        .pt td {{ padding:6px 10px; border-bottom:1px solid rgba(128,128,128,0.15); vertical-align:middle; }}
        .pt tr:hover td {{ background:rgba(128,128,128,0.08); }}
        .pt a {{ color:#0068c9; text-decoration:none; }}
        .pt a:hover {{ text-decoration:underline; }}
        .pt th.sep {{ border-left: 2px solid rgba(128,128,128,0.3); }}
        .pt td.sep {{ border-left: 1px solid rgba(128,128,128,0.15); }}
    </style>
    <table class="pt">
        <thead><tr>
            <th>Kategoria</th><th>Produkt (CR)</th>
            <th>CR (PLN)</th>
            <th class="sep">BD (EUR)</th><th>BD (~PLN @ {eur_rate:.2f})</th>
            <th class="sep">MTB (PLN)</th>
            <th class="sep">BI (PLN)</th>
            <th class="sep">Link CR</th><th>Link BD</th><th>Link MTB</th><th>Link BI</th><th>Link AL</th>
        </tr></thead>
        <tbody>{''.join(rows_html)}</tbody>
    </table>
    <p style="font-size:12px;color:#888;margin-top:8px">
        💡 Kurs EUR/PLN: {eur_rate:.2f} · Ceny BD w PLN są orientacyjne — uwzględnij koszty dostawy i ewentualne cło. · MTB = mtbiker.pl · BI = bikeinn.com (ceny PLN). · made by <a href="https://buycoffee.to/icearas" rel="noreferrer noopener" target="_blank" style="color:#888">icearas</a>
    </p>
    </div>
    """
    st.markdown(table_html, unsafe_allow_html=True)
