"""
theory_rules.py
Regelbasierte Erkennung von Theorien in Paper-Abstracts.

Drei Methoden werden kombiniert:
1. Feste Liste bekannter Theorien (Dictionary-Matching per Regex)
2. Signalwörter, die typischerweise vor einer Theoriennennung stehen
   (z.B. "based on", "drawing on", "grounded in") -> Kandidaten-Extraktion
3. Generische Erkennung: jedes Wort/jede kurze Wortfolge direkt vor einem
   Theorie-Schlüsselwort ("theory", "view", "model", ...), unabhängig
   davon, ob die Theorie in KNOWN_THEORIES steht. Fängt z.B. "Game Theory"
   oder "Equity Theory" ab, auch wenn sie nicht in der festen Liste stehen.
"""

import re
from collections import Counter


# -----------------------------------------------------
# 1. Bekannte Theorien (feste Liste)
# -----------------------------------------------------
# Liste kann jederzeit erweitert werden. Groß-/Kleinschreibung spielt
# beim Matching keine Rolle (re.IGNORECASE).
KNOWN_THEORIES = [
    "Stakeholder Theory",
    "Resource-Based View",
    "Natural Resource-Based View",
    "Dynamic Capabilities",
    "Institutional Theory",
    "Legitimacy Theory",
    "Agency Theory",
    "Transaction Cost Economics",
    "Transaction Cost Theory",
    "Upper Echelons Theory",
    "Signaling Theory",
    "Social Exchange Theory",
    "Contingency Theory",
    "Diffusion of Innovation Theory",
    "Technology Acceptance Model",
    "Theory of Planned Behavior",
    "Theory of Reasoned Action",
    "Absorptive Capacity",
    "Knowledge-Based View",
    "Practice Theory",
    "Ecological Modernization Theory",
    "Stakeholder Salience Theory",
    "Corporate Social Responsibility Theory",
    "Triple Bottom Line",
    "Circular Economy Theory",
    "Industrial Ecology",
    "Cradle-to-Cradle",
    "Sustainability Transitions Theory",
    "Socio-Technical Transitions Theory",
    "Multi-Level Perspective",
    "Institutional Isomorphism",
    "Path Dependence Theory",
    "Organizational Learning Theory",
    "Behavioral Theory of the Firm",
    "Complexity Theory",
    "Systems Theory",
    "Actor-Network Theory",
    "Social Identity Theory",
    "Structuration Theory",
]

# Regex-Muster vorkompilieren (schneller bei vielen Abstracts)
KNOWN_THEORY_PATTERNS = {
    theory: re.compile(re.escape(theory), re.IGNORECASE)
    for theory in KNOWN_THEORIES
}


# -----------------------------------------------------
# 2. Signalwörter, die auf eine Theorie hindeuten
# -----------------------------------------------------
SIGNAL_PHRASES = [
    r"based on(?: the)?",
    r"drawing on(?: the)?",
    r"grounded in(?: the)?",
    r"building on(?: the)?",
    r"according to(?: the)?",
    r"using the lens of",
    r"through the lens of",
    r"guided by(?: the)?",
    r"informed by(?: the)?",
    r"rooted in(?: the)?",
    r"applying(?: the)?",
    r"adopting(?: the)?",
    r"employing(?: the)?",
]

# Wörter, die am Ende einer Theoriebezeichnung stehen.
# "model" bewusst ausgeschlossen (siehe GENERIC_THEORY_KEYWORD_RE weiter
# unten) - zu viele Fehltreffer wie "regression model", "conceptual model".
THEORY_KEYWORDS = r"(theory|view|perspective|approach|framework|paradigm)"

# Kombiniertes Muster: Signalphrase + bis zu 6 Wörter + Theorie-Schlüsselwort
SIGNAL_PATTERN = re.compile(
    r"(?:" + "|".join(SIGNAL_PHRASES) + r")\s+"
    r"((?:[A-Za-z][\w\-]*\s+){0,6}" + THEORY_KEYWORDS + r")",
    re.IGNORECASE
)


# -----------------------------------------------------
# 3. Generische Erkennung: "<Begriff> + Theorie-Schlüsselwort"
#    Fängt auch Theorien ab, die NICHT in KNOWN_THEORIES stehen
#    (z.B. "Game Theory", "Equity Theory", "Framing Theory"),
#    solange direkt "theory/view/model/..." danach steht.
# -----------------------------------------------------

