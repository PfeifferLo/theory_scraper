"""
theory_rules.py
Regelbasierte Erkennung von Theorien in Paper-Abstracts – mit Fokus auf
INNOVATIVE / NEUARTIGE Theorien.

Vier Methoden werden kombiniert:
1. Feste Liste bekannter Theorien (Dictionary-Matching per Regex)
   -> dient v.a. als Vergleichsbasis ("ist das eine bereits etablierte
      Theorie?") und zum Herausfiltern von Dopplungen.
2. Signalwörter, die typischerweise vor einer Theoriennennung stehen
   (z.B. "based on", "drawing on", "grounded in") -> Kandidaten-Extraktion
3. Generische Erkennung: jedes Wort/jede kurze Wortfolge direkt vor einem
   Theorie-Schlüsselwort ("theory", "view", ...), unabhängig davon, ob die
   Theorie in KNOWN_THEORIES steht.
4. NEU – Innovations-Erkennung (Kernstück dieses Moduls): erkennt gezielt
   Textstellen, an denen Autor:innen eine Theorie explizit als NEU/NOVEL
   vorstellen bzw. selbst entwickeln/vorschlagen/einführen, z.B.:
     - "we propose a new theory of resource orchestration"
     - "this paper develops a novel theory of circular supply chains"
     - "toward a theory of stakeholder co-creation"
   Im Gegensatz zu den Methoden 1-3, die JEDE Theorie-Erwähnung zählen
   (auch reine Zitate bestehender Theorien wie "based on stakeholder
   theory"), liefert Methode 4 NUR Theorien, die im Text als neu/eigen-
   ständig entwickelt gekennzeichnet sind, und versucht dabei möglichst
   den konkreten (benannten) Theorienamen zu rekonstruieren statt nur das
   bloße Wort "Theory" zurückzugeben.

WICHTIG: "Framework"/"Frameworks" wird an keiner Stelle mehr als
Theorie-Schlüsselwort erkannt, und jeder Treffer, der den Begriff
"Framework" irgendwo im erkannten Text enthält, wird am Ende
konsequent aus allen Ergebnislisten entfernt (siehe _drop_framework_hits).

Singular/Plural (z.B. "Theory" vs. "Theories") werden überall auf die
Singular-Form normalisiert, damit z.B. "Legitimacy Theory" und
"Legitimacy Theories" als EIN Eintrag gezählt werden.
"""

import re
from collections import Counter


# -----------------------------------------------------
# 1. Bekannte Theorien (feste Liste)
# -----------------------------------------------------
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

# -----------------------------------------------------
# 1b. Singular/Plural-Normalisierung
# -----------------------------------------------------
# Mapping der Theorie-Schlüsselwörter: Plural -> Singular.
# "framework(s)" wurde bewusst ENTFERNT: Framework-Treffer sollen laut
# Anforderung generell nicht mehr im Ergebnis erscheinen (siehe unten).
PLURAL_TO_SINGULAR_KEYWORDS = {
    "theories": "theory",
    "views": "view",
    "perspectives": "perspective",
    "approaches": "approach",
    "paradigms": "paradigm",
}


def normalize_theory_name(name: str) -> str:
    """Vereinheitlicht Singular/Plural am Ende eines Theorienamens.
    'Legitimacy Theories' -> 'Legitimacy Theory'
    'Stakeholder Views'   -> 'Stakeholder View'
    Lässt alles andere unverändert.
    """
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
    """Erstellt für eine bekannte Theorie ein Regex-Pattern, das sowohl
    die Singular- als auch die Pluralform des letzten Wortes erkennt
    (z.B. matcht 'Legitimacy Theory' auch 'Legitimacy Theories' im Text)."""
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


