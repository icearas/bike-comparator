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

st.title("🚵 Porównywarka cen części rowerowych")
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

# ── Obliczenia ────────────────────────────────────────────────────────────────
filtered = df.copy()

if selected_label != "Wszystkie":
    filtered = filtered[filtered["category"] == category_map[selected_label]]

filtered["bd_price_pln"] = (filtered["bd_price_eur"] * eur_rate).round(2)
filtered["oszczednosc_pln"] = (filtered["cr_price_pln"] - filtered["bd_price_pln"]).round(2)
filtered["oszczednosc_pct"] = (
    filtered["oszczednosc_pln"] / filtered["cr_price_pln"] * 100
).round(1)

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
    display = filtered[[
        "category",
        "cr_name",
        "cr_price_pln",
        "bd_price_eur",
        "bd_price_pln",
        "oszczednosc_pln",
        "oszczednosc_pct",
        "cr_url",
        "bd_url",
    ]].copy()

    display["category"] = display["category"].map(
        lambda x: CATEGORY_LABELS.get(x, x)
    )

    st.dataframe(
        display,
        use_container_width=True,
        height=600,
        column_config={
            "category": st.column_config.TextColumn("Kategoria", width="small"),
            "cr_name": st.column_config.TextColumn("Produkt (CR)", width="large"),
            "cr_price_pln": st.column_config.NumberColumn(
                "CR (PLN)", format="%.2f zł", width="small"
            ),
            "bd_price_eur": st.column_config.NumberColumn(
                "BD (EUR)", format="%.2f €", width="small"
            ),
            "bd_price_pln": st.column_config.NumberColumn(
                f"BD (~PLN @ {eur_rate:.2f})", format="%.2f zł", width="small"
            ),
            "oszczednosc_pln": st.column_config.NumberColumn(
                "Oszczędność (PLN)", format="%.2f zł", width="small"
            ),
            "oszczednosc_pct": st.column_config.NumberColumn(
                "Oszczędność (%)", format="%.1f%%", width="small"
            ),
            "cr_url": st.column_config.LinkColumn(
                "Link CR", display_text="centrumrowerowe.pl", width="small"
            ),
            "bd_url": st.column_config.LinkColumn(
                "Link BD", display_text="bike-discount.de", width="small"
            ),
        },
        hide_index=True,
    )

    st.caption(
        f"💡 Kurs EUR/PLN: {eur_rate:.2f} · "
        "Ceny BD w PLN są orientacyjne — uwzględnij koszty dostawy i ewentualne cło."
    )