# Wörter, die NICHT Teil eines Theorienamens sein dürfen -> Abbruchkriterium
# beim Rückwärtslaufen. Bewusst konservativ gehalten, um False Positives
# wie "This Theory" oder "Our Theory" zu vermeiden.
GENERIC_STOPWORDS = {
    "a", "an", "the", "this", "that", "these", "those", "our", "their",
    "its", "his", "her", "my", "your", "one", "such", "any", "each",
    "every", "some", "no", "new", "current", "existing", "prior",
    "previous", "related", "relevant", "respective", "above",
    "following", "same", "given", "certain", "particular",
    "we", "they", "it", "he", "she", "i", "you", "who", "which",
    "is", "are", "was", "were", "be", "been", "being",
    "and", "or", "but", "of", "in", "on", "for", "to", "from",
    "with", "as", "by", "at", "into", "consider", "considering",
    "considered", "use", "using", "used", "apply", "applying",
    "applied", "develop", "developing", "developed", "provide",
    "providing", "paper", "study", "research",
}

# Theorie-Schlüsselwörter als eigenständige Tokens (kein "approach" etc.
# doppelt zählen, wenn's schon in KNOWN_THEORIES matched hat).
# "model" ist bewusst ausgeschlossen: zu viele Fehltreffer wie "regression
# model", "conceptual model", "structural equation model" (letzteres bleibt
# über KNOWN_THEORIES abgedeckt, sofern explizit gelistet).
GENERIC_THEORY_KEYWORD_RE = re.compile(
    r"^(theory|theories|view|perspective|framework|paradigm)$",
    re.IGNORECASE,
)

# Tokenizer: Wörter und Satzzeichen getrennt erfassen, damit wir am
# Komma/Punkt sauber abbrechen können (z.B. "..., framing theory, ...")
_TOKEN_RE = re.compile(r"[A-Za-z][\w\-]*|[.,;:()\[\]]")


def extract_generic_theories(abstract: str, max_words: int = 3) -> list:
    """
    Läuft von jedem Theorie-Schlüsselwort ("theory", "view", "model", ...)
    rückwärts durch die vorangehenden Wörter und sammelt sie, solange sie
    keine Satzzeichen oder Füllwörter (GENERIC_STOPWORDS) sind.
    Dadurch werden auch Theorien erfasst, die nicht in KNOWN_THEORIES
    stehen (z.B. "Game Theory", "Equity Theory").
    """
    if not abstract:
        return []

    tokens = _TOKEN_RE.findall(abstract)
    found = []

    for i, tok in enumerate(tokens):
        if not GENERIC_THEORY_KEYWORD_RE.match(tok):
            continue

        words = []
        j = i - 1
        while j >= 0 and len(words) < max_words:
            w = tokens[j]
            if len(w) == 1 and not w.isalnum():  # Satzzeichen -> Stopp
                break
            if w.lower() in GENERIC_STOPWORDS:
                break
            words.insert(0, w)
            j -= 1

        if words:  # nur werten, wenn mind. ein sinnvolles Wort davor steht
            phrase = " ".join(words + [tok])
            found.append(phrase.title())

    return found


# -----------------------------------------------------
# Extraktion für einen einzelnen Abstract
# -----------------------------------------------------
def extract_known_theories(abstract: str) -> list:
    """Sucht nach Treffern aus der festen Theorien-Liste.
    Ist eine Theorie Teilstring einer anderen gefundenen Theorie
    (z.B. 'Resource-Based View' in 'Natural Resource-Based View'),
    wird nur die spezifischere (längere) behalten."""
    if not abstract:
        return []
    found = []
    for theory, pattern in KNOWN_THEORY_PATTERNS.items():
        if pattern.search(abstract):
            found.append(theory)

    # Kürzere Treffer entfernen, wenn sie in einem längeren enthalten sind
    filtered = []
    for theory in found:
        is_substring_of_other = any(
            theory.lower() != other.lower() and theory.lower() in other.lower()
            for other in found
        )
        if not is_substring_of_other:
            filtered.append(theory)
    return filtered


