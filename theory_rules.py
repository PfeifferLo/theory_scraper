"""
theory_rules.py
Regelbasierte Erkennung von Theorien in Paper-Abstracts – mit Fokus auf
INNOVATIVE / NEUARTIGE Theorien.

Kernideen dieser Version:
- Vier komplementäre Methoden (bekannte Liste, Signalphrasen, generische
  Erkennung, Innovations-Erkennung).
- HARTE FILTER gegen generische Nicht-Theorien wie "Systematic Approach",
  "Conceptual Approach", "Theoretical View" usw. – diese werden nie als
  Theorie gezählt, weder in known/candidate/generic noch in innovative.
- "Framework"/"Frameworks" ist überall ausgeschlossen.
- Singular/Plural werden zu einer Form normalisiert.
- Innovative Theorien werden separat ausgewiesen, mit einer
  Konfidenz zwischen 0 und 1, sodass sie im Dashboard gezielt
  hervorgehoben und gefiltert werden können.
"""

import re
from collections import Counter


# =========================================================
# 1. Bekannte Theorien
# =========================================================
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


# =========================================================
# 2. Singular/Plural-Normalisierung
# =========================================================
PLURAL_TO_SINGULAR_KEYWORDS = {
    "theories": "theory",
    "views": "view",
    "perspectives": "perspective",
    "approaches": "approach",
    "paradigms": "paradigm",
    "lenses": "lens",
}


def normalize_theory_name(name: str) -> str:
    if not name:
        return name
    words = name.split()
    if not words:
        return name
    last = words[-1]
    last_lower = last.lower()
    if last_lower in PLURAL_TO_SINGULAR_KEYWORDS:
        singular = PLURAL_TO_SINGULAR_KEYWORDS[last_lower]
        words[-1] = singular.capitalize()
    return " ".join(words)


def _make_known_theory_pattern(theory: str) -> re.Pattern:
    singular_to_plural = {v: k for k, v in PLURAL_TO_SINGULAR_KEYWORDS.items()}
    words = theory.split()
    last = words[-1]
    last_lower = last.lower()
    if last_lower in singular_to_plural:
        base = " ".join(words[:-1])
        plural = singular_to_plural[last_lower]
        prefix = re.escape(base + " ") if base else ""
        pattern = prefix + r"(?:" + re.escape(last) + "|" + re.escape(plural) + r")\b"
        return re.compile(pattern, re.IGNORECASE)
    return re.compile(re.escape(theory), re.IGNORECASE)


KNOWN_THEORY_PATTERNS = {
    theory: _make_known_theory_pattern(theory)
    for theory in KNOWN_THEORIES
}


# =========================================================
# 3. Blacklist generischer "Nicht-Theorien"
# =========================================================
# Alles hier drin ist zu unspezifisch, um als Theorie zu zählen. Wird an
# JEDER Extraktionsstelle geprüft und rausgeworfen (case-insensitive,
# nach Singular-Normalisierung verglichen).
GENERIC_THEORY_BLACKLIST = {
    # "Approach"-Kombinationen
    "systematic approach", "conceptual approach", "theoretical approach",
    "empirical approach", "analytical approach", "holistic approach",
    "integrated approach", "comprehensive approach", "traditional approach",
    "modern approach", "general approach", "novel approach", "new approach",
    "innovative approach", "practical approach", "qualitative approach",
    "quantitative approach", "mixed approach", "multi-method approach",
    "case study approach", "research approach", "different approach",
    "similar approach", "same approach", "our approach", "this approach",
    # "View"-Kombinationen
    "conceptual view", "theoretical view", "traditional view",
    "general view", "holistic view", "integrated view", "our view",
    "this view", "same view", "different view", "overall view",
    "broader view", "narrower view",
    # "Perspective"-Kombinationen
    "conceptual perspective", "theoretical perspective", "general perspective",
    "holistic perspective", "integrated perspective", "traditional perspective",
    "broader perspective", "narrower perspective", "different perspective",
    "similar perspective", "our perspective", "this perspective",
    "same perspective", "critical perspective", "comparative perspective",
    # "Theory"-Kombinationen (leer/generisch)
    "general theory", "grand theory", "middle-range theory", "our theory",
    "this theory", "same theory", "different theory", "existing theory",
    "current theory", "prior theory", "previous theory", "relevant theory",
    "underlying theory", "background theory",
    # "Paradigm"-Kombinationen
    "traditional paradigm", "dominant paradigm", "current paradigm",
    "existing paradigm", "prevailing paradigm", "same paradigm",
    "different paradigm", "our paradigm", "this paradigm",
    # "Lens"-Kombinationen
    "theoretical lens", "conceptual lens", "analytical lens",
    "different lens", "same lens", "this lens", "our lens",
}


