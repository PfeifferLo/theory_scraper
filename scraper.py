"""
scraper.py
Lädt Paper ausgewählter Journals aus OpenAlex und speichert sie als JSON.
"""

import os
import json
import time
import requests

# -----------------------------------------------------
# Einstellungen
# -----------------------------------------------------

# E-Mail ist optional, aber empfohlen (schnellerer "polite pool" bei OpenAlex).
# Wird NICHT im Code hinterlegt, sondern über eine Umgebungsvariable gesetzt:
#   Windows (PowerShell):  $env:SCRAPER_EMAIL = "deine@mail.at"
#   Mac/Linux:              export SCRAPER_EMAIL="deine@mail.at"
# Ohne gesetzte Variable läuft der Scraper trotzdem, nur mit niedrigeren Rate-Limits.
EMAIL = os.environ.get("SCRAPER_EMAIL", "")

HEADERS = {
    "User-Agent": f"PaperTheoryScraper/1.0 (mailto:{EMAIL})" if EMAIL else "PaperTheoryScraper/1.0"
}

DATA_DIR = "data"

JOURNALS = {
    "BSE": {
        "name": "Business Strategy and the Environment",
        "issn": "0964-4733"
    },
    "JPM": {
        "name": "Journal of Purchasing and Supply Management",
        "issn": "1478-4092"
    },
    "JCP": {
        "name": "Journal of Cleaner Production",
        "issn": "0959-6526"
    },
    "RCR": {
        "name": "Resources, Conservation and Recycling",
        "issn": "0921-3449"
    },
    "IMM": {
        "name": "Industrial Marketing Management",
        "issn": "0019-8501"
    }
}


# -----------------------------------------------------
# Abstract rekonstruieren
# -----------------------------------------------------
def reconstruct_abstract(inverted_index):
    """OpenAlex liefert Abstracts als 'inverted index' (Wort -> Positionen).
    Diese Funktion setzt daraus den Fließtext wieder zusammen."""
    if not inverted_index:
        return ""
    positions = {}
    for word, indexes in inverted_index.items():
        for i in indexes:
            positions[i] = word
    return " ".join(positions[i] for i in sorted(positions))


# -----------------------------------------------------
# Eine Seite von OpenAlex laden (mit Retry bei Fehlern)
# -----------------------------------------------------
def fetch_page(issn, cursor="*", retries=3):
    url = "https://api.openalex.org/works"
    params = {
        "filter": f"primary_location.source.issn:{issn}",
        "per-page": 200,
        "cursor": cursor
    }
    if EMAIL:
        params["mailto"] = EMAIL

    for attempt in range(1, retries + 1):
        try:
            response = requests.get(url, params=params, headers=HEADERS, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"  Fehler beim Abruf (Versuch {attempt}/{retries}): {e}")
            if attempt < retries:
                time.sleep(2 ** attempt)  # exponentielles Backoff: 2s, 4s, 8s...
            else:
                raise RuntimeError(f"Abruf für ISSN {issn} nach {retries} Versuchen fehlgeschlagen.")


# -----------------------------------------------------
# Komplettes Journal herunterladen
# -----------------------------------------------------
def scrape_journal(journal_code, progress_callback=None):
    """
    Lädt alle Paper eines Journals von OpenAlex.

    progress_callback: optionale Funktion, die mit (anzahl_geladen) aufgerufen
    wird, nachdem jede Seite geladen wurde. Damit kann z.B. ein Streamlit-UI
    live den Fortschritt anzeigen.
    """
    if journal_code not in JOURNALS:
        raise ValueError(f"Unbekanntes Journal: {journal_code}")

    journal = JOURNALS[journal_code]
    print(f"\nLade {journal['name']} ({journal_code})...\n")

    papers = []
    cursor = "*"

    while True:
        data = fetch_page(journal["issn"], cursor)
        results = data.get("results", [])

        if len(results) == 0:
            break

        for work in results:
            authors = []
            for authorship in work.get("authorships", []):
                if "author" in authorship:
                    authors.append(authorship["author"]["display_name"])

            papers.append({
                "journal_code": journal_code,
                "journal_name": journal["name"],
                "title": work.get("title", ""),
                "year": work.get("publication_year"),
                "doi": work.get("doi", ""),
                "authors": authors,
                "citations": work.get("cited_by_count", 0),
                "abstract": reconstruct_abstract(work.get("abstract_inverted_index"))
            })

        print(f"  {len(papers)} Paper geladen...")
        if progress_callback:
            progress_callback(len(papers))

        cursor = data.get("meta", {}).get("next_cursor")
        if cursor is None:
            break

    print(f"Fertig: {len(papers)} Paper für {journal_code}.")
    return papers


# -----------------------------------------------------
# Ergebnisse als JSON speichern
# -----------------------------------------------------
def save_papers(papers, journal_code):
    os.makedirs(DATA_DIR, exist_ok=True)
    filepath = os.path.join(DATA_DIR, f"{journal_code}_papers.json")
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(papers, f, ensure_ascii=False, indent=2)
    print(f"Gespeichert unter {filepath}")


def save_combined(all_papers):
    os.makedirs(DATA_DIR, exist_ok=True)
    combined_path = os.path.join(DATA_DIR, "all_papers.json")
    with open(combined_path, "w", encoding="utf-8") as f:
        json.dump(all_papers, f, ensure_ascii=False, indent=2)
    return combined_path


# -----------------------------------------------------
# Ausgewählte Journals scrapen (für UI-Aufrufe, z.B. aus Streamlit)
# -----------------------------------------------------
def scrape_selected(journal_codes, status_callback=None):
    """
    Lädt nur die übergebenen Journals (Liste von Codes, z.B. ["BSE", "JCP"]).

    status_callback: optionale Funktion status_callback(journal_code, anzahl)
    für Live-Updates in einer UI.

    Bereits vorhandene all_papers.json wird um die neu geladenen Journals
    ergänzt/aktualisiert (andere, nicht neu geladene Journals bleiben erhalten).
    """
    os.makedirs(DATA_DIR, exist_ok=True)
    combined_path = os.path.join(DATA_DIR, "all_papers.json")

    # Bestehende Daten laden, um andere Journals nicht zu verlieren
    existing = []
    if os.path.exists(combined_path):
        with open(combined_path, "r", encoding="utf-8") as f:
            existing = json.load(f)

    # Alle Paper von Journals behalten, die JETZT NICHT neu geladen werden
    kept = [p for p in existing if p.get("journal_code") not in journal_codes]

    new_papers = []
    for journal_code in journal_codes:
        try:
            def cb(n, code=journal_code):
                if status_callback:
                    status_callback(code, n)

            papers = scrape_journal(journal_code, progress_callback=cb)
            save_papers(papers, journal_code)
            new_papers.extend(papers)
        except RuntimeError as e:
            print(f"Überspringe {journal_code}: {e}")
            continue

    all_papers = kept + new_papers
    save_combined(all_papers)
    return all_papers


# -----------------------------------------------------
# Alle Journals nacheinander scrapen (klassischer CLI-Modus)
# -----------------------------------------------------
def scrape_all():
    return scrape_selected(list(JOURNALS.keys()))


# -----------------------------------------------------
# Hauptprogramm
# -----------------------------------------------------
if __name__ == "__main__":
    if not EMAIL:
        print("Hinweis: Keine SCRAPER_EMAIL gesetzt. Läuft trotzdem, aber mit niedrigeren Rate-Limits.\n")

    all_papers = scrape_all()
    print(f"\nGesamt über alle Journals: {len(all_papers)} Paper")