def extract_candidate_theories(abstract: str) -> list:
    """Sucht nach Signalwort + Theorie-Muster, um auch unbekannte/neue
    Theorienbezeichnungen zu erfassen, die nicht in KNOWN_THEORIES stehen."""
    if not abstract:
        return []
    matches = SIGNAL_PATTERN.findall(abstract)
    # findall gibt bei Gruppen Tupel zurück -> nur ersten Teil (ganze Phrase) nehmen
    candidates = []
    for match in matches:
        phrase = match[0] if isinstance(match, tuple) else match
        candidates.append(phrase.strip().title())
    return candidates


def extract_theories_from_abstract(abstract: str) -> dict:
    """Kombiniert alle drei Methoden und gibt strukturiertes Ergebnis zurück."""
    known = extract_known_theories(abstract)
    candidates = extract_candidate_theories(abstract)
    generic = extract_generic_theories(abstract)

    # Kandidaten, die bereits als bekannte Theorie erfasst wurden, nicht doppelt zählen
    candidates_filtered = [
        c for c in candidates
        if not any(c.lower() in k.lower() or k.lower() in c.lower() for k in known)
    ]

    # Generische Treffer gegen 'known' und 'candidates' abgleichen, damit
    # nichts doppelt gezählt wird (z.B. "Stakeholder Theory" käme sonst
    # sowohl aus known_theories als auch aus generic_theories)
    already_found = known + candidates_filtered
    generic_filtered = []
    seen_lower = set()
    for g in generic:
        if any(g.lower() in af.lower() or af.lower() in g.lower() for af in already_found):
            continue
        if g.lower() in seen_lower:  # Duplikate innerhalb generic selbst raus
            continue
        seen_lower.add(g.lower())
        generic_filtered.append(g)

    return {
        "known_theories": known,
        "candidate_theories": candidates_filtered,
        "generic_theories": generic_filtered,  # separat sichtbar für Debugging/Filter
        "all_theories": known + candidates_filtered + generic_filtered,
        "theory_count": len(known) + len(candidates_filtered) + len(generic_filtered),
    }


# -----------------------------------------------------
# Zusatz-Check: Circular Economy / Sustainability Orientation
# -----------------------------------------------------
CIRCULAR_ECONOMY_KEYWORDS = [
    "circular economy", "closed-loop", "reuse", "recycling", "remanufactur",
    "cradle-to-cradle", "circularity", "resource loop", "industrial symbiosis"
]

SUSTAINABILITY_ORIENTATION_KEYWORDS = [
    "sustainability orientation", "sustainable orientation",
    "environmental orientation", "sustainability-oriented",
    "corporate sustainability", "sustainable development"
]


def check_topic_relevance(abstract: str) -> dict:
    """Prüft, ob der Abstract Circular-Economy- bzw. Sustainability-Orientation-
    Begriffe enthält."""
    if not abstract:
        return {"circular_economy": False, "sustainability_orientation": False}
    text = abstract.lower()
    return {
        "circular_economy": any(kw in text for kw in CIRCULAR_ECONOMY_KEYWORDS),
        "sustainability_orientation": any(kw in text for kw in SUSTAINABILITY_ORIENTATION_KEYWORDS),
    }


# -----------------------------------------------------
# Analyse einer ganzen Paper-Liste
# -----------------------------------------------------
def analyze_papers(papers: list) -> list:
    """Reichert jede Paper-Dict um Theorien- und Themen-Infos an."""
    enriched = []
    for paper in papers:
        abstract = paper.get("abstract", "")
        theory_result = extract_theories_from_abstract(abstract)
        topic_result = check_topic_relevance(abstract)

        enriched_paper = dict(paper)  # Kopie, Original nicht verändern
        enriched_paper.update(theory_result)
        enriched_paper.update(topic_result)
        enriched.append(enriched_paper)
    return enriched


def count_all_theories(enriched_papers: list) -> Counter:
    """Zählt, wie oft jede Theorie über alle Paper hinweg vorkommt."""
    counter = Counter()
    for paper in enriched_papers:
        for theory in paper.get("all_theories", []):
            counter[theory] += 1
    return counter