def _is_blacklisted(name: str) -> bool:
    """True, wenn der (normalisierte) Name als generische Nicht-Theorie
    auf der Blacklist steht."""
    if not name:
        return True
    return name.lower().strip() in GENERIC_THEORY_BLACKLIST


# =========================================================
# 4. Stoppwörter und Modifikatoren
# =========================================================
# Wörter, die NIE Teil eines Theorienamens sein sollen -> beenden die
# Rückwärtssuche in der generischen Extraktion.
GENERIC_STOPWORDS = {
    # Artikel, Pronomen, Demonstrativa
    "a", "an", "the", "this", "that", "these", "those", "our", "their",
    "its", "his", "her", "my", "your", "one", "such", "any", "each",
    "every", "some", "no",
    # Vergleichende / relativierende Adjektive
    "current", "existing", "prior", "previous", "related", "relevant",
    "respective", "above", "following", "same", "given", "certain",
    "particular", "different", "similar", "various", "several", "many",
    "few", "main", "key", "core", "central", "important", "significant",
    "appropriate", "proper", "suitable", "adequate", "effective",
    "efficient", "successful", "overall", "broader", "narrower",
    # Personalpronomen / Verben
    "we", "they", "it", "he", "she", "i", "you", "who", "which",
    "is", "are", "was", "were", "be", "been", "being",
    # Konjunktionen / Präpositionen
    "and", "or", "but", "of", "in", "on", "for", "to", "from",
    "with", "as", "by", "at", "into", "through", "between", "among",
    # Verben rund um "verwenden"
    "consider", "considering", "considered", "use", "using", "used",
    "apply", "applying", "applied", "provide", "providing",
    # Meta-Vokabular
    "paper", "study", "research", "article", "analysis", "review",
    "literature", "context", "findings", "results", "authors",
}

# Adjektive, die NUR Neuheit ausdrücken – nicht Teil eines Namens.
NOVELTY_ONLY_WORDS = {
    "new", "novel", "emerging", "innovative", "original", "unprecedented",
    "groundbreaking", "pioneering", "nascent", "alternative", "fresh",
    "revised", "updated", "modified", "extended",
}

# Adjektive, die für sich allein KEINEN Theorienamen ergeben.
# "Systematic Approach" allein ist keine Theorie – nur wenn davor noch
# ein inhaltlicher Begriff steht (z.B. "Stakeholder Systematic Approach")
# könnte es Sinn ergeben, aber wir bleiben streng.
GENERIC_MODIFIERS = {
    "systematic", "conceptual", "theoretical", "empirical", "analytical",
    "holistic", "integrated", "comprehensive", "traditional", "modern",
    "general", "practical", "qualitative", "quantitative", "mixed",
    "critical", "comparative", "descriptive", "exploratory", "explanatory",
    "predictive", "normative", "positive", "formal", "informal",
    "overall", "broader", "narrower", "dominant", "prevailing",
    "underlying", "background", "grand",
}

