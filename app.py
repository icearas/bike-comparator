import streamlit as st
import pandas as pd
from pathlib import Path
import urllib.request
import urllib.parse
import json

CR_ALL_PATH = Path(__file__).parent / "data" / "cr_all.csv"
MATCHED_PATH = Path(__file__).parent / "data" / "matched_products.csv"
MTB_MATCHED_PATH = Path(__file__).parent / "data" / "mtb_matched.csv"
BI_MATCHED_PATH  = Path(__file__).parent / "data" / "bi_matched.csv"

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


@st.cache_data
def load_data() -> pd.DataFrame:
    cr = pd.read_csv(CR_ALL_PATH)
    cr = cr.rename(columns={"name": "cr_name", "price": "cr_price_pln", "url": "cr_url"})

    matched = pd.read_csv(MATCHED_PATH)
    matched["matched_at"] = pd.to_datetime(matched["matched_at"], utc=True, errors="coerce")
    matched = matched[["cr_url", "bd_name", "bd_price_eur", "bd_url", "matched_at"]]

    df = cr.merge(matched, on="cr_url", how="left")
    if MTB_MATCHED_PATH.exists():
        mtb = pd.read_csv(MTB_MATCHED_PATH)
        mtb = mtb[["cr_url", "mtb_name", "mtb_price_pln", "mtb_url"]]
        df = df.merge(mtb, on="cr_url", how="left")
    else:
        df["mtb_name"] = None
        df["mtb_price_pln"] = float("nan")
        df["mtb_url"] = None
    if BI_MATCHED_PATH.exists():
        bi = pd.read_csv(BI_MATCHED_PATH)
        bi = bi[["cr_url", "bi_name", "bi_price_pln", "bi_url"]]
        df = df.merge(bi, on="cr_url", how="left")
    else:
        df["bi_name"] = None
        df["bi_price_pln"] = float("nan")
        df["bi_url"] = None
    return df


df = load_data()
last_updated = df["matched_at"].max()
if pd.notna(last_updated):
    st.caption(f"Ostatnia aktualizacja danych: {last_updated.strftime('%d.%m.%Y')}")

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
    mask = (
        filtered["cr_name"].str.lower().str.contains(q, na=False)
        | filtered["bd_name"].str.lower().str.contains(q, na=False)
        | filtered["mtb_name"].str.lower().str.contains(q, na=False)
        | filtered["bi_name"].str.lower().str.contains(q, na=False)
    )
    filtered = filtered[mask]

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
    brand_keywords = {
        "Shimano":  ["shimano", "deore", "slx", "xtr", "saint"],
        "SRAM":     ["sram", "gx eagle", "x01 eagle", "xx1 eagle", "guide", "maven", "db8"],
        "RockShox": ["rock shox", "rockshox", "pike", "lyrik", "zeb", "yari", "psylo"],
        "FOX":      ["fox"],
    }
    kws = [kw for b in selected_brands for kw in brand_keywords[b]]
    filtered = filtered[filtered["cr_name"].str.lower().apply(
        lambda n: any(k in n for k in kws)
    )]