# -----------------------------------------------------
# Test
# -----------------------------------------------------
if __name__ == "__main__":
    test_abstract = (
        "This study is based on Stakeholder Theory and draws on the "
        "Natural Resource-Based View to examine circular economy practices "
        "and sustainability orientation in manufacturing firms. Grounded in "
        "institutional theory, we further explore adoption barriers. We "
        "consider equity theory, framing theory, mental accounting, social "
        "exchange theory, signaling theory, agency theory, game theory, "
        "and institutional theory in terms of their implications."
    )
    result = extract_theories_from_abstract(test_abstract)
    print(result)
    print(check_topic_relevance(test_abstract))"""
theory_rules.py
Regelbasierte Erkennung von Theorien in Paper-Abstracts.

Drei Methoden werden kombiniert:
1. Feste Liste bekannter Theorien (Dictionary-Matching per Regex)
2. Signalwörter, die typischerweise vor einer Theoriennennung stehen
   (z.B. "based on", "drawing on", "grounded in") -> Kandidaten-Extraktion
3. Generische Erkennung: jedes Wort/jede kurze Wortfolge direkt vor einem
   Theorie-Schlüsselwort ("theory", "view", "model", ...), unabhängig
   davon, ob die Theorie in KNOWN_THEORIES steht. Fängt z.B. "Game Theory"
   oder "Equity Theory" ab, auch wenn sie nicht in der festen Liste stehen.
"""

import re
from collections import Counter


# -----------------------------------------------------
# 1. Bekannte Theorien (feste Liste)
# -----------------------------------------------------
# Liste kann jederzeit erweitert werden. Groß-/Kleinschreibung spielt
# beim Matching keine Rolle (re.IGNORECASE).
KNOWN_THEORIES = [
    "Stakeholder Theory",
    "Resource-Based View",
    "Natural Resource-Based View",
    "Dynamic Capabilities",
    "Institutional Theory",
    "Legitimacy Theory",
    "Agency Theory",
    "Transaction Cost Economics",
    "Transaction Cost Theory",
    "Upper Echelons Theory",
    "Signaling Theory",
    "Social Exchange Theory",
    "Contingency Theory",
    "Diffusion of Innovation Theory",
    "Technology Acceptance Model",
    "Theory of Planned Behavior",
    "Theory of Reasoned Action",
    "Absorptive Capacity",
    "Knowledge-Based View",
    "Practice Theory",
    "Ecological Modernization Theory",
    "Stakeholder Salience Theory",
    "Corporate Social Responsibility Theory",
    "Triple Bottom Line",
    "Circular Economy Theory",
    "Industrial Ecology",
    "Cradle-to-Cradle",
    "Sustainability Transitions Theory",
    "Socio-Technical Transitions Theory",
    "Multi-Level Perspective",
    "Institutional Isomorphism",
    "Path Dependence Theory",
    "Organizational Learning Theory",
    "Behavioral Theory of the Firm",
    "Complexity Theory",
    "Systems Theory",
    "Actor-Network Theory",
    "Social Identity Theory",
    "Structuration Theory",
]

# Regex-Muster vorkompilieren (schneller bei vielen Abstracts)
KNOWN_THEORY_PATTERNS = {
    theory: re.compile(re.escape(theory), re.IGNORECASE)
    for theory in KNOWN_THEORIES
}


# -----------------------------------------------------
# 2. Signalwörter, die auf eine Theorie hindeuten
# -----------------------------------------------------
SIGNAL_PHRASES = [
    r"based on(?: the)?",
    r"drawing on(?: the)?",
    r"grounded in(?: the)?",
    r"building on(?: the)?",
    r"according to(?: the)?",
    r"using the lens of",
    r"through the lens of",
    r"guided by(?: the)?",
    r"informed by(?: the)?",
    r"rooted in(?: the)?",
    r"applying(?: the)?",
    r"adopting(?: the)?",
    r"employing(?: the)?",
]

# Wörter, die am Ende einer Theoriebezeichnung stehen
THEORY_KEYWORDS = r"(theory|view|perspective|approach|model|framework|paradigm)"

# Kombiniertes Muster: Signalphrase + bis zu 6 Wörter + Theorie-Schlüsselwort
SIGNAL_PATTERN = re.compile(
    r"(?:" + "|".join(SIGNAL_PHRASES) + r")\s+"
    r"((?:[A-Za-z][\w\-]*\s+){0,6}" + THEORY_KEYWORDS + r")",
    re.IGNORECASE
)


