"""
main.py
Streamlit-Dashboard: Auswahl & Download von Papern ausgewählter Journals
sowie Analyse der darin erkannten Theorien rund um Circular Economy &
Sustainability Orientation.
"""

import json
import os

import altair as alt
import pandas as pd
import streamlit as st

from scraper import JOURNALS, scrape_selected
from theory_rules import analyze_papers, count_all_theories

DATA_DIR = "data"
COMBINED_FILE = os.path.join(DATA_DIR, "all_papers.json")

st.set_page_config(
    page_title="Theorie-Landscape: Circular Economy & Sustainability",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded",
)


# =======================================================
# Styling
# =======================================================
def inject_css():
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

        html, body, [class*="css"]  {
            font-family: 'Inter', sans-serif;
        }

        :root {
            --brand-primary: #2E6F5E;
            --brand-primary-light: #E7F2EE;
            --brand-accent: #C9A227;
            --brand-ink: #1F2A24;
            --brand-muted: #6B7A72;
        }

        .block-container {
            padding-top: 2rem;
            padding-bottom: 3rem;
        }

        /* Header */
        .app-title {
            font-size: 2.1rem;
            font-weight: 800;
            color: var(--brand-ink);
            margin-bottom: 0.15rem;
            letter-spacing: -0.02em;
        }
        .app-subtitle {
            font-size: 1rem;
            color: var(--brand-muted);
            margin-bottom: 1.5rem;
        }

        /* Metric cards */
        .metric-card {
            background: white;
            border: 1px solid #E7EAE8;
            border-radius: 14px;
            padding: 1.1rem 1.3rem;
            box-shadow: 0 1px 3px rgba(0,0,0,0.04);
            height: 100%;
        }
        .metric-label {
            font-size: 0.8rem;
            font-weight: 600;
            color: var(--brand-muted);
            text-transform: uppercase;
            letter-spacing: 0.04em;
            margin-bottom: 0.3rem;
        }
        .metric-value {
            font-size: 1.9rem;
            font-weight: 800;
            color: var(--brand-ink);
        }
        .metric-sub {
            font-size: 0.8rem;
            color: var(--brand-accent);
            font-weight: 600;
            margin-top: 0.2rem;
        }

        /* Section headers */
        .section-header {
            font-size: 1.25rem;
            font-weight: 700;
            color: var(--brand-ink);
            margin-top: 0.5rem;
            margin-bottom: 0.2rem;
        }
        .section-caption {
            color: var(--brand-muted);
            font-size: 0.88rem;
            margin-bottom: 0.8rem;
        }

        /* Journal selection cards */
        .journal-card {
            background: white;
            border: 1px solid #E7EAE8;
            border-radius: 12px;
            padding: 1rem 1.1rem;
            margin-bottom: 0.6rem;
        }
        .journal-card-title {
            font-weight: 700;
            color: var(--brand-ink);
            font-size: 0.95rem;
        }
        .journal-card-code {
            display: inline-block;
            background: var(--brand-primary-light);
            color: var(--brand-primary);
            font-weight: 700;
            font-size: 0.72rem;
            padding: 0.15rem 0.5rem;
            border-radius: 6px;
            margin-right: 0.5rem;
        }

        div.stButton > button {
            border-radius: 10px;
            font-weight: 600;
            border: 1px solid var(--brand-primary);
        }
        div.stButton > button[kind="primary"] {
            background-color: var(--brand-primary);
            border: 1px solid var(--brand-primary);
        }

        .badge-ce {
            background: #E7F2EE; color: #2E6F5E;
            padding: 0.1rem 0.5rem; border-radius: 6px;
            font-size: 0.75rem; font-weight: 700; margin-right: 0.3rem;
        }
        .badge-so {
            background: #FBF3DC; color: #93731A;
            padding: 0.1rem 0.5rem; border-radius: 6px;
            font-size: 0.75rem; font-weight: 700;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def metric_card(label, value, sub=None):
    sub_html = f'<div class="metric-sub">{sub}</div>' if sub else ""
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-label">{label}</div>
            <div class="metric-value">{value}</div>
            {sub_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


# =======================================================
# Daten laden
# =======================================================
@st.cache_data
def load_papers():
    if not os.path.exists(COMBINED_FILE):
        return []
    with open(COMBINED_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


@st.cache_data
def get_enriched_papers(papers):
    return analyze_papers(papers)


def available_journal_codes():
    """Welche Journals stecken bereits in den gespeicherten Daten?"""
    papers = load_papers()
    return sorted({p.get("journal_code") for p in papers if p.get("journal_code")})


# =======================================================
# Bildschirm 1: Journal-Auswahl & Ladevorgang
# =======================================================
def show_scraper_screen():
    st.markdown('<div class="app-title">📚 Paper-Daten laden</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="app-subtitle">Wähle die Journals aus, für die Paper von OpenAlex '
        "heruntergeladen werden sollen. Bereits geladene Journals werden dabei aktualisiert, "
        "alle anderen bleiben unverändert erhalten.</div>",
        unsafe_allow_html=True,
    )

    already_loaded = available_journal_codes()

    selected = []
    cols = st.columns(2)
    for i, (code, info) in enumerate(JOURNALS.items()):
        with cols[i % 2]:
            loaded_tag = " · bereits geladen" if code in already_loaded else " · noch nicht geladen"
            st.markdown(
                f"""
                <div class="journal-card">
                    <span class="journal-card-code">{code}</span>
                    <span class="journal-card-title">{info['name']}</span>
                    <div style="color:#6B7A72; font-size:0.78rem; margin-top:0.3rem;">
                        ISSN {info['issn']}{loaded_tag}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            checked = st.checkbox(
                "Auswählen", value=(code in already_loaded), key=f"chk_{code}"
            )
            if checked:
                selected.append(code)

    st.write("")
    col_a, col_b, col_c = st.columns([1, 1, 2])
    with col_a:
        start = st.button("⬇️ Ausgewählte Journals laden", type="primary", disabled=(len(selected) == 0))
    with col_b:
        if already_loaded:
            if st.button("↩️ Zum Dashboard"):
                st.session_state.show_scraper = False
                st.rerun()

    if not EMAIL_HINT_SHOWN[0]:
        st.caption(
            "💡 Tipp: Setze die Umgebungsvariable `SCRAPER_EMAIL` vor dem Start, "
            "um von OpenAlex' schnellerem 'polite pool' zu profitieren."
        )
        EMAIL_HINT_SHOWN[0] = True

    if start and selected:
        status_area = st.status("Lade Paper von OpenAlex...", expanded=True)
        progress_bar = st.progress(0)
        counters = {code: 0 for code in selected}

        def status_callback(journal_code, n):
            counters[journal_code] = n
            journal_name = JOURNALS[journal_code]["name"]
            status_area.write(f"**{journal_code}** – {journal_name}: {n} Paper geladen...")
            # grobe Fortschrittsanzeige über die Anzahl bearbeiteter Journals
            done_journals = sum(1 for c in selected if counters[c] > 0)
            progress_bar.progress(min(done_journals / len(selected), 1.0))

        try:
            scrape_selected(selected, status_callback=status_callback)
            progress_bar.progress(1.0)
            status_area.update(label="Fertig! Alle ausgewählten Journals wurden geladen.", state="complete")
        except Exception as e:
            status_area.update(label="Beim Laden ist ein Fehler aufgetreten.", state="error")
            st.error(f"Fehler: {e}")
            return

        st.cache_data.clear()
        st.session_state.show_scraper = False
        st.success("Daten erfolgreich aktualisiert. Weiter zum Dashboard...")
        st.rerun()


EMAIL_HINT_SHOWN = [False]


# =======================================================
# Bildschirm 2: Dashboard
# =======================================================
def show_dashboard():
    papers = load_papers()
    enriched = get_enriched_papers(papers)
    df = pd.DataFrame(enriched)

    # ---------------- Sidebar ----------------
    st.sidebar.markdown("### 📂 Daten")
    if st.sidebar.button("🔄 Journals laden / aktualisieren"):
        st.session_state.show_scraper = True
        st.rerun()

    st.sidebar.markdown("---")
    st.sidebar.markdown("### 🔎 Filter")

    journals = sorted(df["journal_code"].dropna().unique())
    selected_journals = st.sidebar.multiselect("Journal", journals, default=journals)

    years = df["year"].dropna().astype(int)
    if not years.empty:
        year_min, year_max = int(years.min()), int(years.max())
        if year_min == year_max:
            selected_years = (year_min, year_max)
            st.sidebar.caption(f"Alle Paper stammen aus {year_min}.")
        else:
            selected_years = st.sidebar.slider(
                "Erscheinungsjahr", year_min, year_max, (year_min, year_max)
            )
    else:
        selected_years = (0, 9999)

    only_circular = st.sidebar.checkbox("Nur Circular Economy Paper", value=False)
    only_sustainability = st.sidebar.checkbox("Nur Sustainability Orientation Paper", value=False)
    only_with_theory = st.sidebar.checkbox("Nur Paper mit erkannter Theorie", value=False)
    search_term = st.sidebar.text_input("Volltextsuche (Titel)", "")

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
    if search_term:
        filtered = filtered[filtered["title"].str.contains(search_term, case=False, na=False)]

    # ---------------- Header ----------------
    st.markdown('<div class="app-title">Theorie-Landscape</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="app-subtitle">Circular Economy & Sustainability Orientation – '
        "automatisch aus Abstracts extrahierte Theorien mittels regelbasierter Erkennung</div>",
        unsafe_allow_html=True,
    )

    if filtered.empty:
        st.warning("Für die aktuelle Filterauswahl wurden keine Paper gefunden.")
        return

    # ---------------- Kennzahlen ----------------
    c1, c2, c3, c4 = st.columns(4)
    total = len(filtered)
    with_theory = int((filtered["theory_count"] > 0).sum())
    ce_count = int(filtered["circular_economy"].sum())
    so_count = int(filtered["sustainability_orientation"].sum())

    with c1:
        metric_card("Paper gesamt", f"{total:,}".replace(",", "."))
    with c2:
        pct = f"{with_theory / total * 100:.0f}% der Paper" if total else ""
        metric_card("Mit erkannter Theorie", f"{with_theory:,}".replace(",", "."), pct)
    with c3:
        metric_card("Circular Economy", f"{ce_count:,}".replace(",", "."))
    with c4:
        metric_card("Sustainability Orientation", f"{so_count:,}".replace(",", "."))

    st.write("")
    st.markdown("---")

    # ---------------- Häufigste Theorien ----------------
    st.markdown('<div class="section-header">🏛️ Häufigste Theorien</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="section-caption">Anzahl der Paper, in denen die jeweilige Theorie erkannt wurde</div>',
        unsafe_allow_html=True,
    )

    theory_counter = count_all_theories(filtered.to_dict("records"))

    if theory_counter:
        theory_df = (
            pd.DataFrame(theory_counter.items(), columns=["Theorie", "Anzahl"])
            .sort_values("Anzahl", ascending=False)
            .reset_index(drop=True)
        )

        top_n = st.slider(
            "Anzahl angezeigter Theorien", 5, min(30, len(theory_df)), min(15, len(theory_df))
        )
        top_df = theory_df.head(top_n)

        chart = (
            alt.Chart(top_df)
            .mark_bar(cornerRadiusTopRight=4, cornerRadiusBottomRight=4, color="#2E6F5E")
            .encode(
                x=alt.X("Anzahl:Q", title="Anzahl Paper"),
                y=alt.Y("Theorie:N", sort="-x", title=None),
                tooltip=["Theorie", "Anzahl"],
            )
            .properties(height=max(280, top_n * 26))
        )
        st.altair_chart(chart, use_container_width=True)

        with st.expander("Alle Theorien als Tabelle anzeigen"):
            st.dataframe(theory_df, use_container_width=True, hide_index=True)
    else:
        st.info("Für die aktuelle Filterauswahl wurden keine Theorien erkannt.")

    st.markdown("---")

    # ---------------- Journal & Jahr nebeneinander ----------------
    col_left, col_right = st.columns(2)

    with col_left:
        st.markdown('<div class="section-header">📰 Paper pro Journal</div>', unsafe_allow_html=True)
        journal_counts = (
            filtered["journal_name"].value_counts().reset_index()
        )
        journal_counts.columns = ["Journal", "Anzahl"]
        donut = (
            alt.Chart(journal_counts)
            .mark_arc(innerRadius=60)
            .encode(
                theta="Anzahl:Q",
                color=alt.Color(
                    "Journal:N",
                    scale=alt.Scale(scheme="tealblues"),
                    legend=alt.Legend(orient="bottom", title=None),
                ),
                tooltip=["Journal", "Anzahl"],
            )
            .properties(height=340)
        )
        st.altair_chart(donut, use_container_width=True)

    with col_right:
        st.markdown('<div class="section-header">📈 Paper pro Jahr</div>', unsafe_allow_html=True)
        year_counts = (
            filtered.dropna(subset=["year"])
            .assign(year=lambda d: d["year"].astype(int))
            .groupby("year")
            .size()
            .reset_index(name="Anzahl")
        )
        area = (
            alt.Chart(year_counts)
            .mark_area(line={"color": "#2E6F5E"}, color="#E7F2EE", opacity=0.7)
            .encode(
                x=alt.X("year:O", title="Jahr"),
                y=alt.Y("Anzahl:Q"),
                tooltip=["year", "Anzahl"],
            )
            .properties(height=340)
        )
        st.altair_chart(area, use_container_width=True)

    st.markdown("---")

    # ---------------- CE vs. SO nach Journal ----------------
    st.markdown(
        '<div class="section-header">🌱 Circular Economy vs. Sustainability Orientation nach Journal</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="section-caption">Vergleich, wie viele Paper je Journal jeweils dem Thema '
        "zugeordnet wurden</div>",
        unsafe_allow_html=True,
    )

    topic_df = (
        filtered.groupby("journal_name")[["circular_economy", "sustainability_orientation"]]
        .sum()
        .reset_index()
        .melt(id_vars="journal_name", var_name="Thema", value_name="Anzahl")
    )
    topic_df["Thema"] = topic_df["Thema"].map(
        {"circular_economy": "Circular Economy", "sustainability_orientation": "Sustainability Orientation"}
    )
    grouped_bar = (
        alt.Chart(topic_df)
        .mark_bar()
        .encode(
            x=alt.X("journal_name:N", title=None, axis=alt.Axis(labelAngle=-20)),
            y=alt.Y("Anzahl:Q"),
            color=alt.Color(
                "Thema:N",
                scale=alt.Scale(range=["#2E6F5E", "#C9A227"]),
                legend=alt.Legend(orient="bottom", title=None),
            ),
            xOffset="Thema:N",
            tooltip=["journal_name", "Thema", "Anzahl"],
        )
        .properties(height=320)
    )
    st.altair_chart(grouped_bar, use_container_width=True)

    st.markdown("---")

    # ---------------- Paper-Tabelle mit Detailansicht ----------------
    st.markdown('<div class="section-header">📄 Paper im Detail</div>', unsafe_allow_html=True)

    display_df = filtered[[
        "title", "journal_code", "year", "citations",
        "theory_count", "circular_economy", "sustainability_orientation"
    ]].sort_values("theory_count", ascending=False).rename(columns={
        "title": "Titel", "journal_code": "Journal", "year": "Jahr",
        "citations": "Zitationen", "theory_count": "Theorien",
        "circular_economy": "CE", "sustainability_orientation": "SO",
    })

    st.dataframe(display_df, use_container_width=True, height=380, hide_index=True)

    csv = filtered.to_csv(index=False).encode("utf-8")
    st.download_button(
        "⬇️ Gefilterte Ergebnisse als CSV herunterladen",
        data=csv,
        file_name="theorie_landscape_export.csv",
        mime="text/csv",
    )

    st.write("")
    st.markdown("**Einzelnes Paper auswählen, um Abstract & erkannte Theorien zu sehen:**")
    paper_titles = filtered["title"].tolist()

    if paper_titles:
        selected_title = st.selectbox("Paper", paper_titles)
        selected_paper = filtered[filtered["title"] == selected_title].iloc[0]

        with st.container():
            st.markdown(f"#### {selected_paper['title']}")

            badges = ""
            if selected_paper["circular_economy"]:
                badges += '<span class="badge-ce">Circular Economy</span>'
            if selected_paper["sustainability_orientation"]:
                badges += '<span class="badge-so">Sustainability Orientation</span>'
            if badges:
                st.markdown(badges, unsafe_allow_html=True)

            meta_col1, meta_col2, meta_col3 = st.columns(3)
            meta_col1.write(f"**Journal:** {selected_paper['journal_name']} ({selected_paper['year']})")
            meta_col2.write(f"**DOI:** {selected_paper['doi']}")
            meta_col3.write(f"**Zitationen:** {selected_paper['citations']}")

            if selected_paper["all_theories"]:
                st.write("**Erkannte Theorien:** " + ", ".join(selected_paper["all_theories"]))
            else:
                st.write("**Erkannte Theorien:** keine")

            st.write("**Abstract:**")
            st.write(selected_paper["abstract"] if selected_paper["abstract"] else "_Kein Abstract verfügbar._")


# =======================================================
# Hauptprogramm
# =======================================================
def main():
    inject_css()

    if "show_scraper" not in st.session_state:
        # Wenn noch keine Daten vorhanden sind, direkt mit der Auswahl starten
        st.session_state.show_scraper = len(load_papers()) == 0

    if st.session_state.show_scraper:
        show_scraper_screen()
    else:
        show_dashboard()


if __name__ == "__main__":
    main()