# Theorie-Schlüsselwörter
THEORY_KEYWORDS = (
    r"(theories|theory|views|view|perspectives|perspective|"
    r"approaches|approach|paradigms|paradigm|lenses|lens)"
)

GENERIC_THEORY_KEYWORD_RE = re.compile(
    r"^(theories|theory|views|view|perspectives|perspective|"
    r"paradigms|paradigm|approaches|approach|lenses|lens)$",
    re.IGNORECASE,
)


# =========================================================
# 5. Signalphrasen ("based on ...", "grounded in ...")
# =========================================================
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
    r"anchored in(?: the)?",
    r"in line with",
]

SIGNAL_PATTERN = re.compile(
    r"(?:" + "|".join(SIGNAL_PHRASES) + r")\s+"
    r"((?:[A-Za-z][\w\-]*\s+){0,6}" + THEORY_KEYWORDS + r")",
    re.IGNORECASE
)

_TOKEN_RE = re.compile(r"[A-Za-z][\w\-]*|[.,;:()\[\]]")


# =========================================================
# 6. Validierung eines Theorienamens
# =========================================================
def _has_content_word(name: str) -> bool:
    """
    Prüft, ob ein extrahierter Name mindestens ein wirklich inhaltliches
    Wort enthält. Wörter, die nur Neuheit oder generische Methodik
    ausdrücken, zählen NICHT als Content Word.
    """
    words = name.split()
    if len(words) < 2:
        return False
    # das letzte Wort ist immer das Schlüsselwort (theory/view/...)
    prefix_words = [w.lower() for w in words[:-1]]
    non_generic = [
        w for w in prefix_words
        if w not in NOVELTY_ONLY_WORDS
        and w not in GENERIC_MODIFIERS
        and w not in GENERIC_STOPWORDS
    ]
    return len(non_generic) >= 1


def _is_valid_theory_name(name: str) -> bool:
    """
    Zentraler Validitätscheck: entfernt Framework-Treffer, Blacklist-
    Einträge und Namen ohne inhaltliches Wort. Wird in ALLEN vier
    Extraktions-Pfaden angewendet.
    """
    if not name:
        return False
    if "framework" in name.lower():
        return False
    if _is_blacklisted(name):
        return False
    if not _has_content_word(name):
        return False
    return True


def _drop_invalid(names: list) -> list:
    """Filtert eine Namensliste auf gültige Theorien."""
    return [n for n in names if _is_valid_theory_name(n)]


# =========================================================
# 7. Methode 1: Bekannte Theorien
# =========================================================
def extract_known_theories(abstract: str) -> list:
    if not abstract:
        return []
    found = []
    for theory, pattern in KNOWN_THEORY_PATTERNS.items():
        if pattern.search(abstract):
            found.append(theory)

    # Kürzere Treffer aussortieren, wenn sie in einem längeren enthalten sind
    filtered = []
    for theory in found:
        is_substring_of_other = any(
            theory.lower() != other.lower() and theory.lower() in other.lower()
            for other in found
        )
        if not is_substring_of_other:
            filtered.append(theory)
    return _drop_invalid(filtered)


# =========================================================
# 8. Methode 2: Signalphrasen-Kandidaten
# =========================================================
def extract_candidate_theories(abstract: str) -> list:
    if not abstract:
        return []
    matches = SIGNAL_PATTERN.findall(abstract)
    candidates = []
    for match in matches:
        phrase = match[0] if isinstance(match, tuple) else match
        name = normalize_theory_name(phrase.strip().title())
        candidates.append(name)
    return _drop_invalid(candidates)


# =========================================================
# 9. Methode 3: Generische Erkennung "<Begriff> + Keyword"
# =========================================================
def extract_generic_theories(abstract: str, max_words: int = 3) -> list:
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

        if words:
            phrase = " ".join(words + [tok])
            name = normalize_theory_name(phrase.title())
            found.append(name)

    return _drop_invalid(found)