# -----------------------------------------------------
# 3. Generische Erkennung: "<Begriff> + Theorie-Schlüsselwort"
#    Fängt auch Theorien ab, die NICHT in KNOWN_THEORIES stehen
#    (z.B. "Game Theory", "Equity Theory", "Framing Theory"),
#    solange direkt "theory/view/model/..." danach steht.
# -----------------------------------------------------

# Wörter, die NICHT Teil eines Theorienamens sein dürfen -> Abbruchkriterium
# beim Rückwärtslaufen. Bewusst konservativ gehalten, um False Positives
# wie "This Theory" oder "Our Theory" zu vermeiden.
GENERIC_STOPWORDS = {
    "a", "an", "the", "this", "that", "these", "those", "our", "their",
    "its", "his", "her", "my", "your", "one", "such", "any", "each",
    "every", "some", "no", "new", "current", "existing", "prior",
    "previous", "related", "relevant", "respective", "above",
    "following", "same", "given", "certain", "particular",
    "we", "they", "it", "he", "she", "i", "you", "who", "which",
    "is", "are", "was", "were", "be", "been", "being",
    "and", "or", "but", "of", "in", "on", "for", "to", "from",
    "with", "as", "by", "at", "into", "consider", "considering",
    "considered", "use", "using", "used", "apply", "applying",
    "applied", "develop", "developing", "developed", "provide",
    "providing", "paper", "study", "research",
}

# Theorie-Schlüsselwörter als eigenständige Tokens (kein "approach" etc.
# doppelt zählen, wenn's schon in KNOWN_THEORIES matched hat)
GENERIC_THEORY_KEYWORD_RE = re.compile(
    r"^(theory|theories|view|perspective|model|framework|paradigm)$",
    re.IGNORECASE,
)

# Tokenizer: Wörter und Satzzeichen getrennt erfassen, damit wir am
# Komma/Punkt sauber abbrechen können (z.B. "..., framing theory, ...")
_TOKEN_RE = re.compile(r"[A-Za-z][\w\-]*|[.,;:()\[\]]")


def extract_generic_theories(abstract: str, max_words: int = 3) -> list:
    """
    Läuft von jedem Theorie-Schlüsselwort ("theory", "view", "model", ...)
    rückwärts durch die vorangehenden Wörter und sammelt sie, solange sie
    keine Satzzeichen oder Füllwörter (GENERIC_STOPWORDS) sind.
    Dadurch werden auch Theorien erfasst, die nicht in KNOWN_THEORIES
    stehen (z.B. "Game Theory", "Equity Theory").
    """
    if not abstract:
        return []

    tokens = _TOKEN_RE.findall(abstract)
    found = []

    for i, tok in enumerate(tokens):
        if not GENERIC_THEORY_KEYWORD_RE.match(tok):
            continue

        words = []
        j = i - 1
        while j >= 0 and len(words) < max_words:
            w = tokens[j]
            if len(w) == 1 and not w.isalnum():  # Satzzeichen -> Stopp
                break
            if w.lower() in GENERIC_STOPWORDS:
                break
            words.insert(0, w)
            j -= 1

        if words:  # nur werten, wenn mind. ein sinnvolles Wort davor steht
            phrase = " ".join(words + [tok])
            found.append(phrase.title())

    return found


# -----------------------------------------------------
# Extraktion für einen einzelnen Abstract
# -----------------------------------------------------
def extract_known_theories(abstract: str) -> list:
    """Sucht nach Treffern aus der festen Theorien-Liste.
    Ist eine Theorie Teilstring einer anderen gefundenen Theorie
    (z.B. 'Resource-Based View' in 'Natural Resource-Based View'),
    wird nur die spezifischere (längere) behalten."""
    if not abstract:
        return []
    found = []
    for theory, pattern in KNOWN_THEORY_PATTERNS.items():
        if pattern.search(abstract):
            found.append(theory)

    # Kürzere Treffer entfernen, wenn sie in einem längeren enthalten sind
    filtered = []
    for theory in found:
        is_substring_of_other = any(
            theory.lower() != other.lower() and theory.lower() in other.lower()
            for other in found
        )
        if not is_substring_of_other:
            filtered.append(theory)
    return filtered


