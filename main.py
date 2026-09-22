"""
main.py
Streamlit-Dashboard: Auswahl & Download von Papern und Analyse der darin
erkannten Theorien – mit besonderem Fokus auf INNOVATIVE / NEUE Theorien.

Struktur:
1. Übersicht (Overview) mit Kennzahlen, Häufigkeitschart, Trend und
   Verteilung.
2. Innovative Theorien – eigener Tab, in dem als neu markierte Theorien
   und die dazugehörigen Paper prominent präsentiert werden.
3. Emerging Candidates – Theorien, die NICHT in der bekannten Liste
   stehen, aber sauber erkannt wurden (potentiell neue Konzepte).
4. Netzwerk – gemeinsames Auftreten von Theorien.
5. Paper – volle Detailtabelle und Suche.
"""

import json
import os
import re
from collections import Counter
from itertools import combinations

import altair as alt
import networkx as nx
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from scraper import JOURNALS, scrape_selected
from theory_rules import (
    analyze_papers,
    count_all_theories,
    count_innovative_theories,
    count_emerging_candidates,
    KNOWN_THEORIES,
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
COMBINED_FILE = os.path.join(DATA_DIR, "all_papers.json")

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
    "all_theories": None,
    "known_theories": None,
    "candidate_theories": None,
    "generic_theories": None,
    "emerging_candidates": None,
    "innovative_theories": None,
    "has_innovative_theory": False,
    "innovation_confidence": 0.0,
    "novelty_signal_count": 0,
    "unnamed_innovative_count": 0,
    "theory_innovation_score": 0,
    "novelty_snippets": None,
}

