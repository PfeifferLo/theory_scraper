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
# Wird genutzt, um z.B. "Legitimacy Theories" auf "Legitimacy Theory"
# zu vereinheitlichen, egal in welcher der drei Methoden es gefunden wurde.
PLURAL_TO_SINGULAR_KEYWORDS = {
    "theories": "theory",
    "views": "view",
    "perspectives": "perspective",
    "approaches": "approach",
    "frameworks": "framework",
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
# "model" bewusst ausgeschlossen (siehe GENERIC_THEORY_KEYWORD_RE weiter
# unten) - zu viele Fehltreffer wie "regression model", "conceptual model".
THEORY_KEYWORDS = (
    r"(theories|theory|views|view|perspectives|perspective|"
    r"approaches|approach|frameworks|framework|paradigms|paradigm)"
)

# Kombiniertes Muster: Signalphrase + bis zu 6 Wörter + Theorie-Schlüsselwort
SIGNAL_PATTERN = re.compile(
    r"(?:" + "|".join(SIGNAL_PHRASES) + r")\s+"
    r"((?:[A-Za-z][\w\-]*\s+){0,6}" + THEORY_KEYWORDS + r")",
    re.IGNORECASE
)


# -----------------------------------------------------
# 3. Generische Erkennung: "<Begriff> + Theorie-Schlüsselwort"
# -----------------------------------------------------
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

# Theorie-Schlüsselwörter als eigenständige Tokens (Singular + Plural),
# "model" bewusst ausgeschlossen (siehe oben).
GENERIC_THEORY_KEYWORD_RE = re.compile(
    r"^(theories|theory|views|view|perspectives|perspective|"
    r"frameworks|framework|paradigms|paradigm|approaches|approach)$",
    re.IGNORECASE,
)

_TOKEN_RE = re.compile(r"[A-Za-z][\w\-]*|[.,;:()\[\]]")


def extract_generic_theories(abstract: str, max_words: int = 3) -> list:
    """
    Läuft von jedem Theorie-Schlüsselwort ("theory"/"theories", "view"/
    "views", ...) rückwärts durch die vorangehenden Wörter und sammelt sie,
    solange sie keine Satzzeichen oder Füllwörter (GENERIC_STOPWORDS) sind.
    Ergebnis wird auf Singular normalisiert (normalize_theory_name).
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