# Regex-Muster vorkompilieren (schneller bei vielen Abstracts)
KNOWN_THEORY_PATTERNS = {
    theory: _make_known_theory_pattern(theory)
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

# Wörter, die am Ende einer Theoriebezeichnung stehen (Singular + Plural).
# "model" bleibt bewusst ausgeschlossen (zu viele Fehltreffer wie
# "regression model", "conceptual model").
# "framework"/"frameworks" wurde ENTFERNT: Framework-Treffer sollen laut
# Anforderung generell nicht mehr im Ergebnis erscheinen.
THEORY_KEYWORDS = (
    r"(theories|theory|views|view|perspectives|perspective|"
    r"approaches|approach|paradigms|paradigm)"
)

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
#    solange direkt "theory/view/..." danach steht.
# -----------------------------------------------------

# Wörter, die NICHT Teil eines Theorienamens sein dürfen -> Abbruchkriterium
# beim Rückwärtslaufen. Bewusst konservativ gehalten, um False Positives
# wie "This Theory" oder "Our Theory" zu vermeiden.
GENERIC_STOPWORDS = {
    "a", "an", "the", "this", "that", "these", "those", "our", "their",
    "its", "his", "her", "my", "your", "one", "such", "any", "each",
    "every", "some", "no", "current", "existing", "prior",
    "previous", "related", "relevant", "respective", "above",
    "following", "same", "given", "certain", "particular",
    "we", "they", "it", "he", "she", "i", "you", "who", "which",
    "is", "are", "was", "were", "be", "been", "being",
    "and", "or", "but", "of", "in", "on", "for", "to", "from",
    "with", "as", "by", "at", "into", "consider", "considering",
    "considered", "use", "using", "used", "apply", "applying",
    "applied", "provide", "providing", "paper", "study", "research",
}

# Theorie-Schlüsselwörter als eigenständige Tokens (Singular + Plural).
# "model" und "framework"/"frameworks" bleiben ausgeschlossen.
GENERIC_THEORY_KEYWORD_RE = re.compile(
    r"^(theories|theory|views|view|perspectives|perspective|"
    r"paradigms|paradigm|approaches|approach)$",
    re.IGNORECASE,
)

# Tokenizer: Wörter und Satzzeichen getrennt erfassen, damit wir am
# Komma/Punkt sauber abbrechen können (z.B. "..., framing theory, ...")
_TOKEN_RE = re.compile(r"[A-Za-z][\w\-]*|[.,;:()\[\]]")

# Adjektive, die reine Neuheit ausdrücken, aber ohne weiteren Kontext
# KEINEN eigenständigen Theorienamen ergeben (z.B. "a new theory" allein
# ist kein Name). Phrasen, die NUR aus diesen Wörtern + Schlüsselwort
# bestehen, werden aus generic/candidate_theories entfernt, weil sie
# nichts Substanzielles beitragen - der eigentliche Neuheits-Fund läuft
# stattdessen gezielt über extract_innovative_theories() (Abschnitt 4).
NOVELTY_ONLY_WORDS = {
    "new", "novel", "emerging", "innovative", "original", "unprecedented",
    "groundbreaking", "pioneering", "nascent", "alternative",
}


def _is_bare_novelty_phrase(name: str) -> bool:
    """True, wenn ein extrahierter Name nur aus Neuheits-Adjektiven + dem
    Theorie-Schlüsselwort besteht (z.B. 'New Theory', 'Novel Perspective')
    - also keinen eigenen inhaltlichen Namen liefert."""
    words = name.split()
    if len(words) < 2:
        return False
    prefix_words = words[:-1]
    return all(w.lower() in NOVELTY_ONLY_WORDS for w in prefix_words)


def extract_generic_theories(abstract: str, max_words: int = 3) -> list:
    """
    Läuft von jedem Theorie-Schlüsselwort ("theory"/"theories", "view"/
    "views", ...) rückwärts durch die vorangehenden Wörter und sammelt sie,
    solange sie keine Satzzeichen oder Füllwörter (GENERIC_STOPWORDS) sind.
    Dadurch werden auch Theorien erfasst, die nicht in KNOWN_THEORIES
    stehen (z.B. "Game Theory", "Equity Theory"). Ergebnis wird auf
    Singular normalisiert (normalize_theory_name). Bare Neuheits-Phrasen
    ohne inhaltlichen Namen (z.B. "New Theory") werden herausgefiltert.
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
            name = normalize_theory_name(phrase.title())
            if not _is_bare_novelty_phrase(name):
                found.append(name)

    return found


# -----------------------------------------------------
# 4. NEU: gezielte Erkennung INNOVATIVER / NEUARTIGER Theorien
# -----------------------------------------------------
# Ziel dieses Abschnitts: nicht jede Theorie-Erwähnung zählt, sondern nur
# solche Stellen, an denen der Text explizit signalisiert, dass hier eine
# NEUE bzw. NOVEL Theorie vorgeschlagen, entwickelt, eingeführt oder
# benannt wird - im Unterschied zu Papern, die eine bestehende Theorie nur
# als Erklärungsrahmen für ihre Hypothesen benutzen.

# Adjektive, die Neuheit/Innovation direkt vor einem Theorienamen anzeigen.
_NOVELTY_ADJ = (
    r"(?:new|novel|emerging|innovative|original|unprecedented|"
    r"groundbreaking|pioneering|nascent|alternative)"
)

# Verben, mit denen Autor:innen typischerweise ankündigen, dass sie selbst
# eine Theorie entwickeln/vorschlagen/einführen (statt nur zu verwenden).
_NOVELTY_VERB = (
    r"(?:propose[sd]?|develop(?:s|ed)?|introduc(?:e|es|ed)|"
    r"advanc(?:e|es|ed)|put(?:s)? forward|formulat(?:e|es|ed)|"
    r"construct(?:s|ed)?|coin(?:s|ed)?|articulat(?:e|es|ed))"
)

# Theorie-Schlüsselwort als BENANNTE Gruppe (für die Namensrekonstruktion
# in Abschnitt 4 gebraucht; inhaltlich identisch zu THEORY_KEYWORDS oben).
_THEORY_KEYWORD_NAMED = (
    r"(?P<kw>theories|theory|views|view|perspectives|perspective|"
    r"approaches|approach|paradigms|paradigm)"
)

# Muster A: Neuheits-Adjektiv direkt vor einer Theoriebezeichnung, optional
# gefolgt von "of <Thema>" (liefert den eigentlichen Namen der Theorie).
# z.B. "a novel stakeholder theory", "a new theory of resource orchestration"
PATTERN_NOVELTY_ADJ = re.compile(
    r"\b(?:a|an)?\s*" + _NOVELTY_ADJ + r"\s+"
    r"(?P<prefix>(?:[A-Za-z][\w\-]*\s+){0,4})" + _THEORY_KEYWORD_NAMED +
    r"(?:\s+of\s+(?P<of>[A-Za-z][\w\-]*(?:\s+[A-Za-z][\w\-]*){0,5}))?"
    r"(?=[\s,.;:]|$)",
    re.IGNORECASE
)

# Muster B: "wir schlagen/entwickeln/führen ein (neues) ... Theorie ein"
# z.B. "we propose a new theory of stakeholder engagement",
#      "this paper develops a novel theory of legitimacy"
PATTERN_NOVELTY_VERB = re.compile(
    r"\b" + _NOVELTY_VERB + r"\s+(?:a|an)?\s*" + _NOVELTY_ADJ + r"?\s*"
    r"(?P<prefix>(?:[A-Za-z][\w\-]*\s+){0,6})" + _THEORY_KEYWORD_NAMED +
    r"(?:\s+of\s+(?P<of>[A-Za-z][\w\-]*(?:\s+[A-Za-z][\w\-]*){0,5}))?"
    r"(?=[\s,.;:]|$)",
    re.IGNORECASE
)

# Muster C: "toward(s) a (new) theory of X" - klassische Formulierung für
# die Ankündigung einer neuen Theorie.
PATTERN_TOWARD_THEORY_OF = re.compile(
    r"\btoward(?:s)?\s+a\s+(?:new\s+|novel\s+)?theor(?:y|ies)\s+of\s+"
    r"(?P<of>[A-Za-z][\w\-]*(?:\s+[A-Za-z][\w\-]*){0,5})(?=[\s,.;:]|$)",
    re.IGNORECASE
)

# Generelle Innovations-/Theoriebildungs-Signale, die NICHT zwingend einen
# konkreten Theorienamen liefern, aber trotzdem stark auf einen
# theoretischen Neuheitsanspruch hindeuten (fließt nur in den Score ein,
# nicht in die Namensliste).
GENERAL_NOVELTY_SIGNAL_PATTERNS = [
    re.compile(r"\btheory\s+building\b", re.IGNORECASE),
    re.compile(r"\btheory\s+development\b", re.IGNORECASE),
    re.compile(r"\btheoretical\s+contribution\w*\b", re.IGNORECASE),
    re.compile(r"\bextend(?:s|ing)?\s+.{0,40}\btheory\b", re.IGNORECASE),
    re.compile(r"\breconceptualiz\w*\b", re.IGNORECASE),
    re.compile(r"\bparadigm\s+shift\b", re.IGNORECASE),
    re.compile(r"\bnew\s+(?:construct|typology|taxonomy)\b", re.IGNORECASE),
]


def _build_theory_name(prefix: str, kw: str, of_part: str):
    """Baut aus den Teilen eines Innovations-Treffers (Muster A/B/C) einen
    lesbaren Theorienamen. Bevorzugt den direkten Namensteil vor dem
    Schlüsselwort (prefix, z.B. 'resource orchestration' in 'a novel
    resource orchestration theory'); falls keiner vorhanden ist, wird der
    Name aus der 'of X'-Ergänzung gebildet (z.B. 'theory of resource
    orchestration' -> 'Resource Orchestration Theory'). Liefert None,
    wenn kein inhaltlicher Name rekonstruierbar ist (z.B. nur 'a novel
    theory' ohne jede weitere Angabe) - solche Treffer sind zu unspezifisch
    für einen Namenseintrag, zählen aber trotzdem in den Score."""
    prefix = (prefix or "").strip()
    of_part = (of_part or "").strip().strip(",.;:")
    kw_singular = PLURAL_TO_SINGULAR_KEYWORDS.get(kw.lower(), kw.lower())

    if prefix:
        name = f"{prefix} {kw_singular}"
    elif of_part:
        name = f"{of_part} {kw_singular}"
    else:
        return None

    name = normalize_theory_name(name.title())
    if _is_bare_novelty_phrase(name):
        return None
    return name


def _extract_innovative_theories_detailed(abstract: str):
    """Interne Variante von extract_innovative_theories(), die zusätzlich
    zurückgibt, wie viele Treffer zwar ein Innovations-Signal enthielten,
    aber KEINEN rekonstruierbaren Namen hatten (z.B. 'a novel theory' ohne
    weitere Angabe). Diese unbenannten Treffer fließen trotzdem in den
    theory_innovation_score ein."""
    if not abstract:
        return [], 0

    names = []
    unnamed_count = 0

    for pattern in (PATTERN_NOVELTY_ADJ, PATTERN_NOVELTY_VERB):
        for m in pattern.finditer(abstract):
            name = _build_theory_name(m.group("prefix"), m.group("kw"), m.groupdict().get("of"))
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

    names = _drop_framework_hits(names)

    # Duplikate entfernen (case-insensitive), Reihenfolge beibehalten
    seen = set()
    deduped = []
    for name in names:
        key = name.lower()
        if key not in seen:
            seen.add(key)
            deduped.append(name)

    return deduped, unnamed_count


def extract_innovative_theories(abstract: str) -> list:
    """
    Kernstück der Innovations-Erkennung: liefert nur Theoriebezeichnungen,
    die im Text erkennbar als NEU / SELBST ENTWICKELT / NOVEL markiert sind
    (statt nur als bestehende Theorie zitiert zu werden), z.B.
    "Resource Orchestration Theory" aus "we propose a new theory of
    resource orchestration". "Framework"-Treffer werden konsequent entfernt.
    """
    names, _unnamed_count = _extract_innovative_theories_detailed(abstract)
    return names


def general_novelty_signal_count(abstract: str) -> int:
    """Zählt zusätzliche, nicht namensgebundene Innovations-/Theoriebildungs-
    Signale im Abstract (z.B. 'theory building', 'paradigm shift'). Fließt
    in den theory_innovation_score ein, taucht aber nicht als eigener
    Theorienname auf."""
    if not abstract:
        return 0
    return sum(1 for p in GENERAL_NOVELTY_SIGNAL_PATTERNS if p.search(abstract))


# -----------------------------------------------------
# Framework-Filter (gilt global für ALLE Ergebnislisten)
# -----------------------------------------------------
def _contains_framework(name: str) -> bool:
    """True, wenn 'framework' irgendwo im erkannten Text vorkommt - auch
    dann, wenn 'framework' nicht das eigentliche Theorie-Schlüsselwort war
    (z.B. als Teil der davorstehenden Wörter, wie in 'Conceptual Framework
    Approach'). Damit werden ALLE Framework-bezogenen Treffer zuverlässig
    ausgeschlossen, wie gewünscht."""
    return "framework" in name.lower()


def _drop_framework_hits(names: list) -> list:
    """Entfernt aus einer Liste von Theorienamen alle Einträge, die
    'framework' enthalten."""
    return [n for n in names if not _contains_framework(n)]


# -----------------------------------------------------
# Extraktion für einen einzelnen Abstract
# -----------------------------------------------------
def extract_known_theories(abstract: str) -> list:
    """Sucht nach Treffern aus der festen Theorien-Liste (Singular ODER
    Plural im Text). Ist eine Theorie Teilstring einer anderen gefundenen
    Theorie (z.B. 'Resource-Based View' in 'Natural Resource-Based View'),
    wird nur die spezifischere (längere) behalten."""
    if not abstract:
        return []
    found = []
    for theory, pattern in KNOWN_THEORY_PATTERNS.items():
        if pattern.search(abstract):
            found.append(theory)  # kanonischer Name bleibt Singular

    # Kürzere Treffer entfernen, wenn sie in einem längeren enthalten sind
    filtered = []
    for theory in found:
        is_substring_of_other = any(
            theory.lower() != other.lower() and theory.lower() in other.lower()
            for other in found
        )
        if not is_substring_of_other:
            filtered.append(theory)
    return _drop_framework_hits(filtered)


def extract_candidate_theories(abstract: str) -> list:
    """Sucht nach Signalwort + Theorie-Muster, um auch unbekannte/neue
    Theorienbezeichnungen zu erfassen, die nicht in KNOWN_THEORIES stehen.
    Ergebnis wird auf Singular normalisiert. Bare Neuheits-Phrasen ohne
    inhaltlichen Namen (z.B. 'New Theory') werden herausgefiltert."""
    if not abstract:
        return []
    matches = SIGNAL_PATTERN.findall(abstract)
    candidates = []
    for match in matches:
        phrase = match[0] if isinstance(match, tuple) else match
        name = normalize_theory_name(phrase.strip().title())
        if not _is_bare_novelty_phrase(name):
            candidates.append(name)
    return _drop_framework_hits(candidates)


def extract_theories_from_abstract(abstract: str) -> dict:
    """Kombiniert alle vier Methoden und gibt strukturiertes Ergebnis zurück.
    Alle Namen sind bereits auf Singular normalisiert, Duplikate (auch über
    Singular/Plural hinweg) werden herausgefiltert, und JEDER Treffer mit
    'Framework' wurde bereits entfernt.

    Neu: 'innovative_theories' enthält nur die Theorienamen, die im Text
    explizit als neu/novel/selbst entwickelt markiert sind - das ist die
    gezielte Antwort auf die Frage "welche neuen/innovativen Theorien gibt
    es in diesem Paper?". 'has_innovative_theory' und
    'theory_innovation_score' erlauben, danach zu filtern bzw. zu ranken.
    """
    known = extract_known_theories(abstract)
    candidates = extract_candidate_theories(abstract)
    generic = _drop_framework_hits(extract_generic_theories(abstract))
    innovative, unnamed_innovative_count = _extract_innovative_theories_detailed(abstract)

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

    all_theories = known + candidates_filtered + generic_filtered

    # Innovations-Score: jede gefundene, benannte innovative Theorie zählt
    # 3 Punkte; unbenannte Innovations-Treffer (z.B. "a novel theory" ohne
    # weitere Angabe) und generelle Neuheits-/Theoriebildungssignale
    # (z.B. "theory building") zählen je 1 Punkt.
    innovation_score = (
        3 * len(innovative)
        + unnamed_innovative_count
        + general_novelty_signal_count(abstract)
    )

    return {
        "known_theories": known,
        "candidate_theories": candidates_filtered,
        "generic_theories": generic_filtered,  # separat sichtbar für Debugging/Filter
        "innovative_theories": innovative,      # NEU: gezielt neue/innovative Theorien
        "all_theories": all_theories,
        "theory_count": len(all_theories),
        "has_innovative_theory": len(innovative) > 0 or unnamed_innovative_count > 0,
        "theory_innovation_score": innovation_score,
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
    """Reichert jede Paper-Dict um Theorien- und Themen-Infos an (inkl. der
    neuen Innovations-Felder aus extract_theories_from_abstract)."""
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


def filter_innovative_papers(enriched_papers: list, min_score: int = 1) -> list:
    """
    Filtert aus einer bereits mit analyze_papers() angereicherten Paper-
    Liste gezielt jene heraus, die eine innovative/neue Theorie enthalten
    (has_innovative_theory=True) bzw. mindestens min_score Innovations-
    Punkte erreichen, und sortiert absteigend nach theory_innovation_score.

    Das ist die direkte Antwort auf "zeig mir die Paper mit neuen/
    innovativen Theorien" - im Gegensatz zu count_all_theories(), das ALLE
    (auch bereits etablierte) Theorien zählt.
    """
    candidates = [
        p for p in enriched_papers
        if p.get("has_innovative_theory") or p.get("theory_innovation_score", 0) >= min_score
    ]
    candidates.sort(key=lambda p: p.get("theory_innovation_score", 0), reverse=True)
    return candidates


def count_all_theories(enriched_papers: list) -> Counter:
    """Zählt, wie oft jede Theorie über alle Paper hinweg vorkommt.
    Singular/Plural sind bereits vor dem Zählen vereinheitlicht,
    Framework-Treffer wurden bereits vorher entfernt."""
    counter = Counter()
    for paper in enriched_papers:
        for theory in paper.get("all_theories", []):
            counter[theory] += 1
    return counter


def count_innovative_theories(enriched_papers: list) -> Counter:
    """Wie count_all_theories(), aber NUR über die als innovativ/neu
    markierten Theorienamen (Feld 'innovative_theories'). Zeigt, welche
    neuartigen Theorien am häufigsten in den gescrapten Papern vorgeschlagen
    werden."""
    counter = Counter()
    for paper in enriched_papers:
        for theory in paper.get("innovative_theories", []):
            counter[theory] += 1
    return counter