# =========================================================
# 10. Methode 4: Innovations-Erkennung
# =========================================================
_NOVELTY_ADJ = (
    r"(?:new|novel|emerging|innovative|original|unprecedented|"
    r"groundbreaking|pioneering|nascent|alternative|fresh)"
)

_NOVELTY_VERB = (
    r"(?:propose[sd]?|develop(?:s|ed)?|introduc(?:e|es|ed)|"
    r"advanc(?:e|es|ed)|put(?:s)? forward|formulat(?:e|es|ed)|"
    r"construct(?:s|ed)?|coin(?:s|ed)?|articulat(?:e|es|ed)|"
    r"present(?:s|ed)?|offer(?:s|ed)?)"
)

_THEORY_KEYWORD_NAMED = (
    r"(?P<kw>theories|theory|views|view|perspectives|perspective|"
    r"approaches|approach|paradigms|paradigm|lenses|lens)"
)

PATTERN_NOVELTY_ADJ = re.compile(
    r"\b(?:a|an)?\s*" + _NOVELTY_ADJ + r"\s+"
    r"(?P<prefix>(?:[A-Za-z][\w\-]*\s+){0,4})" + _THEORY_KEYWORD_NAMED +
    r"(?:\s+of\s+(?P<of>[A-Za-z][\w\-]*(?:[\s\-][A-Za-z][\w\-]*){0,6}))?"
    r"(?=[\s,.;:]|$)",
    re.IGNORECASE
)

PATTERN_NOVELTY_VERB = re.compile(
    r"\b" + _NOVELTY_VERB + r"\s+(?:a|an)?\s*" + _NOVELTY_ADJ + r"?\s*"
    r"(?P<prefix>(?:[A-Za-z][\w\-]*\s+){0,6})" + _THEORY_KEYWORD_NAMED +
    r"(?:\s+of\s+(?P<of>[A-Za-z][\w\-]*(?:[\s\-][A-Za-z][\w\-]*){0,6}))?"
    r"(?=[\s,.;:]|$)",
    re.IGNORECASE
)

PATTERN_TOWARD_THEORY_OF = re.compile(
    r"\btoward(?:s)?\s+a\s+(?:new\s+|novel\s+)?theor(?:y|ies)\s+of\s+"
    r"(?P<of>[A-Za-z][\w\-]*(?:[\s\-][A-Za-z][\w\-]*){0,6})(?=[\s,.;:]|$)",
    re.IGNORECASE
)

GENERAL_NOVELTY_SIGNAL_PATTERNS = [
    re.compile(r"\btheory\s+building\b", re.IGNORECASE),
    re.compile(r"\btheory\s+development\b", re.IGNORECASE),
    re.compile(r"\btheoretical\s+contribution\w*\b", re.IGNORECASE),
    re.compile(r"\bextend(?:s|ing)?\s+.{0,40}\btheory\b", re.IGNORECASE),
    re.compile(r"\breconceptualiz\w*\b", re.IGNORECASE),
    re.compile(r"\bparadigm\s+shift\b", re.IGNORECASE),
    re.compile(r"\bnew\s+(?:construct|typology|taxonomy)\b", re.IGNORECASE),
    re.compile(r"\bnovel\s+conceptualization\b", re.IGNORECASE),
]


def _clean_of_part(of_part: str) -> str:
    """Räumt eine "of X"-Ergänzung auf: entfernt trailing Stopwörter,
    Satzzeichen und leere Wörter."""
    if not of_part:
        return ""
    of_part = of_part.strip().strip(",.;:")
    words = of_part.split()
    # Trailing Stopwörter abschneiden
    while words and words[-1].lower() in GENERIC_STOPWORDS:
        words.pop()
    return " ".join(words).strip()