# Posortuj: zmatchowane najpierw (wg oszczędności malejąco), potem niezmatchowane
matched_rows = filtered[filtered["bd_price_eur"].notna()].sort_values("oszczednosc_pct", ascending=False)
unmatched_rows = filtered[filtered["bd_price_eur"].isna()].sort_values("cr_price_pln", ascending=False)
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
        al_link = f'<a href="{allegro_url(row["cr_name"])}" rel="noreferrer noopener" target="_blank">AL 🔗</a>'

        if has_bd:
            color_bd = "#1a7f37" if row["oszczednosc_pln"] > 0 else "#c0392b"
            sign_bd = "+" if row["oszczednosc_pln"] > 0 else ""
            bd_eur = f"{row['bd_price_eur']:.2f} €"
            bd_pln = f"{row['bd_price_pln']:.2f} zł"
            sav_bd_pln = f'<td style="text-align:right;color:{color_bd};font-weight:bold">{sign_bd}{row["oszczednosc_pln"]:.2f} zł</td>'
            sav_bd_pct = f'<td style="text-align:right;color:{color_bd};font-weight:bold">{sign_bd}{row["oszczednosc_pct"]:.1f}%</td>'
            bd_link = f'<a href="{row["bd_url"]}" rel="noreferrer noopener" target="_blank">BD 🔗</a>'
        else:
            bd_eur = "—"
            bd_pln = "—"
            sav_bd_pln = '<td style="text-align:right;color:#aaa">—</td>'
            sav_bd_pct = '<td style="text-align:right;color:#aaa">—</td>'
            bd_link = '<span style="color:#aaa">—</span>'

        if has_mtb:
            color_mtb = "#1a7f37" if row["mtb_oszczednosc_pln"] > 0 else "#c0392b"
            sign_mtb = "+" if row["mtb_oszczednosc_pln"] > 0 else ""
            mtb_pln = f"{row['mtb_price_pln']:.2f} zł"
            sav_mtb_pln = f'<td style="text-align:right;color:{color_mtb};font-weight:bold">{sign_mtb}{row["mtb_oszczednosc_pln"]:.2f} zł</td>'
            sav_mtb_pct = f'<td style="text-align:right;color:{color_mtb};font-weight:bold">{sign_mtb}{row["mtb_oszczednosc_pct"]:.1f}%</td>'
            mtb_link = f'<a href="{row["mtb_url"]}" rel="noreferrer noopener" target="_blank">MTB 🔗</a>'
        else:
            mtb_pln = "—"
            sav_mtb_pln = '<td style="text-align:right;color:#aaa">—</td>'
            sav_mtb_pct = '<td style="text-align:right;color:#aaa">—</td>'
            mtb_link = '<span style="color:#aaa">—</span>'

        if has_bi:
            color_bi = "#1a7f37" if row["bi_oszczednosc_pln"] > 0 else "#c0392b"
            sign_bi = "+" if row["bi_oszczednosc_pln"] > 0 else ""
            bi_pln = f"{row['bi_price_pln']:.2f} zł"
            sav_bi_pln = f'<td style="text-align:right;color:{color_bi};font-weight:bold">{sign_bi}{row["bi_oszczednosc_pln"]:.2f} zł</td>'
            sav_bi_pct = f'<td style="text-align:right;color:{color_bi};font-weight:bold">{sign_bi}{row["bi_oszczednosc_pct"]:.1f}%</td>'
            bi_link = f'<a href="{row["bi_url"]}" rel="noreferrer noopener" target="_blank">BI 🔗</a>'
        else:
            bi_pln = "—"
            sav_bi_pln = '<td style="text-align:right;color:#aaa">—</td>'
            sav_bi_pct = '<td style="text-align:right;color:#aaa">—</td>'
            bi_link = '<span style="color:#aaa">—</span>'

        rows_html.append(f"""
        <tr>
            <td>{CATEGORY_LABELS.get(row['category'], row['category'])}</td>
            <td>{row['cr_name']}</td>
            <td style="text-align:right">{row['cr_price_pln']:.2f} zł</td>
            <td style="text-align:right">{bd_eur}</td>
            <td style="text-align:right">{bd_pln}</td>
            {sav_bd_pln}
            {sav_bd_pct}
            <td style="text-align:right">{mtb_pln}</td>
            {sav_mtb_pln}
            {sav_mtb_pct}
            <td class="sep" style="text-align:right">{bi_pln}</td>
            {sav_bi_pln}
            {sav_bi_pct}
            <td style="text-align:center">{cr_link}</td>
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
            <th class="sep">BD (EUR)</th><th>BD (~PLN @ {eur_rate:.2f})</th><th>Oszcz. BD (PLN)</th><th>Oszcz. BD (%)</th>
            <th class="sep">MTB (PLN)</th><th>Oszcz. MTB (PLN)</th><th>Oszcz. MTB (%)</th>
            <th class="sep">BI (PLN)</th><th>Oszcz. BI (PLN)</th><th>Oszcz. BI (%)</th>
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