def extract_candidate_theories(abstract: str) -> list:
    """Sucht nach Signalwort + Theorie-Muster, um auch unbekannte/neue
    Theorienbezeichnungen zu erfassen, die nicht in KNOWN_THEORIES stehen."""
    if not abstract:
        return []
    matches = SIGNAL_PATTERN.findall(abstract)
    # findall gibt bei Gruppen Tupel zurück -> nur ersten Teil (ganze Phrase) nehmen
    candidates = []
    for match in matches:
        phrase = match[0] if isinstance(match, tuple) else match
        candidates.append(phrase.strip().title())
    return candidates


def extract_theories_from_abstract(abstract: str) -> dict:
    """Kombiniert alle drei Methoden und gibt strukturiertes Ergebnis zurück."""
    known = extract_known_theories(abstract)
    candidates = extract_candidate_theories(abstract)
    generic = extract_generic_theories(abstract)

    # Kandidaten, die bereits als bekannte Theorie erfasst wurden, nicht doppelt zählen
    candidates_filtered = [
        c for c in candidates
        if not any(c.lower() in k.lower() or k.lower() in c.lower() for k in known)
    ]

    # Generische Treffer gegen 'known' und 'candidates' abgleichen, damit
    # nichts doppelt gezählt wird (z.B. "Stakeholder Theory" käme sonst
    # sowohl aus known_theories als auch aus generic_theories)
    already_found = known + candidates_filtered
    generic_filtered = []
    seen_lower = set()
    for g in generic:
        if any(g.lower() in af.lower() or af.lower() in g.lower() for af in already_found):
            continue
        if g.lower() in seen_lower:  # Duplikate innerhalb generic selbst raus
            continue
        seen_lower.add(g.lower())
        generic_filtered.append(g)

    return {
        "known_theories": known,
        "candidate_theories": candidates_filtered,
        "generic_theories": generic_filtered,  # separat sichtbar für Debugging/Filter
        "all_theories": known + candidates_filtered + generic_filtered,
        "theory_count": len(known) + len(candidates_filtered) + len(generic_filtered),
    }


# -----------------------------------------------------
# Zusatz-Check: Circular Economy / Sustainability Orientation
# -----------------------------------------------------
CIRCULAR_ECONOMY_KEYWORDS = [
    "circular economy", "closed-loop", "reuse", "recycling", "remanufactur",
    "cradle-to-cradle", "circularity", "resource loop", "industrial symbiosis"
]

SUSTAINABILITY_ORIENTATION_KEYWORDS = [
    "sustainability orientation", "sustainable orientation",
    "environmental orientation", "sustainability-oriented",
    "corporate sustainability", "sustainable development"
]


def check_topic_relevance(abstract: str) -> dict:
    """Prüft, ob der Abstract Circular-Economy- bzw. Sustainability-Orientation-
    Begriffe enthält."""
    if not abstract:
        return {"circular_economy": False, "sustainability_orientation": False}
    text = abstract.lower()
    return {
        "circular_economy": any(kw in text for kw in CIRCULAR_ECONOMY_KEYWORDS),
        "sustainability_orientation": any(kw in text for kw in SUSTAINABILITY_ORIENTATION_KEYWORDS),
    }


# -----------------------------------------------------
# Analyse einer ganzen Paper-Liste
# -----------------------------------------------------
def analyze_papers(papers: list) -> list:
    """Reichert jede Paper-Dict um Theorien- und Themen-Infos an."""
    enriched = []
    for paper in papers:
        abstract = paper.get("abstract", "")
        theory_result = extract_theories_from_abstract(abstract)
        topic_result = check_topic_relevance(abstract)

        enriched_paper = dict(paper)  # Kopie, Original nicht verändern
        enriched_paper.update(theory_result)
        enriched_paper.update(topic_result)
        enriched.append(enriched_paper)
    return enriched


def count_all_theories(enriched_papers: list) -> Counter:
    """Zählt, wie oft jede Theorie über alle Paper hinweg vorkommt."""
    counter = Counter()
    for paper in enriched_papers:
        for theory in paper.get("all_theories", []):
            counter[theory] += 1
    return counter