def _build_theory_name(prefix: str, kw: str, of_part: str):
    """Baut aus Prefix + Keyword + optionalem 'of X' einen Namen."""
    prefix = (prefix or "").strip()
    of_part = _clean_of_part(of_part or "")
    kw_singular = PLURAL_TO_SINGULAR_KEYWORDS.get(kw.lower(), kw.lower())

    # Prefix von generischen Modifikatoren am Anfang befreien
    prefix_words = prefix.split()
    while prefix_words and (
        prefix_words[0].lower() in NOVELTY_ONLY_WORDS
        or prefix_words[0].lower() in GENERIC_STOPWORDS
    ):
        prefix_words.pop(0)
    prefix = " ".join(prefix_words)

    if prefix and of_part:
        # z.B. "sustainability theory of firm behavior"
        name = f"{prefix} {kw_singular} of {of_part}"
    elif prefix:
        name = f"{prefix} {kw_singular}"
    elif of_part:
        name = f"{kw_singular} of {of_part}"
    else:
        return None

    name = normalize_theory_name(name.title())
    if not _is_valid_theory_name(name):
        return None
    return name


def _extract_innovative_theories_detailed(abstract: str):
    """Liefert (Namensliste, Anzahl unbenannter Innovations-Treffer)."""
    if not abstract:
        return [], 0

    names = []
    unnamed_count = 0

    for pattern in (PATTERN_NOVELTY_ADJ, PATTERN_NOVELTY_VERB):
        for m in pattern.finditer(abstract):
            name = _build_theory_name(
                m.group("prefix"),
                m.group("kw"),
                m.groupdict().get("of"),
            )
            if name:
                names.append(name)
            else:
                unnamed_count += 1

    for m in PATTERN_TOWARD_THEORY_OF.finditer(abstract):
        name = _build_theory_name("", "theory", m.group("of"))
        if name:
            names.append(name)
        else:
            unnamed_count += 1

    # Duplikate case-insensitive entfernen, Reihenfolge behalten
    seen = set()
    deduped = []
    for name in names:
        key = name.lower()
        if key not in seen:
            seen.add(key)
            deduped.append(name)
    return deduped, unnamed_count


def extract_innovative_theories(abstract: str) -> list:
    names, _ = _extract_innovative_theories_detailed(abstract)
    return names


def general_novelty_signal_count(abstract: str) -> int:
    if not abstract:
        return 0
    return sum(1 for p in GENERAL_NOVELTY_SIGNAL_PATTERNS if p.search(abstract))


def find_novelty_snippets(abstract: str, context: int = 60) -> list:
    """
    Gibt die konkreten Textstellen zurück, an denen Innovations-Signale
    im Abstract stehen (für UI-Highlights im Dashboard).
    """
    if not abstract:
        return []
    hits = []
    for pattern in (PATTERN_NOVELTY_ADJ, PATTERN_NOVELTY_VERB, PATTERN_TOWARD_THEORY_OF):
        for m in pattern.finditer(abstract):
            start = max(0, m.start() - context)
            end = min(len(abstract), m.end() + context)
            hits.append({
                "match": abstract[m.start():m.end()],
                "snippet": abstract[start:end].strip(),
            })
    return hits