KNOWN_LOWER = {t.lower() for t in KNOWN_THEORIES}

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
        html, body, [class*="css"]  { font-family: 'Inter', sans-serif; }
        :root {
            --brand-primary: #2E6F5E;
            --brand-primary-light: #E7F2EE;
            --brand-accent: #C9A227;
            --brand-accent-light: #FBF3DC;
            --brand-ink: #1F2A24;
            --brand-muted: #6B7A72;
        }
        .block-container { padding-top: 2rem; padding-bottom: 3rem; }
        .app-title {
            font-size: 2.1rem; font-weight: 800; color: var(--brand-ink);
            margin-bottom: 0.15rem; letter-spacing: -0.02em;
        }
        .app-subtitle {
            font-size: 1rem; color: var(--brand-muted); margin-bottom: 1.5rem;
        }
        .metric-card {
            background: white; border: 1px solid #E7EAE8;
            border-radius: 14px; padding: 1.1rem 1.3rem;
            box-shadow: 0 1px 3px rgba(0,0,0,0.04); height: 100%;
        }
        .metric-card.accent {
            border: 1px solid var(--brand-accent);
            background: linear-gradient(180deg, #FDF9EA 0%, #FFFFFF 100%);
        }
        .metric-label {
            font-size: 0.8rem; font-weight: 600; color: var(--brand-muted);
            text-transform: uppercase; letter-spacing: 0.04em; margin-bottom: 0.3rem;
        }
        .metric-value {
            font-size: 1.9rem; font-weight: 800; color: var(--brand-ink);
        }
        .metric-sub {
            font-size: 0.8rem; color: var(--brand-accent);
            font-weight: 600; margin-top: 0.2rem;
        }
        .section-header {
            font-size: 1.25rem; font-weight: 700; color: var(--brand-ink);
            margin-top: 0.5rem; margin-bottom: 0.2rem;
        }
        .section-caption {
            color: var(--brand-muted); font-size: 0.88rem; margin-bottom: 0.8rem;
        }
        .journal-card {
            background: white; border: 1px solid #E7EAE8;
            border-radius: 12px; padding: 1rem 1.1rem; margin-bottom: 0.6rem;
        }
        .journal-card-title {
            font-weight: 700; color: var(--brand-ink); font-size: 0.95rem;
        }
        .journal-card-code {
            display: inline-block; background: var(--brand-primary-light);
            color: var(--brand-primary); font-weight: 700; font-size: 0.72rem;
            padding: 0.15rem 0.5rem; border-radius: 6px; margin-right: 0.5rem;
        }
        div.stButton > button {
            border-radius: 10px; font-weight: 600;
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
            font-size: 0.75rem; font-weight: 700; margin-right: 0.3rem;
        }
        .badge-innov {
            background: #FCE9C6; color: #7A5A0A;
            padding: 0.1rem 0.5rem; border-radius: 6px;
            font-size: 0.75rem; font-weight: 700; margin-right: 0.3rem;
        }
        .badge-known {
            background: #E7F2EE; color: #2E6F5E;
            padding: 0.1rem 0.5rem; border-radius: 6px;
            font-size: 0.75rem; font-weight: 700; margin-right: 0.3rem;
        }
        .badge-emerging {
            background: #F1E9F9; color: #6B3FA0;
            padding: 0.1rem 0.5rem; border-radius: 6px;
            font-size: 0.75rem; font-weight: 700; margin-right: 0.3rem;
        }
        .empty-state {
            background: white; border: 1px dashed #C7D1CB;
            border-radius: 14px; padding: 2.2rem 1.6rem;
            text-align: center; color: var(--brand-muted);
        }
        .snippet-box {
            background: #FDF9EA; border-left: 4px solid var(--brand-accent);
            padding: 0.6rem 0.8rem; margin: 0.3rem 0;
            border-radius: 6px; font-size: 0.88rem; color: var(--brand-ink);
        }
        mark.novelty {
            background: #FCE9C6; padding: 0.05rem 0.2rem; border-radius: 3px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def metric_card(label, value, sub=None, accent=False):
    sub_html = f'<div class="metric-sub">{sub}</div>' if sub else ""
    cls = "metric-card accent" if accent else "metric-card"
    st.markdown(
        f"""
        <div class="{cls}">
            <div class="metric-label">{label}</div>
            <div class="metric-value">{value}</div>
            {sub_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


# =======================================================
# Helper: Autoren
# =======================================================
def get_authors_list(row):
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
# Helper: Highlighting im Abstract
# =======================================================
NOVELTY_RE = re.compile(
    r"\b(new|novel|emerging|innovative|original|unprecedented|groundbreaking|"
    r"pioneering|nascent|alternative|propose[sd]?|develop(?:s|ed)?|"
    r"introduc(?:e|es|ed)|toward(?:s)?|theory building|theory development|"
    r"reconceptualiz\w*|paradigm shift)\b",
    re.IGNORECASE,
)


def highlight_novelty(text: str) -> str:
    if not text:
        return ""
    safe = (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
    return NOVELTY_RE.sub(lambda m: f'<mark class="novelty">{m.group(0)}</mark>', safe)


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
    list_columns = {
        "all_theories", "known_theories", "candidate_theories",
        "generic_theories", "emerging_candidates", "innovative_theories",
        "novelty_snippets", "authors",
    }
    for col, default in REQUIRED_COLUMNS.items():
        if col not in df.columns:
            if col in list_columns:
                df[col] = [[] for _ in range(len(df))]
            else:
                df[col] = default
    for col in list_columns:
        if col in df.columns:
            df[col] = df[col].apply(lambda v: v if isinstance(v, list) else [])
    return df


# =======================================================
# Netzwerk-Analyse
# =======================================================
def compute_theory_cooccurrence(records):
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
    pair_counter, freq_counter,
    min_cooccurrence=1, max_nodes=40,
    highlight_theory=None, show_all_labels=True,
    innovative_set=None,
):
    innovative_set = innovative_set or set()
    G = nx.Graph()
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

    try:
        if nx.is_connected(G):
            pos = nx.kamada_kawai_layout(G)
        else:
            pos = nx.spring_layout(G, seed=42, k=1.6 / max(1, G.number_of_nodes()) ** 0.4, iterations=200)
    except Exception:
        pos = nx.spring_layout(G, seed=42, k=1.6 / max(1, G.number_of_nodes()) ** 0.4, iterations=200)

    weights = [d["weight"] for _, _, d in G.edges(data=True)]
    max_w = max(weights) if weights else 1

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
            go.Scatter(x=[x0, x1, None], y=[y0, y1, None], mode="lines",
                       line=dict(width=width, color=color),
                       hoverinfo="skip", showlegend=False)
        )

    edge_hover_x, edge_hover_y, edge_hover_text = [], [], []
    for u, v, data in G.edges(data=True):
        x0, y0 = pos[u]; x1, y1 = pos[v]
        edge_hover_x.append((x0 + x1) / 2)
        edge_hover_y.append((y0 + y1) / 2)
        edge_hover_text.append(f"<b>{u} ↔ {v}</b><br>{data['weight']} gemeinsame Paper")

    edge_hover_trace = go.Scatter(
        x=edge_hover_x, y=edge_hover_y, mode="markers",
        marker=dict(size=10, color="rgba(0,0,0,0)"),
        hoverinfo="text", hovertext=edge_hover_text, showlegend=False,
    )

    node_x, node_y, node_text, node_size = [], [], [], []
    node_hover, node_color, node_line_width = [], [], []
    freqs = [d.get("freq", 1) for _, d in G.nodes(data=True)]
    max_freq = max(freqs) if freqs else 1

    for node, data in G.nodes(data=True):
        x, y = pos[node]
        node_x.append(x); node_y.append(y)
        freq = data.get("freq", 1)
        node_size.append(18 + (freq / max_freq) * 42)
        is_novel = node in innovative_set
        badge = " · 🆕 innovativ" if is_novel else ""
        node_hover.append(f"<b>{node}</b>{badge}<br>Erkannt in {freq} Paper(en)")

        dimmed = node_is_dimmed(node)
        if node == highlight_theory:
            node_color.append("#C9A227"); node_line_width.append(3)
        elif dimmed:
            node_color.append("rgba(180,188,183,0.5)"); node_line_width.append(1)
        elif is_novel:
            node_color.append("#C9A227"); node_line_width.append(2)
        else:
            node_color.append("#2E6F5E"); node_line_width.append(1.5)

        if show_all_labels or freq >= max(2, max_freq * 0.35) or node == highlight_theory:
            node_text.append(node)
        else:
            node_text.append("")

    node_trace = go.Scatter(
        x=node_x, y=node_y, mode="markers+text",
        text=node_text, textposition="top center",
        hovertext=node_hover, hoverinfo="text",
        marker=dict(size=node_size, color=node_color,
                    line=dict(width=node_line_width, color="white")),
        textfont=dict(size=12, color="#1F2A24", family="Inter, sans-serif"),
        showlegend=False,
    )

    fig = go.Figure(data=edge_traces + [edge_hover_trace, node_trace])
    fig.update_layout(
        margin=dict(l=10, r=10, t=10, b=10),
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        height=620, plot_bgcolor="white", paper_bgcolor="white",
        hovermode="closest", dragmode="pan",
    )
    return fig


# =======================================================
# Theorie-Trend
# =======================================================
def compute_theory_trend(df: pd.DataFrame, theories: list) -> pd.DataFrame:
    years_present = df["year"].dropna().astype(int)
    if years_present.empty or not theories:
        return pd.DataFrame(columns=["Jahr", "Theorie", "Anzahl"])
    year_min, year_max = int(years_present.min()), int(years_present.max())
    all_years = list(range(year_min, year_max + 1))
    records = []
    for theory in theories:
        mask = df["all_theories"].apply(lambda ts: theory in (ts or []))
        sub = df[mask].dropna(subset=["year"]).assign(year=lambda d: d["year"].astype(int))
        counts = sub.groupby("year").size().to_dict()
        for year in all_years:
            records.append({"Jahr": year, "Theorie": theory, "Anzahl": counts.get(year, 0)})
    return pd.DataFrame(records)


# =======================================================
# Bildschirm 1: Scraper
# =======================================================
EMAIL_HINT_SHOWN = [False]


def show_scraper_screen():
    st.markdown('<div class="app-title">📚 Paper-Daten laden</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="app-subtitle">Wähle die Journals aus, für die Paper von OpenAlex '
        "heruntergeladen werden sollen.</div>",
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
            checked = st.checkbox("Auswählen", value=(code in already_loaded), key=f"chk_{code}")
            if checked:
                selected.append(code)

    st.write("")
    col_a, col_b, _ = st.columns([1, 1, 2])
    with col_a:
        start = st.button("⬇️ Ausgewählte Journals laden", type="primary", disabled=(len(selected) == 0))
    with col_b:
        if already_loaded:
            if st.button("↩️ Zum Dashboard"):
                st.session_state.show_scraper = False
                st.rerun()

    if not EMAIL_HINT_SHOWN[0]:
        st.caption("💡 Tipp: Setze `SCRAPER_EMAIL` für OpenAlex' schnellerem 'polite pool'.")
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
            status_area.update(label="Fertig!", state="complete")
        except Exception as e:
            status_area.update(label="Fehler beim Laden.", state="error")
            st.error(f"Fehler: {e}")
            return

        st.cache_data.clear()
        st.session_state.show_scraper = False
        st.success("Daten erfolgreich aktualisiert.")
        st.rerun()


# =======================================================
# Tab 1: Overview
# =======================================================
def render_overview_tab(filtered: pd.DataFrame, theory_counter: Counter, all_theory_names: list, innovative_set: set):
    total = len(filtered)
    with_theory = int((filtered["theory_count"] > 0).sum())
    with_innov = int(filtered["has_innovative_theory"].fillna(False).astype(bool).sum())
    ce_count = int(filtered["circular_economy"].sum())
    so_count = int(filtered["sustainability_orientation"].sum())

    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        metric_card("Paper gesamt", f"{total:,}".replace(",", "."))
    with c2:
        pct = f"{with_theory / total * 100:.0f}% der Paper" if total else ""
        metric_card("Mit erkannter Theorie", f"{with_theory:,}".replace(",", "."), pct)
    with c3:
        pct = f"{with_innov / total * 100:.0f}% der Paper" if total else ""
        metric_card("Mit innovativer Theorie", f"{with_innov:,}".replace(",", "."), pct, accent=True)
    with c4:
        metric_card("Circular Economy", f"{ce_count:,}".replace(",", "."))
    with c5:
        metric_card("Sustainability Orientation", f"{so_count:,}".replace(",", "."))

    st.markdown("---")

    st.markdown('<div class="section-header">🏛️ Häufigste Theorien</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="section-caption">Anzahl der Paper, in denen die Theorie erkannt wurde. '
        "Goldene Balken = im Text explizit als NEU / innovativ vorgestellt.</div>",
        unsafe_allow_html=True,
    )

    if theory_counter:
        theory_df = (
            pd.DataFrame(theory_counter.items(), columns=["Theorie", "Anzahl"])
            .sort_values("Anzahl", ascending=False)
            .reset_index(drop=True)
        )
        theory_df["Typ"] = theory_df["Theorie"].apply(
            lambda t: "Innovativ" if t in innovative_set
            else ("Etabliert" if t.lower() in KNOWN_LOWER else "Emerging")
        )

        top_n = st.slider("Anzahl angezeigter Theorien", 5, min(30, len(theory_df)), min(15, len(theory_df)))
        top_df = theory_df.head(top_n)

        chart = (
            alt.Chart(top_df)
            .mark_bar(cornerRadiusTopRight=4, cornerRadiusBottomRight=4)
            .encode(
                x=alt.X("Anzahl:Q", title="Anzahl Paper"),
                y=alt.Y("Theorie:N", sort="-x", title=None),
                color=alt.Color(
                    "Typ:N",
                    scale=alt.Scale(
                        domain=["Etabliert", "Emerging", "Innovativ"],
                        range=["#2E6F5E", "#6B3FA0", "#C9A227"],
                    ),
                    legend=alt.Legend(orient="bottom", title=None),
                ),
                tooltip=["Theorie", "Anzahl", "Typ"],
            )
            .properties(height=max(280, top_n * 26))
        )
        st.altair_chart(chart, use_container_width=True)

        with st.expander("Alle Theorien als Tabelle"):
            st.dataframe(theory_df, use_container_width=True, hide_index=True)
    else:
        st.info("Für die aktuelle Filterauswahl wurden keine Theorien erkannt.")

    st.markdown("---")

    # Trend
    st.markdown('<div class="section-header">📈 Theorie-Trend über Zeit</div>', unsafe_allow_html=True)
    if not all_theory_names:
        st.info("Keine Theorien für Trend verfügbar.")
    else:
        default_theories = [t for t, _ in theory_counter.most_common(3)] if theory_counter else []
        col1, col2 = st.columns([2.2, 1])
        with col1:
            selected_trend_theories = st.multiselect(
                "Theorie(n) für den Trend",
                options=all_theory_names,
                default=default_theories,
            )
        with col2:
            cumulative = st.checkbox("Kumuliert anzeigen", value=False)

        if selected_trend_theories:
            trend_df = compute_theory_trend(filtered, selected_trend_theories)
            if not trend_df.empty and trend_df["Anzahl"].sum() > 0:
                if cumulative:
                    trend_df = trend_df.sort_values("Jahr")
                    trend_df["Anzahl"] = trend_df.groupby("Theorie")["Anzahl"].cumsum()
                    y_title = "Kumulierte Anzahl Paper"
                else:
                    y_title = "Anzahl Paper"

                trend_chart = (
                    alt.Chart(trend_df)
                    .mark_line(point=True, strokeWidth=2.5)
                    .encode(
                        x=alt.X("Jahr:O", title="Erscheinungsjahr"),
                        y=alt.Y("Anzahl:Q", title=y_title),
                        color=alt.Color("Theorie:N", scale=alt.Scale(scheme="tableau10"),
                                        legend=alt.Legend(orient="bottom", title=None)),
                        tooltip=["Theorie", "Jahr", "Anzahl"],
                    )
                    .properties(height=380)
                    .interactive()
                )
                st.altair_chart(trend_chart, use_container_width=True)

    st.markdown("---")

    # Journal + Jahr
    col_left, col_right = st.columns(2)
    with col_left:
        st.markdown('<div class="section-header">📰 Paper pro Journal</div>', unsafe_allow_html=True)
        journal_counts = filtered["journal_name"].value_counts().reset_index()
        journal_counts.columns = ["Journal", "Anzahl"]
        donut = (
            alt.Chart(journal_counts)
            .mark_arc(innerRadius=60)
            .encode(theta="Anzahl:Q",
                    color=alt.Color("Journal:N", scale=alt.Scale(scheme="tealblues"),
                                    legend=alt.Legend(orient="bottom", title=None)),
                    tooltip=["Journal", "Anzahl"])
            .properties(height=340)
        )
        st.altair_chart(donut, use_container_width=True)

    with col_right:
        st.markdown('<div class="section-header">📈 Paper pro Jahr</div>', unsafe_allow_html=True)
        year_counts = (
            filtered.dropna(subset=["year"])
            .assign(year=lambda d: d["year"].astype(int))
            .groupby("year").size().reset_index(name="Anzahl")
        )
        area = (
            alt.Chart(year_counts)
            .mark_area(line={"color": "#2E6F5E"}, color="#E7F2EE", opacity=0.7)
            .encode(x=alt.X("year:O", title="Jahr"),
                    y=alt.Y("Anzahl:Q"),
                    tooltip=["year", "Anzahl"])
            .properties(height=340)
        )
        st.altair_chart(area, use_container_width=True)


# =======================================================
# Tab 2: Innovative Theorien
# =======================================================
def render_innovative_tab(filtered: pd.DataFrame):
    st.markdown('<div class="section-header">🆕 Innovative / neu vorgestellte Theorien</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="section-caption">Nur Theorien, die im Abstract explizit als NEU, NOVEL, '
        "SELBST ENTWICKELT oder VORGESCHLAGEN gekennzeichnet sind. Sortiert nach Innovations-"
        "Konfidenz (0–1), die auf Häufigkeit, Klarheit und expliziter Neuheitssprache basiert.</div>",
        unsafe_allow_html=True,
    )

    innovative_df = filtered[filtered["has_innovative_theory"].fillna(False).astype(bool)].copy()

    if innovative_df.empty:
        st.info(
            "In der aktuellen Auswahl wurden keine Paper mit explizit als neu/innovativ "
            "gekennzeichneten Theorien gefunden. Erweitere die Filter oder deaktiviere den "
            "Themenfilter."
        )
        return

    innov_counter = count_innovative_theories(innovative_df.to_dict("records"))
    top_innov = innov_counter.most_common(20)

    if top_innov:
        st.markdown("#### Ranking der als neu markierten Theorien")
        innov_theory_df = pd.DataFrame(top_innov, columns=["Theorie", "Anzahl Paper"])
        chart = (
            alt.Chart(innov_theory_df)
            .mark_bar(color="#C9A227", cornerRadiusTopRight=4, cornerRadiusBottomRight=4)
            .encode(
                x=alt.X("Anzahl Paper:Q"),
                y=alt.Y("Theorie:N", sort="-x", title=None),
                tooltip=["Theorie", "Anzahl Paper"],
            )
            .properties(height=max(280, len(innov_theory_df) * 26))
        )
        st.altair_chart(chart, use_container_width=True)
    else:
        st.caption(
            "Innovations-Signale erkannt, aber ohne rekonstruierbaren Theorienamen "
            "(z.B. 'we propose a novel theory'). Die betroffenen Paper stehen unten."
        )

    st.markdown("---")
    st.markdown("#### Top-Paper nach Innovations-Konfidenz")

    innov_sorted = innovative_df.sort_values("innovation_confidence", ascending=False).head(20)

    for _, row in innov_sorted.iterrows():
        conf = row.get("innovation_confidence", 0)
        title = row.get("title", "")
        with st.expander(f"🆕 {title}  —  Konfidenz {conf:.2f}"):
            authors = get_authors_list(row)
            st.markdown(
                f'<div style="color:#6B7A72;margin-bottom:0.4rem;">'
                f'👤 {format_authors(authors)}</div>', unsafe_allow_html=True,
            )
            m1, m2, m3 = st.columns(3)
            m1.write(f"**Journal:** {row.get('journal_name', '')} ({row.get('year', '')})")
            m2.write(f"**DOI:** {row.get('doi', '') or '–'}")
            m3.write(f"**Zitationen:** {row.get('citations', 0)}")

            innov = row.get("innovative_theories") or []
            if innov:
                st.write("**Als neu vorgestellte Theorien:** " +
                         ", ".join(f"🆕 {t}" for t in innov))
            unnamed = row.get("unnamed_innovative_count", 0) or 0
            if unnamed:
                st.write(f"**Unbenannte Innovations-Signale:** {unnamed}")

            snippets = row.get("novelty_snippets") or []
            if snippets:
                st.write("**Fundstellen im Abstract:**")
                for s in snippets[:5]:
                    st.markdown(
                        f'<div class="snippet-box">…{s["snippet"]}…</div>',
                        unsafe_allow_html=True,
                    )

            st.write("**Abstract (mit Highlights):**")
            st.markdown(
                highlight_novelty(row.get("abstract") or "_Kein Abstract verfügbar._"),
                unsafe_allow_html=True,
            )


# =======================================================
# Tab 3: Emerging Candidates
# =======================================================
def render_emerging_tab(filtered: pd.DataFrame):
    st.markdown('<div class="section-header">🔬 Emerging Candidates (unbekannte Theorien)</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="section-caption">Theorien, die weder auf der bekannten Liste stehen '
        "noch als generisch aussortiert wurden – potentielle Neuentdeckungen ohne explizite "
        "'novel'-Sprache. Häufigkeit = Anzahl der Paper.</div>",
        unsafe_allow_html=True,
    )
    emerging_counter = count_emerging_candidates(filtered.to_dict("records"))

    if not emerging_counter:
        st.info("Für die aktuelle Auswahl wurden keine Emerging Candidates gefunden.")
        return

    emerging_df = pd.DataFrame(emerging_counter.most_common(), columns=["Theorie", "Anzahl"])
    min_count = st.slider(
        "Mindesthäufigkeit für Anzeige", 1, max(1, int(emerging_df["Anzahl"].max())), 1
    )
    emerging_df = emerging_df[emerging_df["Anzahl"] >= min_count]

    chart = (
        alt.Chart(emerging_df.head(30))
        .mark_bar(color="#6B3FA0", cornerRadiusTopRight=4, cornerRadiusBottomRight=4)
        .encode(
            x=alt.X("Anzahl:Q"),
            y=alt.Y("Theorie:N", sort="-x", title=None),
            tooltip=["Theorie", "Anzahl"],
        )
        .properties(height=max(280, min(30, len(emerging_df)) * 24))
    )
    st.altair_chart(chart, use_container_width=True)

    with st.expander("Alle Emerging Candidates als Tabelle"):
        st.dataframe(emerging_df, use_container_width=True, hide_index=True)


# =======================================================
# Tab 4: Netzwerk
# =======================================================
def render_network_tab(filtered: pd.DataFrame, innovative_set: set):
    st.markdown('<div class="section-header">🕸️ Theorie-Netzwerk</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="section-caption">Gemeinsames Auftreten von Theorien in einem Abstract. '
        "Goldene Knoten = im Text als neu markiert.</div>",
        unsafe_allow_html=True,
    )

    records_for_network = filtered.to_dict("records")
    pair_counter, freq_counter = compute_theory_cooccurrence(records_for_network)

    if not pair_counter:
        st.info("Keine gemeinsam auftretenden Theoriepaare in der aktuellen Auswahl.")
        return

    c1, c2, c3 = st.columns([1.4, 1.4, 1.4])
    with c1:
        max_possible = max(pair_counter.values())
        min_co = st.slider("Mind. gemeinsame Nennungen", 1, max(1, max_possible), 1)
    with c2:
        max_nodes_option = st.slider("Max. Theorien im Netzwerk", 5,
                                     max(5, len(freq_counter)), min(25, len(freq_counter)))
    with c3:
        theory_options = ["– keine –"] + sorted(freq_counter.keys())
        highlight_choice = st.selectbox("Theorie hervorheben", theory_options)
        highlight_theory = None if highlight_choice == "– keine –" else highlight_choice

    show_all_labels = st.checkbox("Alle Beschriftungen anzeigen", value=True)

    fig = build_theory_network_figure(
        pair_counter, freq_counter,
        min_cooccurrence=min_co, max_nodes=max_nodes_option,
        highlight_theory=highlight_theory, show_all_labels=show_all_labels,
        innovative_set=innovative_set,
    )
    if fig is None:
        st.info("Bei dieser Schwelle bleiben keine Verbindungen übrig.")
        return

    st.plotly_chart(
        fig, use_container_width=True,
        config={"scrollZoom": True, "displaylogo": False,
                "modeBarButtonsToRemove": ["lasso2d", "select2d"]},
    )

    pair_list = pair_counter.most_common()
    pair_df = pd.DataFrame(
        [{"Theorie A": a, "Theorie B": b, "Gemeinsame Paper": c} for (a, b), c in pair_list]
    )
    with st.expander("Häufigste Theorie-Paare"):
        st.dataframe(pair_df, use_container_width=True, hide_index=True)


# =======================================================
# Tab 5: Paper
# =======================================================
def render_papers_tab(filtered: pd.DataFrame, theory_filter: list):
    st.markdown('<div class="section-header">📄 Paper im Detail</div>', unsafe_allow_html=True)

    display_df = filtered.copy()
    display_df["Autoren"] = display_df.apply(
        lambda r: format_authors(get_authors_list(r), max_shown=2), axis=1
    )
    display_df["Innov."] = display_df["innovation_confidence"].fillna(0).round(2)
    display_df = display_df[[
        "title", "Autoren", "journal_code", "year", "citations",
        "theory_count", "Innov.", "circular_economy", "sustainability_orientation",
    ]].sort_values(
        ["Innov.", "theory_count"], ascending=[False, False]
    ).rename(columns={
        "title": "Titel", "journal_code": "Journal", "year": "Jahr",
        "citations": "Zit.", "theory_count": "Theorien",
        "circular_economy": "CE", "sustainability_orientation": "SO",
    })

    st.dataframe(display_df, use_container_width=True, height=420, hide_index=True)

    csv = filtered.to_csv(index=False).encode("utf-8")
    st.download_button(
        "⬇️ Gefilterte Ergebnisse als CSV",
        data=csv, file_name="theorie_landscape_export.csv", mime="text/csv",
    )

    st.markdown("---")

    st.markdown('<div class="section-header">🔍 Paper durchsuchen</div>', unsafe_allow_html=True)
    search_query = st.text_input(
        "🔎 Suchbegriff",
        placeholder="Titel, Autor:in oder Stichwort im Abstract...",
        label_visibility="collapsed",
    )

    search_results = filtered.copy()
    if search_query:
        q = search_query.lower().strip()

        def matches(row):
            return (
                q in str(row.get("title", "")).lower()
                or q in str(row.get("abstract", "")).lower()
                or any(q in a.lower() for a in get_authors_list(row))
            )

        search_results = search_results[search_results.apply(matches, axis=1)]

    search_results = search_results.sort_values(
        ["innovation_confidence", "theory_count"], ascending=[False, False]
    )
    total_hits = len(search_results)
    max_display = 30

    if theory_filter:
        st.caption(f"{total_hits} Treffer · gefiltert nach: {', '.join(theory_filter)}")
    else:
        st.caption(f"{total_hits} Treffer")

    if total_hits == 0:
        st.info("Keine Paper gefunden.")
        return

    if total_hits > max_display:
        st.caption(f"Zeige die {max_display} relevantesten Treffer.")

    for _, row in search_results.head(max_display).iterrows():
        authors = get_authors_list(row)
        badges = ""
        if row.get("has_innovative_theory"):
            badges += '<span class="badge-innov">🆕 Innovative Theorie</span>'
        if row.get("circular_economy"):
            badges += '<span class="badge-ce">Circular Economy</span>'
        if row.get("sustainability_orientation"):
            badges += '<span class="badge-so">Sustainability Orientation</span>'

        title = row.get('title', '')
        conf = row.get("innovation_confidence", 0)
        suffix = f" · 🆕 {conf:.2f}" if conf and conf > 0 else ""

        with st.expander(f"{title}  —  {row.get('journal_code', '')} · {row.get('year', '')}{suffix}"):
            if badges:
                st.markdown(badges, unsafe_allow_html=True)
            st.markdown(
                f'<div style="color:#6B7A72;font-size:0.85rem;margin-bottom:0.4rem;">'
                f'👤 {format_authors(authors)}</div>', unsafe_allow_html=True,
            )
            m1, m2, m3 = st.columns(3)
            m1.write(f"**Journal:** {row.get('journal_name', '')} ({row.get('year', '')})")
            m2.write(f"**DOI:** {row.get('doi', '') or '–'}")
            m3.write(f"**Zitationen:** {row.get('citations', 0)}")

            known = row.get("known_theories") or []
            emerging = row.get("emerging_candidates") or []
            innov = row.get("innovative_theories") or []

            if known:
                st.markdown("**Etablierte Theorien:** " +
                            ", ".join(f'<span class="badge-known">{t}</span>' for t in known),
                            unsafe_allow_html=True)
            if emerging:
                st.markdown("**Emerging Candidates:** " +
                            ", ".join(f'<span class="badge-emerging">{t}</span>' for t in emerging),
                            unsafe_allow_html=True)
            if innov:
                st.markdown("**Als neu markierte Theorien:** " +
                            ", ".join(f'<span class="badge-innov">🆕 {t}</span>' for t in innov),
                            unsafe_allow_html=True)
            if not (known or emerging or innov):
                st.write("**Erkannte Theorien:** keine")

            st.write("**Abstract:**")
            st.markdown(
                highlight_novelty(row.get("abstract") or "_Kein Abstract verfügbar._"),
                unsafe_allow_html=True,
            )

            # Debug: verworfene Generics
            generic = row.get("generic_theories") or []
            if generic:
                with st.popover("🔧 Debug: als generisch verworfene Kandidaten"):
                    st.write(", ".join(generic))


# =======================================================
# Dashboard
# =======================================================
def show_dashboard():
    papers = load_papers()
    enriched = get_enriched_papers(papers)
    df = pd.DataFrame(enriched)

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
                <p>Wähle in der Seitenleiste Journals aus und lade die Daten.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button("⬇️ Jetzt Journals laden", type="primary"):
            st.session_state.show_scraper = True
            st.rerun()
        return

    df = ensure_required_columns(df)

    # Basis-Zähler
    all_theory_counter = count_all_theories(df.to_dict("records"))
    all_theory_names = sorted(all_theory_counter.keys())
    all_innovative_counter = count_innovative_theories(df.to_dict("records"))
    innovative_set_global = set(all_innovative_counter.keys())

    # ---- Sidebar ----
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
            st.sidebar.caption(f"Alle Paper aus {year_min}.")
        else:
            selected_years = st.sidebar.slider(
                "Erscheinungsjahr", year_min, year_max, (year_min, year_max)
            )
    else:
        selected_years = (0, 9999)

    only_circular = st.sidebar.checkbox("Nur Circular Economy", value=False)
    only_sustainability = st.sidebar.checkbox("Nur Sustainability Orientation", value=False)
    only_with_theory = st.sidebar.checkbox("Nur Paper mit erkannter Theorie", value=False)
    only_innovative = st.sidebar.checkbox("🆕 Nur Paper mit innovativer Theorie", value=False)

    min_confidence = st.sidebar.slider(
        "Min. Innovations-Konfidenz",
        0.0, 1.0, 0.0, 0.05,
        help="Filtert Paper nach der Konfidenz, mit der eine neue Theorie erkannt wurde.",
    )

    theory_filter = st.sidebar.multiselect(
        "Nach Theorie filtern", options=all_theory_names,
        help="Zeigt nur Paper, in denen mindestens eine der Theorien vorkommt.",
    )

    # Filter anwenden
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
    if only_innovative:
        filtered = filtered[filtered["has_innovative_theory"].fillna(False).astype(bool)]
    if min_confidence > 0:
        filtered = filtered[filtered["innovation_confidence"].fillna(0) >= min_confidence]
    if theory_filter:
        filtered = filtered[
            filtered["all_theories"].apply(lambda ts: any(t in (ts or []) for t in theory_filter))
        ]

    # Header
    st.markdown('<div class="app-title">Theorie-Landscape</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="app-subtitle">Circular Economy & Sustainability Orientation – '
        "regelbasierte Erkennung etablierter und neuer Theorien</div>",
        unsafe_allow_html=True,
    )

    if filtered.empty:
        st.warning("Für die aktuelle Filterauswahl wurden keine Paper gefunden.")
        return

    theory_counter = count_all_theories(filtered.to_dict("records"))

    # Tabs
    tab_overview, tab_innov, tab_emerging, tab_network, tab_papers = st.tabs([
        "📊 Übersicht",
        "🆕 Innovative Theorien",
        "🔬 Emerging Candidates",
        "🕸️ Netzwerk",
        "📄 Paper",
    ])

    with tab_overview:
        render_overview_tab(filtered, theory_counter, all_theory_names, innovative_set_global)
    with tab_innov:
        render_innovative_tab(filtered)
    with tab_emerging:
        render_emerging_tab(filtered)
    with tab_network:
        render_network_tab(filtered, innovative_set_global)
    with tab_papers:
        render_papers_tab(filtered, theory_filter)


# =======================================================
# main
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
