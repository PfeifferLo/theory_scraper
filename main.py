"""
main.py
Streamlit-Dashboard: zeigt gescrapte Paper und die darin erkannten
Theorien rund um Circular Economy & Sustainability Orientation.
"""

import json
import os
from collections import Counter

import pandas as pd
import streamlit as st

from theory_rules import analyze_papers, count_all_theories

DATA_DIR = "data"
COMBINED_FILE = os.path.join(DATA_DIR, "all_papers.json")

st.set_page_config(
    page_title="Theorie-Landscape: Circular Economy & Sustainability",
    layout="wide"
)


# -----------------------------------------------------
# Daten laden (gecached, damit nicht bei jeder Interaktion neu geladen wird)
# -----------------------------------------------------
@st.cache_data
def load_papers():
    if not os.path.exists(COMBINED_FILE):
        return []
    with open(COMBINED_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


@st.cache_data
def get_enriched_papers(papers):
    return analyze_papers(papers)


# -----------------------------------------------------
# Daten laden & analysieren
# -----------------------------------------------------
papers = load_papers()

if not papers:
    st.error(
        f"Keine Daten gefunden unter `{COMBINED_FILE}`. "
        "Bitte zuerst `scraper.py` ausführen, um Paper herunterzuladen."
    )
    st.stop()

enriched = get_enriched_papers(papers)
df = pd.DataFrame(enriched)


# -----------------------------------------------------
# Sidebar: Filter
# -----------------------------------------------------
st.sidebar.header("Filter")

journals = sorted(df["journal_code"].dropna().unique())
selected_journals = st.sidebar.multiselect(
    "Journal", journals, default=journals
)

years = df["year"].dropna().astype(int)
if not years.empty:
    year_min, year_max = int(years.min()), int(years.max())
    selected_years = st.sidebar.slider(
        "Erscheinungsjahr", year_min, year_max, (year_min, year_max)
    )
else:
    selected_years = (0, 9999)

only_circular = st.sidebar.checkbox("Nur Circular Economy Paper", value=False)
only_sustainability = st.sidebar.checkbox("Nur Sustainability Orientation Paper", value=False)
only_with_theory = st.sidebar.checkbox("Nur Paper mit erkannter Theorie", value=False)


# -----------------------------------------------------
# Filter anwenden
# -----------------------------------------------------
filtered = df[
    df["journal_code"].isin(selected_journals)
    & df["year"].fillna(0).astype(int).between(selected_years[0], selected_years[1])
]

if only_circular:
    filtered = filtered[filtered["circular_economy"] == True]
if only_sustainability:
    filtered = filtered[filtered["sustainability_orientation"] == True]
if only_with_theory:
    filtered = filtered[filtered["theory_count"] > 0]


# -----------------------------------------------------
# Kopfbereich: Kennzahlen
# -----------------------------------------------------
st.title("Theorie-Landscape: Circular Economy & Sustainability Orientation")
st.caption("Automatisch aus Abstracts extrahierte Theorien mittels regelbasierter Erkennung")

col1, col2, col3, col4 = st.columns(4)
col1.metric("Paper gesamt", len(filtered))
col2.metric("Mit erkannter Theorie", int((filtered["theory_count"] > 0).sum()))
col3.metric("Circular Economy", int(filtered["circular_economy"].sum()))
col4.metric("Sustainability Orientation", int(filtered["sustainability_orientation"].sum()))

st.divider()


# -----------------------------------------------------
# Theorien-Häufigkeit
# -----------------------------------------------------
st.subheader("Häufigste Theorien")

theory_counter = count_all_theories(filtered.to_dict("records"))

if theory_counter:
    theory_df = (
        pd.DataFrame(theory_counter.items(), columns=["Theorie", "Anzahl"])
        .sort_values("Anzahl", ascending=False)
        .reset_index(drop=True)
    )

    top_n = st.slider("Anzahl angezeigter Theorien", 5, min(30, len(theory_df)), min(15, len(theory_df)))

    st.bar_chart(theory_df.head(top_n).set_index("Theorie"))
    st.dataframe(theory_df, use_container_width=True)
else:
    st.info("Für die aktuelle Filterauswahl wurden keine Theorien erkannt.")

st.divider()


# -----------------------------------------------------
# Verteilung nach Journal
# -----------------------------------------------------
st.subheader("Paper pro Journal")
journal_counts = filtered["journal_name"].value_counts()
st.bar_chart(journal_counts)

st.divider()


# -----------------------------------------------------
# Verteilung nach Jahr
# -----------------------------------------------------
st.subheader("Paper pro Jahr")
year_counts = filtered["year"].dropna().astype(int).value_counts().sort_index()
st.line_chart(year_counts)

st.divider()


# -----------------------------------------------------
# Paper-Tabelle mit Detailansicht
# -----------------------------------------------------
st.subheader("Paper im Detail")

display_df = filtered[[
    "title", "journal_code", "year", "citations",
    "theory_count", "circular_economy", "sustainability_orientation"
]].sort_values("theory_count", ascending=False)

st.dataframe(display_df, use_container_width=True, height=400)

st.markdown("**Einzelnes Paper auswählen, um Abstract & erkannte Theorien zu sehen:**")
paper_titles = filtered["title"].tolist()

if paper_titles:
    selected_title = st.selectbox("Paper", paper_titles)
    selected_paper = filtered[filtered["title"] == selected_title].iloc[0]

    st.markdown(f"### {selected_paper['title']}")
    st.write(f"**Journal:** {selected_paper['journal_name']} ({selected_paper['year']})")
    st.write(f"**DOI:** {selected_paper['doi']}")
    st.write(f"**Zitationen:** {selected_paper['citations']}")

    if selected_paper["all_theories"]:
        st.write("**Erkannte Theorien:** " + ", ".join(selected_paper["all_theories"]))
    else:
        st.write("**Erkannte Theorien:** keine")

    st.write("**Abstract:**")
    st.write(selected_paper["abstract"] if selected_paper["abstract"] else "_Kein Abstract verfügbar._")
