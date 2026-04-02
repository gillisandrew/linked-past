"""Structured question extraction for targeted retrieval.

Decomposes a natural language question into components that enable
better dataset routing, example retrieval, and SPARQL generation.

Inspired by sparql-llm's extraction pipeline, adapted for multi-dataset
prosopographical queries.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class ExtractedQuestion:
    """Structured extraction from a natural language question."""

    original: str
    intent: str  # "query" (needs SPARQL), "explore" (entity lookup), "discover" (which datasets?)
    entities: list[str] = field(default_factory=list)  # Named entities: "Caesar", "Sicily", "denarius"
    classes: list[str] = field(default_factory=list)  # Domain concepts: "person", "office", "province", "coin"
    temporal: str | None = None  # Date/period references: "100 BC", "late Republic"
    spatial: str | None = None  # Place references: "Sicily", "Hispania", "Rome"
    steps: list[str] = field(default_factory=list)  # Decomposed sub-questions
    suggested_datasets: list[str] = field(default_factory=list)  # Which datasets are likely relevant


# Domain concept → dataset mapping
_CONCEPT_DATASETS = {
    # Persons / prosopography
    "person": ["dprr"],
    "consul": ["dprr"],
    "praetor": ["dprr"],
    "senator": ["dprr"],
    "magistrate": ["dprr"],
    "moneyer": ["dprr", "nomisma", "crro"],
    "office": ["dprr"],
    "family": ["dprr"],
    "relationship": ["dprr"],
    # Numismatics
    "coin": ["nomisma", "crro", "ocre"],
    "denarius": ["nomisma", "crro"],
    "aureus": ["nomisma", "crro", "ocre"],
    "mint": ["nomisma"],
    "denomination": ["nomisma"],
    "rrc": ["crro"],
    "ric": ["ocre"],
    # Places
    "place": ["pleiades"],
    "province": ["dprr", "pleiades"],
    "city": ["pleiades"],
    "settlement": ["pleiades"],
    "findspot": ["edh", "pleiades"],
    # Inscriptions
    "inscription": ["edh"],
    "epitaph": ["edh"],
    "epigraph": ["edh"],
    # Periods
    "period": ["periodo"],
    "republic": ["dprr", "periodo"],
    "empire": ["ocre", "periodo"],
    "century": ["periodo"],
}

# Temporal pattern matching
_DATE_PATTERNS = [
    re.compile(r"(\d{1,4})\s*(BC|BCE|AD|CE)", re.IGNORECASE),
    re.compile(r"(early|mid|late|end of the?)\s+(republic|empire|principate)", re.IGNORECASE),
    re.compile(r"(\d+)(st|nd|rd|th)\s+century", re.IGNORECASE),
]


def extract_question(question: str, available_datasets: list[str] | None = None) -> ExtractedQuestion:
    """Extract structured components from a natural language question.

    This is a lightweight, rule-based extraction (no LLM call needed).
    Good enough for dataset routing and example retrieval.
    """
    q_lower = question.lower()

    # Detect intent
    if any(kw in q_lower for kw in ["what datasets", "which datasets", "what data"]):
        intent = "discover"
    elif any(kw in q_lower for kw in ["who is", "tell me about", "explore", "what do we know about"]):
        intent = "explore"
    else:
        intent = "query"

    # Extract temporal references
    temporal = None
    for pattern in _DATE_PATTERNS:
        match = pattern.search(question)
        if match:
            temporal = match.group(0)
            break

    # Extract domain concepts and map to datasets
    detected_concepts = []
    suggested_datasets = set()
    for concept, datasets in _CONCEPT_DATASETS.items():
        if concept in q_lower:
            detected_concepts.append(concept)
            for ds in datasets:
                if available_datasets is None or ds in available_datasets:
                    suggested_datasets.add(ds)

    # Extract likely named entities (capitalized words that aren't common English)
    _COMMON = {
        "the", "a", "an", "in", "of", "for", "and", "or", "who", "what",
        "when", "where", "how", "many", "which", "all", "any", "every",
        "was", "were", "did", "had", "held", "during", "between", "from",
        "to", "with", "about", "find", "list", "show", "tell", "me",
        "roman", "republic", "empire", "ancient", "late", "early",
    }
    entities = []
    for word in re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b", question):
        if word.lower() not in _COMMON and len(word) > 2:
            entities.append(word)

    # Decompose into steps for complex questions
    steps = []
    if " and " in q_lower or " then " in q_lower or "?" in question and q_lower.count("?") > 1:
        # Multi-part question
        parts = re.split(r"\band\b|\bthen\b|\?", question)
        steps = [p.strip() for p in parts if p.strip() and len(p.strip()) > 10]

    # Spatial references
    spatial = None
    _PLACES = [
        "Sicily", "Sicilia", "Hispania", "Africa", "Asia", "Gaul", "Gallia",
        "Rome", "Roma", "Athens", "Alexandria", "Carthage", "Italy", "Greece",
        "Britain", "Britannia", "Egypt", "Syria",
    ]
    for place in _PLACES:
        if place.lower() in q_lower:
            spatial = place
            suggested_datasets.add("pleiades")
            break

    # Default dataset if nothing detected
    if not suggested_datasets:
        suggested_datasets.add("dprr")  # Default to prosopography

    return ExtractedQuestion(
        original=question,
        intent=intent,
        entities=entities,
        classes=detected_concepts,
        temporal=temporal,
        spatial=spatial,
        steps=steps,
        suggested_datasets=sorted(suggested_datasets),
    )
