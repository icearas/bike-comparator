import streamlit as st
import pandas as pd
from pathlib import Path

CR_ALL_PATH = Path(__file__).parent / "data" / "cr_all.csv"
MATCHED_PATH = Path(__file__).parent / "data" / "matched_products.csv"
RW_MATCHED_PATH = Path(__file__).parent / "data" / "rw_matched.csv"

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
st.caption("centrumrowerowe.pl  vs  bike-discount.de  vs  rowerowy.com")


@st.cache_data
def load_data() -> pd.DataFrame:
    cr = pd.read_csv(CR_ALL_PATH)
    cr = cr.rename(columns={"name": "cr_name", "price": "cr_price_pln", "url": "cr_url"})

    matched = pd.read_csv(MATCHED_PATH)
    matched["matched_at"] = pd.to_datetime(matched["matched_at"], utc=True, errors="coerce")
    matched = matched[["cr_url", "bd_name", "bd_price_eur", "bd_url", "matched_at"]]

    rw = pd.read_csv(RW_MATCHED_PATH)
    rw = rw[["cr_url", "rw_name", "rw_price_pln", "rw_url"]]

    df = cr.merge(matched, on="cr_url", how="left")
    df = df.merge(rw, on="cr_url", how="left")
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

    eur_rate = st.number_input(
        "Kurs EUR → PLN",
        min_value=3.5,
        max_value=6.0,
        value=4.25,
        step=0.05,
        format="%.2f",
        help="Użyj aktualnego kursu ze swojego banku lub Revoluta.",
    )

    st.divider()
    st.header("🔍 Filtry")

    all_categories = sorted(df["category"].unique().tolist())
    category_display = ["Wszystkie"] + [CATEGORY_LABELS.get(c, c) for c in all_categories]
    category_map = {CATEGORY_LABELS.get(c, c): c for c in all_categories}

    selected_label = st.selectbox("Kategoria", category_display)

    min_savings_pct = st.slider(
        "Min. oszczędność (%)",
        min_value=0,
        max_value=60,
        value=0,
        step=5,
        help="Pokaż tylko produkty tańsze w BD o co najmniej X%.",
    )

    only_cheaper = st.checkbox(
        "Tylko tańsze w BD",
        value=False,
        help="Ukryj produkty droższe lub równe w bike-discount.",
    )

    only_matched = st.checkbox(
        "Tylko z matchem w BD",
        value=False,
        help="Ukryj produkty bez odpowiednika w bike-discount.",
    )

    only_cheaper_rw = st.checkbox(
        "Tylko tańsze w RW",
        value=False,
        help="Pokaż tylko produkty tańsze w rowerowy.com niż w CR.",
    )

    only_matched_rw = st.checkbox(
        "Tylko z matchem w RW",
        value=False,
        help="Ukryj produkty bez odpowiednika w rowerowy.com.",
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

filtered["rw_oszczednosc_pln"] = (filtered["cr_price_pln"] - filtered["rw_price_pln"]).round(2)
filtered["rw_oszczednosc_pct"] = (
    filtered["rw_oszczednosc_pln"] / filtered["cr_price_pln"] * 100
).round(1)

if search_query:
    q = search_query.strip().lower()
    mask = (
        filtered["cr_name"].str.lower().str.contains(q, na=False)
        | filtered["bd_name"].str.lower().str.contains(q, na=False)
        | filtered["rw_name"].str.lower().str.contains(q, na=False)
    )
    filtered = filtered[mask]

if only_matched:
    filtered = filtered[filtered["bd_price_eur"].notna()]

if only_matched_rw:
    filtered = filtered[filtered["rw_price_pln"].notna()]

if only_cheaper:
    filtered = filtered[filtered["oszczednosc_pln"] > 0]

if only_cheaper_rw:
    filtered = filtered[filtered["rw_oszczednosc_pln"] > 0]

if min_savings_pct > 0:
    filtered = filtered[filtered["oszczednosc_pct"] >= min_savings_pct]

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
        has_rw = pd.notna(row.get("rw_price_pln"))
        cr_link = f'<a href="{row["cr_url"]}" rel="noreferrer noopener" target="_blank">CR 🔗</a>' if row.get("cr_url") else "—"

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

        if has_rw:
            color_rw = "#1a7f37" if row["rw_oszczednosc_pln"] > 0 else "#c0392b"
            sign_rw = "+" if row["rw_oszczednosc_pln"] > 0 else ""
            rw_pln = f"{row['rw_price_pln']:.2f} zł"
            sav_rw_pln = f'<td style="text-align:right;color:{color_rw};font-weight:bold">{sign_rw}{row["rw_oszczednosc_pln"]:.2f} zł</td>'
            sav_rw_pct = f'<td style="text-align:right;color:{color_rw};font-weight:bold">{sign_rw}{row["rw_oszczednosc_pct"]:.1f}%</td>'
            rw_link = f'<a href="{row["rw_url"]}" rel="noreferrer noopener" target="_blank">RW 🔗</a>'
        else:
            rw_pln = "—"
            sav_rw_pln = '<td style="text-align:right;color:#aaa">—</td>'
            sav_rw_pct = '<td style="text-align:right;color:#aaa">—</td>'
            rw_link = '<span style="color:#aaa">—</span>'

        rows_html.append(f"""
        <tr>
            <td>{CATEGORY_LABELS.get(row['category'], row['category'])}</td>
            <td>{row['cr_name']}</td>
            <td style="text-align:right">{row['cr_price_pln']:.2f} zł</td>
            <td style="text-align:right">{bd_eur}</td>
            <td style="text-align:right">{bd_pln}</td>
            {sav_bd_pln}
            {sav_bd_pct}
            <td style="text-align:right">{rw_pln}</td>
            {sav_rw_pln}
            {sav_rw_pct}
            <td style="text-align:center">{cr_link}</td>
            <td style="text-align:center">{bd_link}</td>
            <td style="text-align:center">{rw_link}</td>
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
            <th class="sep">RW (PLN)</th><th>Oszcz. RW (PLN)</th><th>Oszcz. RW (%)</th>
            <th class="sep">Link CR</th><th>Link BD</th><th>Link RW</th>
        </tr></thead>
        <tbody>{''.join(rows_html)}</tbody>
    </table>
    <p style="font-size:12px;color:#888;margin-top:8px">
        💡 Kurs EUR/PLN: {eur_rate:.2f} · Ceny BD w PLN są orientacyjne — uwzględnij koszty dostawy i ewentualne cło. · RW = rowerowy.com (ceny PLN).
    </p>
    </div>
    """
    st.markdown(table_html, unsafe_allow_html=True)
