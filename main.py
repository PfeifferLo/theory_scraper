"""
main.py
Streamlit-Dashboard: Auswahl & Download von Papern ausgewählter Journals
sowie Analyse der darin erkannten Theorien rund um Circular Economy &
Sustainability Orientation.
"""

import json
import os
from collections import Counter
from itertools import combinations

import altair as alt
import networkx as nx
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from scraper import JOURNALS, scrape_selected
from theory_rules import analyze_papers, count_all_theories

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
COMBINED_FILE = os.path.join(DATA_DIR, "all_papers.json")

# Spalten, die das Dashboard mindestens erwartet. Fehlt eine davon (z.B. weil
# analyze_papers() sie in Einzelfällen nicht liefert), wird sie mit einem
# sinnvollen Default ergänzt, statt dass die App mit einem KeyError abstürzt.
REQUIRED_COLUMNS = {
    "title": "",
    "authors": None,
    "abstract": "",
    "doi": "",
    "journal_code": None,
    "journal_name": "",
    "year": None,
    "citations": 0,
    "circular_economy": False,
    "sustainability_orientation": False,
    "theory_count": 0,
    "all_theories": None,  # wird unten separat als Liste behandelt
}

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

        .result-card {
            background: white;
            border: 1px solid #E7EAE8;
            border-radius: 12px;
            padding: 0.2rem 0.2rem;
            margin-bottom: 0.5rem;
        }
        .authors-line {
            color: var(--brand-muted);
            font-size: 0.85rem;
            margin-bottom: 0.4rem;
        }
        .empty-state {
            background: white;
            border: 1px dashed #C7D1CB;
            border-radius: 14px;
            padding: 2.2rem 1.6rem;
            text-align: center;
            color: var(--brand-muted);
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
# Hilfsfunktionen für Autoren
# =======================================================
def get_authors_list(row):
    """Gibt die Autorenliste eines Papers robust zurück (auch wenn das Feld fehlt)."""
    authors = row.get("authors", None) if hasattr(row, "get") else None
    if isinstance(authors, list):
        return [a for a in authors if a]
    return []


def format_authors(authors, max_shown=4):
    if not authors:
        return "Keine Autoreninformation verfügbar"
    if len(authors) <= max_shown:
        return ", ".join(authors)
    shown = ", ".join(authors[:max_shown])
    return f"{shown} et al. ({len(authors)} Autor:innen gesamt)"


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
    papers = load_papers()
    return sorted({p.get("journal_code") for p in papers if p.get("journal_code")})


def ensure_required_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Stellt sicher, dass alle vom Dashboard benötigten Spalten existieren –
    verhindert KeyError/Absturz, wenn analyze_papers() mal ein Feld nicht
    liefert oder df leer ist.
    """
    for col, default in REQUIRED_COLUMNS.items():
        if col not in df.columns:
            if col == "all_theories":
                df[col] = [[] for _ in range(len(df))]
            else:
                df[col] = default
    # all_theories kann als None statt [] vorliegen -> normalisieren
    df["all_theories"] = df["all_theories"].apply(lambda v: v if isinstance(v, list) else [])
    return df


# =======================================================
# Netzwerk-Analyse: gemeinsames Auftreten von Theorien
# =======================================================
def compute_theory_cooccurrence(records):
    """
    Zählt, wie oft je zwei Theorien gemeinsam im selben Abstract erkannt wurden,
    sowie die Gesamthäufigkeit jeder einzelnen Theorie.
    """
    pair_counter = Counter()
    freq_counter = Counter()

    for r in records:
        theories = sorted(set(r.get("all_theories", []) or []))
        for t in theories:
            freq_counter[t] += 1
        for a, b in combinations(theories, 2):
            pair_counter[(a, b)] += 1

    return pair_counter, freq_counter


def build_theory_network_figure(
    pair_counter,
    freq_counter,
    min_cooccurrence=1,
    max_nodes=40,
    highlight_theory=None,
    show_all_labels=True,
):
    """Baut eine interaktive Plotly-Netzwerkgrafik der Theorie-Co-Occurrence."""
    G = nx.Graph()

    # nur die häufigsten Theorien berücksichtigen, damit das Netzwerk lesbar bleibt
    top_theories = {t for t, _ in freq_counter.most_common(max_nodes)}

    for t, f in freq_counter.items():
        if t in top_theories:
            G.add_node(t, freq=f)

    for (a, b), c in pair_counter.items():
        if c >= min_cooccurrence and a in top_theories and b in top_theories:
            G.add_edge(a, b, weight=c)

    G.remove_nodes_from(list(nx.isolates(G)))

    if G.number_of_nodes() == 0:
        return None

    # Kamada-Kawai liefert für diese Art von Netzwerken meist deutlich
    # klarere, weniger überlappende Layouts als spring_layout. Fällt das
    # Netzwerk in mehrere unverbundene Teile, weichen wir auf spring_layout aus.
    try:
        if nx.is_connected(G):
            pos = nx.kamada_kawai_layout(G)
        else:
            pos = nx.spring_layout(G, seed=42, k=1.6 / max(1, G.number_of_nodes()) ** 0.4, iterations=200)
    except Exception:
        pos = nx.spring_layout(G, seed=42, k=1.6 / max(1, G.number_of_nodes()) ** 0.4, iterations=200)

    weights = [d["weight"] for _, _, d in G.edges(data=True)]
    max_w = max(weights) if weights else 1

    # Wenn eine Theorie hervorgehoben werden soll: Nachbarschaft bestimmen
    highlighted_neighbors = set()
    if highlight_theory and highlight_theory in G.nodes:
        highlighted_neighbors = set(G.neighbors(highlight_theory)) | {highlight_theory}

    def edge_is_dimmed(u, v):
        if not highlight_theory:
            return False
        return not (u in highlighted_neighbors and v in highlighted_neighbors)

    def node_is_dimmed(n):
        if not highlight_theory:
            return False
        return n not in highlighted_neighbors

    edge_traces = []
    for u, v, data in G.edges(data=True):
        x0, y0 = pos[u]
        x1, y1 = pos[v]
        w = data["weight"]
        width = 1.2 + (w / max_w) * 7
        dimmed = edge_is_dimmed(u, v)
        base_opacity = 0.12 if dimmed else (0.3 + 0.55 * (w / max_w))
        color = f"rgba(150,160,155,{base_opacity:.2f})" if dimmed else f"rgba(46,111,94,{base_opacity:.2f})"
        edge_traces.append(
            go.Scatter(
                x=[x0, x1, None],
                y=[y0, y1, None],
                mode="lines",
                line=dict(width=width, color=color),
                hoverinfo="skip",
                showlegend=False,
            )
        )

    # unsichtbare Hover-Punkte in der Mitte jeder Kante, damit man die
    # Anzahl gemeinsamer Paper beim Hovern über die Verbindung sehen kann
    edge_hover_x, edge_hover_y, edge_hover_text = [], [], []
    for u, v, data in G.edges(data=True):
        x0, y0 = pos[u]
        x1, y1 = pos[v]
        edge_hover_x.append((x0 + x1) / 2)
        edge_hover_y.append((y0 + y1) / 2)
        edge_hover_text.append(f"<b>{u} ↔ {v}</b><br>{data['weight']} gemeinsame Paper")

    edge_hover_trace = go.Scatter(
        x=edge_hover_x,
        y=edge_hover_y,
        mode="markers",
        marker=dict(size=10, color="rgba(0,0,0,0)"),
        hoverinfo="text",
        hovertext=edge_hover_text,
        showlegend=False,
    )

    node_x, node_y, node_text, node_size, node_hover, node_color, node_line_width = (
        [], [], [], [], [], [], []
    )
    freqs = [d.get("freq", 1) for _, d in G.nodes(data=True)]
    max_freq = max(freqs) if freqs else 1

    for node, data in G.nodes(data=True):
        x, y = pos[node]
        node_x.append(x)
        node_y.append(y)
        freq = data.get("freq", 1)
        node_size.append(18 + (freq / max_freq) * 42)
        node_hover.append(f"<b>{node}</b><br>Erkannt in {freq} Paper(en)")

        dimmed = node_is_dimmed(node)
        if node == highlight_theory:
            node_color.append("#C9A227")
            node_line_width.append(3)
        elif dimmed:
            node_color.append("rgba(180,188,183,0.5)")
            node_line_width.append(1)
        else:
            node_color.append("#2E6F5E")
            node_line_width.append(1.5)

        if show_all_labels or freq >= max(2, max_freq * 0.35) or node == highlight_theory:
            node_text.append(node)
        else:
            node_text.append("")

    node_trace = go.Scatter(
        x=node_x,
        y=node_y,
        mode="markers+text",
        text=node_text,
        textposition="top center",
        hovertext=node_hover,
        hoverinfo="text",
        marker=dict(
            size=node_size,
            color=node_color,
            line=dict(width=node_line_width, color="white"),
        ),
        textfont=dict(size=12, color="#1F2A24", family="Inter, sans-serif"),
        showlegend=False,
    )

    fig = go.Figure(data=edge_traces + [edge_hover_trace, node_trace])
    fig.update_layout(
        margin=dict(l=10, r=10, t=10, b=10),
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        height=620,
        plot_bgcolor="white",
        paper_bgcolor="white",
        hovermode="closest",
        dragmode="pan",
    )
    return fig


# =======================================================
# Bildschirm 1: Journal-Auswahl & Ladevorgang
# =======================================================
EMAIL_HINT_SHOWN = [False]


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

        # Cache leeren, damit load_papers() / get_enriched_papers() die
        # frisch gescrapten Daten sofort einlesen, statt alte Cache-Werte
        # (z.B. ein leeres [] von vor dem ersten Laden) weiterzuverwenden.
        st.cache_data.clear()
        st.session_state.show_scraper = False
        st.success("Daten erfolgreich aktualisiert. Weiter zum Dashboard...")
        st.rerun()


# =======================================================
# Bildschirm 2: Dashboard
# =======================================================
def show_dashboard():
    papers = load_papers()
    enriched = get_enriched_papers(papers)
    df = pd.DataFrame(enriched)

    # ---- Absturzsicher: keine/leere Daten ----
    if df.empty:
        st.markdown('<div class="app-title">Theorie-Landscape</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="app-subtitle">Circular Economy & Sustainability Orientation</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            """
            <div class="empty-state">
                <h4>📭 Es sind noch keine Paper geladen</h4>
                <p>Wähle in der Seitenleiste Journals aus und lade die Daten, um das Dashboard zu befüllen.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button("⬇️ Jetzt Journals laden", type="primary"):
            st.session_state.show_scraper = True
            st.rerun()
        return

    df = ensure_required_columns(df)
    all_theory_names = sorted(count_all_theories(df.to_dict("records")).keys())

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

    theory_filter = st.sidebar.multiselect(
        "Nach Theorie filtern",
        options=all_theory_names,
        help="Zeigt nur Paper, in denen mindestens eine der ausgewählten Theorien erkannt wurde.",
    )

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
    if theory_filter:
        filtered = filtered[
            filtered["all_theories"].apply(
                lambda ts: any(t in (ts or []) for t in theory_filter)
            )
        ]

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
        journal_counts = filtered["journal_name"].value_counts().reset_index()
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

    # ---------------- Netzwerk-Analyse ----------------
    st.markdown('<div class="section-header">🕸️ Theorie-Netzwerk</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="section-caption">Zeigt, welche Theorien häufig gemeinsam in einem Abstract '
        "untersucht werden. Linienstärke = Anzahl gemeinsamer Paper, Knotengröße = Gesamthäufigkeit. "
        "Zoome, verschiebe und hovere über Knoten/Kanten für Details – oder hebe gezielt eine "
        "Theorie samt ihrer Verbindungen hervor.</div>",
        unsafe_allow_html=True,
    )

    records_for_network = filtered.to_dict("records")
    pair_counter, freq_counter = compute_theory_cooccurrence(records_for_network)

    if not pair_counter:
        st.info(
            "Für die aktuelle Filterauswahl gibt es keine Paper, in denen mindestens zwei "
            "Theorien gemeinsam erkannt wurden."
        )
    else:
        net_col1, net_col2, net_col3 = st.columns([1.4, 1.4, 1.4])
        with net_col1:
            max_possible = max(pair_counter.values())
            min_co = st.slider(
                "Mind. gemeinsame Nennungen je Verbindung",
                1, max(1, max_possible), 1,
            )
        with net_col2:
            max_nodes_option = st.slider(
                "Max. Anzahl Theorien im Netzwerk", 5, max(5, len(freq_counter)), min(25, len(freq_counter))
            )
        with net_col3:
            theory_options = ["– keine –"] + sorted(freq_counter.keys())
            highlight_choice = st.selectbox(
                "Theorie hervorheben", theory_options,
                help="Hebt eine Theorie und alle direkt verbundenen Theorien farblich hervor.",
            )
            highlight_theory = None if highlight_choice == "– keine –" else highlight_choice

        show_all_labels = st.checkbox(
            "Alle Beschriftungen anzeigen (statt nur der häufigsten Theorien)", value=True
        )

        fig = build_theory_network_figure(
            pair_counter,
            freq_counter,
            min_cooccurrence=min_co,
            max_nodes=max_nodes_option,
            highlight_theory=highlight_theory,
            show_all_labels=show_all_labels,
        )

        if fig is None:
            st.info("Bei dieser Mindestanzahl bleiben keine Verbindungen übrig. Schwelle reduzieren.")
        else:
            st.plotly_chart(
                fig,
                use_container_width=True,
                config={
                    "scrollZoom": True,
                    "displaylogo": False,
                    "modeBarButtonsToRemove": ["lasso2d", "select2d"],
                },
            )

        pair_list = pair_counter.most_common()
        pair_df = pd.DataFrame(
            [{"Theorie A": a, "Theorie B": b, "Gemeinsame Paper": c} for (a, b), c in pair_list]
        )

        table_col, chart_col = st.columns([1.3, 1])
        with table_col:
            with st.expander("Häufigste Theorie-Paare als Tabelle anzeigen", expanded=False):
                st.dataframe(pair_df, use_container_width=True, hide_index=True)
        with chart_col:
            with st.expander("Top 10 Theorie-Paare als Chart anzeigen", expanded=False):
                top_pairs = pair_df.head(10).copy()
                top_pairs["Paar"] = top_pairs["Theorie A"] + " ↔ " + top_pairs["Theorie B"]
                pair_chart = (
                    alt.Chart(top_pairs)
                    .mark_bar(color="#C9A227", cornerRadiusTopRight=4, cornerRadiusBottomRight=4)
                    .encode(
                        x=alt.X("Gemeinsame Paper:Q"),
                        y=alt.Y("Paar:N", sort="-x", title=None),
                        tooltip=["Theorie A", "Theorie B", "Gemeinsame Paper"],
                    )
                    .properties(height=320)
                )
                st.altair_chart(pair_chart, use_container_width=True)

    st.markdown("---")

    # ---------------- Paper-Tabelle ----------------
    st.markdown('<div class="section-header">📄 Paper im Detail</div>', unsafe_allow_html=True)

    display_df = filtered.copy()
    display_df["Autoren"] = display_df.apply(
        lambda r: format_authors(get_authors_list(r), max_shown=2), axis=1
    )
    display_df = display_df[[
        "title", "Autoren", "journal_code", "year", "citations",
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

    st.markdown("---")

    # ---------------- Suchleiste + Ergebnisliste ----------------
    st.markdown('<div class="section-header">🔍 Paper durchsuchen</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="section-caption">Suche nach Titel, Autor:in oder Stichwort im Abstract. '
        "Nutze zusätzlich den Theorie-Filter in der Seitenleiste, um z.B. alle Abstracts zu "
        "sehen, in denen eine bestimmte Theorie vorkommt.</div>",
        unsafe_allow_html=True,
    )

    search_query = st.text_input(
        "🔎 Suchbegriff",
        placeholder="z.B. 'stakeholder theory', ein Autorenname oder ein Stichwort...",
        label_visibility="collapsed",
    )

    search_results = filtered.copy()
    if search_query:
        q = search_query.lower().strip()

        def matches(row):
            title_match = q in str(row.get("title", "")).lower()
            abstract_match = q in str(row.get("abstract", "")).lower()
            author_match = any(q in a.lower() for a in get_authors_list(row))
            return title_match or abstract_match or author_match

        search_results = search_results[search_results.apply(matches, axis=1)]

    search_results = search_results.sort_values("theory_count", ascending=False)
    total_hits = len(search_results)
    max_display = 30

    if theory_filter:
        st.caption(
            f"{total_hits} Treffer · gefiltert nach Theorie(n): {', '.join(theory_filter)}"
        )
    else:
        st.caption(f"{total_hits} Treffer")

    if total_hits == 0:
        st.info("Keine Paper gefunden, die zu Suchbegriff und Filtern passen.")
    else:
        if total_hits > max_display:
            st.caption(f"Zeige die {max_display} relevantesten Treffer (nach Anzahl erkannter Theorien sortiert).")

        for _, row in search_results.head(max_display).iterrows():
            authors = get_authors_list(row)
            badges = ""
            if row.get("circular_economy"):
                badges += '<span class="badge-ce">Circular Economy</span>'
            if row.get("sustainability_orientation"):
                badges += '<span class="badge-so">Sustainability Orientation</span>'

            with st.expander(f"{row['title']}  —  {row.get('journal_code', '')} · {row.get('year', '')}"):
                if badges:
                    st.markdown(badges, unsafe_allow_html=True)
                st.markdown(
                    f'<div class="authors-line">👤 {format_authors(authors)}</div>',
                    unsafe_allow_html=True,
                )

                meta_col1, meta_col2, meta_col3 = st.columns(3)
                meta_col1.write(f"**Journal:** {row.get('journal_name', '')} ({row.get('year', '')})")
                meta_col2.write(f"**DOI:** {row.get('doi', '') or '–'}")
                meta_col3.write(f"**Zitationen:** {row.get('citations', 0)}")

                theories = row.get("all_theories") or []
                if theories:
                    st.write("**Erkannte Theorien:** " + ", ".join(theories))
                else:
                    st.write("**Erkannte Theorien:** keine")

                st.write("**Abstract:**")
                st.write(row.get("abstract") or "_Kein Abstract verfügbar._")


# =======================================================
# Hauptprogramm
# =======================================================
def main():
    inject_css()

    if "show_scraper" not in st.session_state:
        st.session_state.show_scraper = len(load_papers()) == 0

    if st.session_state.show_scraper:
        show_scraper_screen()
    else:
        show_dashboard()


if __name__ == "__main__":
    main()
