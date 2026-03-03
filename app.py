import streamlit as st
import pandas as pd
from pathlib import Path

DATA_PATH = Path(__file__).parent / "data" / "matched_products.csv"

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
st.caption("centrumrowerowe.pl  vs  bike-discount.de")


@st.cache_data
def load_data() -> pd.DataFrame:
    df = pd.read_csv(DATA_PATH)
    df["matched_at"] = pd.to_datetime(df["matched_at"], utc=True, errors="coerce")
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
    category_display = ["Wszystkie"] + [
        CATEGORY_LABELS.get(c, c) for c in all_categories
    ]
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

if search_query:
    q = search_query.strip().lower()
    mask = (
        filtered["cr_name"].str.lower().str.contains(q, na=False)
        | filtered["bd_name"].str.lower().str.contains(q, na=False)
    )
    filtered = filtered[mask]

if only_cheaper:
    filtered = filtered[filtered["oszczednosc_pln"] > 0]

if min_savings_pct > 0:
    filtered = filtered[filtered["oszczednosc_pct"] >= min_savings_pct]
filtered = filtered.sort_values("oszczednosc_pct", ascending=False)

# ── Metryki ───────────────────────────────────────────────────────────────────
c1, c2, c3, c4 = st.columns(4)

taniej_count = (filtered["oszczednosc_pln"] > 0).sum()
avg_savings = filtered.loc[filtered["oszczednosc_pln"] > 0, "oszczednosc_pct"].mean()
max_savings = filtered["oszczednosc_pct"].max()

c1.metric("Dopasowanych produktów", len(filtered))
c2.metric(
    "Taniej w BD",
    f"{taniej_count} / {len(filtered)}",
)
c3.metric(
    "Śr. oszczędność",
    f"{avg_savings:.1f}%" if pd.notna(avg_savings) else "—",
)
c4.metric(
    "Max oszczędność",
    f"{max_savings:.1f}%" if pd.notna(max_savings) and len(filtered) > 0 else "—",
)

st.divider()

# ── Tabela ────────────────────────────────────────────────────────────────────
if len(filtered) == 0:
    st.info("Brak produktów spełniających wybrane kryteria.")
else:
    rows_html = []
    for _, row in filtered.iterrows():
        color = "#1a7f37" if row["oszczednosc_pln"] > 0 else "#c0392b"
        sign = "+" if row["oszczednosc_pln"] > 0 else ""
        rows_html.append(f"""
        <tr>
            <td>{CATEGORY_LABELS.get(row['category'], row['category'])}</td>
            <td>{row['cr_name']}</td>
            <td style="text-align:right">{row['cr_price_pln']:.2f} zł</td>
            <td style="text-align:right">{row['bd_price_eur']:.2f} €</td>
            <td style="text-align:right">{row['bd_price_pln']:.2f} zł</td>
            <td style="text-align:right;color:{color};font-weight:bold">{sign}{row['oszczednosc_pln']:.2f} zł</td>
            <td style="text-align:right;color:{color};font-weight:bold">{sign}{row['oszczednosc_pct']:.1f}%</td>
            <td style="text-align:center"><a href="{row['cr_url']}" rel="noreferrer noopener" target="_blank">CR 🔗</a></td>
            <td style="text-align:center"><a href="{row['bd_url']}" rel="noreferrer noopener" target="_blank">BD 🔗</a></td>
        </tr>""")

    table_html = f"""
    <style>
        .pt {{ width:100%; border-collapse:collapse; font-size:13px; }}
        .pt th {{ background:#f0f2f6; padding:8px 10px; text-align:left; border-bottom:2px solid #d0d3da; white-space:nowrap; }}
        .pt td {{ padding:6px 10px; border-bottom:1px solid #eaecf0; vertical-align:middle; }}
        .pt tr:hover td {{ background:#f7f8fa; }}
        .pt a {{ color:#0068c9; text-decoration:none; }}
        .pt a:hover {{ text-decoration:underline; }}
    </style>
    <table class="pt">
        <thead><tr>
            <th>Kategoria</th><th>Produkt (CR)</th>
            <th>CR (PLN)</th><th>BD (EUR)</th><th>BD (~PLN @ {eur_rate:.2f})</th>
            <th>Oszczędność (PLN)</th><th>Oszczędność (%)</th>
            <th>Link CR</th><th>Link BD</th>
        </tr></thead>
        <tbody>{''.join(rows_html)}</tbody>
    </table>
    <p style="font-size:12px;color:#888;margin-top:8px">
        💡 Kurs EUR/PLN: {eur_rate:.2f} · Ceny BD w PLN są orientacyjne — uwzględnij koszty dostawy i ewentualne cło.
    </p>
    """
    st.markdown(table_html, unsafe_allow_html=True)