# =========================================================
# 11. Gesamt-Extraktion pro Abstract
# =========================================================
def extract_theories_from_abstract(abstract: str) -> dict:
    known = extract_known_theories(abstract)
    candidates = extract_candidate_theories(abstract)
    generic = extract_generic_theories(abstract)
    innovative, unnamed_innovative_count = _extract_innovative_theories_detailed(abstract)
    novelty_signals = general_novelty_signal_count(abstract)

    # Kandidaten, die schon als bekannt erfasst sind, nicht doppelt zählen
    candidates_filtered = [
        c for c in candidates
        if not any(c.lower() in k.lower() or k.lower() in c.lower() for k in known)
    ]

    # Generische Treffer gegen known + candidates abgleichen
    already_found = known + candidates_filtered
    generic_filtered = []
    seen_lower = set()
    for g in generic:
        if any(g.lower() in af.lower() or af.lower() in g.lower() for af in already_found):
            continue
        if g.lower() in seen_lower:
            continue
        seen_lower.add(g.lower())
        generic_filtered.append(g)

    # Neu ausgewiesene "emerging candidates": Signalphrase-Kandidaten +
    # generische Treffer, die NICHT auf der bekannten Liste stehen.
    emerging_candidates = candidates_filtered + generic_filtered

    all_theories = known + emerging_candidates

    # Innovations-Konfidenz zwischen 0 und 1:
    # - jede benannte innovative Theorie: hoher Beitrag
    # - unbenannte Innovations-Treffer: mittlerer Beitrag
    # - generelle Innovations-Signale: kleiner Beitrag
    raw_score = (
        3 * len(innovative)
        + 2 * unnamed_innovative_count
        + 1 * novelty_signals
    )
    # 6 Punkte = maximale Konfidenz (grober Kalibrierungswert)
    innovation_confidence = min(1.0, raw_score / 6.0)

    return {
        "known_theories": known,
        "candidate_theories": candidates_filtered,
        "generic_theories": generic_filtered,
        "emerging_candidates": emerging_candidates,   # neu, unbekannt aber sauber
        "innovative_theories": innovative,            # explizit als neu markiert
        "all_theories": all_theories,
        "theory_count": len(all_theories),
        "has_innovative_theory": len(innovative) > 0 or unnamed_innovative_count > 0,
        "unnamed_innovative_count": unnamed_innovative_count,
        "novelty_signal_count": novelty_signals,
        "theory_innovation_score": raw_score,
        "innovation_confidence": round(innovation_confidence, 3),
    }


# =========================================================
# 12. Themenerkennung
# =========================================================
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
    if not abstract:
        return {"circular_economy": False, "sustainability_orientation": False}
    text = abstract.lower()
    return {
        "circular_economy": any(kw in text for kw in CIRCULAR_ECONOMY_KEYWORDS),
        "sustainability_orientation": any(kw in text for kw in SUSTAINABILITY_ORIENTATION_KEYWORDS),
    }


# =========================================================
# 13. Batch-Analyse
# =========================================================
def analyze_papers(papers: list) -> list:
    enriched = []
    for paper in papers:
        abstract = paper.get("abstract", "")
        theory_result = extract_theories_from_abstract(abstract)
        topic_result = check_topic_relevance(abstract)

        enriched_paper = dict(paper)
        enriched_paper.update(theory_result)
        enriched_paper.update(topic_result)
        enriched_paper["novelty_snippets"] = find_novelty_snippets(abstract)
        enriched.append(enriched_paper)
    return enriched


def filter_innovative_papers(enriched_papers: list, min_confidence: float = 0.2) -> list:
    """Filtert nach Innovations-Konfidenz und sortiert absteigend."""
    candidates = [
        p for p in enriched_papers
        if p.get("innovation_confidence", 0) >= min_confidence
    ]
    candidates.sort(key=lambda p: p.get("innovation_confidence", 0), reverse=True)
    return candidates


def count_all_theories(enriched_papers: list) -> Counter:
    counter = Counter()
    for paper in enriched_papers:
        for theory in paper.get("all_theories", []):
            counter[theory] += 1
    return counter


def count_innovative_theories(enriched_papers: list) -> Counter:
    counter = Counter()
    for paper in enriched_papers:
        for theory in paper.get("innovative_theories", []):
            counter[theory] += 1
    return counter


def count_emerging_candidates(enriched_papers: list) -> Counter:
    """Zählt Theorien, die NICHT auf der bekannten Liste stehen und nicht
    als generisch verworfen wurden – die 'Neuentdeckungen' abseits von
    Novelty-Sprache."""
    counter = Counter()
    for paper in enriched_papers:
        for theory in paper.get("emerging_candidates", []):
            counter[theory] += 1
    return counter
