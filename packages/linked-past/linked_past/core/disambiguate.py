"""Prosopographic disambiguation engine.

Scores DPRR person candidates against contextual evidence (filiation,
career, geography, temporal overlap) using weighted linear combination.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

from linked_past.core.onomastics import (
    is_greek,
    normalize_praenomen,
    parse_filiation,
    parse_office,
    parse_roman_name,
    transliterate_greek,
)

logger = logging.getLogger(__name__)

WEIGHTS = {
    "filiation": 0.4,
    "career": 0.3,
    "geography": 0.2,
    "temporal": 0.1,
}

# Cursus honorum minimum ages (approximate)
_MIN_AGE_FOR_OFFICE = {
    "consul": 35,
    "praetor": 33,
    "aedilis": 30,
    "tribunus plebis": 27,
    "quaestor": 25,
    "legatus": 25,
    "proconsul": 35,
    "propraetor": 33,
}
_MAX_AGE = 80  # No one holds office after ~80


@dataclass
class PersonContext:
    name: str
    normalized_name: str
    praenomen: str | None = None
    nomen: str | None = None
    cognomen: str | None = None
    filiation: str | None = None
    office: str | None = None
    date_start: int | None = None
    date_end: int | None = None
    findspot_uri: str | None = None
    source_uri: str | None = None


@dataclass
class SignalResult:
    score: float        # 0.0–1.0
    weight: float       # from WEIGHTS dict
    explanation: str
    is_absent: bool     # True if signal has no data (weight redistributed)


@dataclass
class CandidateMatch:
    dprr_uri: str
    dprr_label: str
    score: float
    confidence: str  # "strong", "probable", "ambiguous"
    signals: dict[str, SignalResult] = field(default_factory=dict)


def score_temporal(
    era_from: int | None,
    era_to: int | None,
    date_start: int | None,
    date_end: int | None,
) -> tuple[float, str, bool]:
    """Score temporal overlap between DPRR era and inscription dates.
    Returns (score, explanation, is_absent).
    """
    if era_from is None and era_to is None:
        return 0.0, "no DPRR era data", True
    if date_start is None and date_end is None:
        return 0.0, "no inscription date", True

    # Use midpoint of inscription date range
    if date_start is not None and date_end is not None:
        mid = (date_start + date_end) / 2
    elif date_start is not None:
        mid = date_start
    else:
        mid = date_end  # type: ignore[assignment]

    e_from = era_from if era_from is not None else -500
    e_to = era_to if era_to is not None else 100

    if e_from <= mid <= e_to:
        return 1.0, f"inscription date {mid:.0f} within era {e_from}..{e_to}", False
    elif (date_start is not None and date_end is not None and
          not (date_end < e_from or date_start > e_to)):
        return 0.5, f"partial overlap: inscription {date_start}..{date_end}, era {e_from}..{e_to}", False
    else:
        return 0.0, f"no overlap: inscription ~{mid:.0f}, era {e_from}..{e_to}", False


def score_career(
    dprr_offices: list[dict],
    era_from: int | None,
    office: str | None,
    date: int | None,
) -> tuple[float, str, bool]:
    """Score career/office match between DPRR person and inscription evidence.
    Returns (score, explanation, is_absent).
    """
    if office is None:
        return 0.0, "no office in inscription", True

    # Check cursus age constraint
    if era_from is not None and date is not None:
        age_at_date = date - era_from  # positive = person alive; negative = office before birth
        if age_at_date < 0:
            return 0.0, f"impossible: office at {date} before birth ~{era_from}", False
        min_age = _MIN_AGE_FOR_OFFICE.get(office, 25)
        if age_at_date < min_age:
            return 0.0, f"cursus violation: age {age_at_date} at {date}, min {min_age} for {office}", False
        if age_at_date > _MAX_AGE:
            return 0.0, f"implausible: age {age_at_date} at {date}", False

    # Check if DPRR person held this office
    held_offices = [o for o in dprr_offices if office in o.get("office", "").lower()]
    if not held_offices:
        # Office not held — but if they held a higher office, career level is plausible
        any_offices = len(dprr_offices) > 0
        if any_offices:
            return 0.3, f"{office} not held, but career active", False
        return 0.0, "no offices recorded", False

    # Office held — check date proximity
    if date is None:
        return 0.5, f"{office} held (no inscription date to compare)", False

    closest = min(held_offices, key=lambda o: abs((o.get("date_start") or 0) - date))
    closest_date = closest.get("date_start")
    if closest_date is None:
        return 0.5, f"{office} held (no DPRR date to compare)", False

    gap = abs(closest_date - date)
    if gap <= 5:
        return 1.0, f"{office} held in {closest_date}, inscription {date} (±{gap}yr)", False
    elif gap <= 10:
        return 0.7, f"{office} held in {closest_date}, inscription {date} (±{gap}yr)", False
    elif gap <= 20:
        return 0.5, f"{office} held in {closest_date}, inscription {date} (±{gap}yr)", False
    else:
        return 0.3, f"{office} held in {closest_date}, inscription {date} (±{gap}yr, distant)", False


def score_filiation(
    dprr_family: dict[str, str | None],
    inscription_filiation: dict[str, str],
) -> tuple[float, str, bool]:
    """Score filiation match between DPRR family data and inscription filiation.
    Returns (score, explanation, is_absent).

    dprr_family: {"father_praenomen": "marcus", "grandfather_praenomen": "gnaeus"}
    inscription_filiation: {"father": "marcus", "grandfather": "gnaeus"} (from parse_filiation)
    """
    if not inscription_filiation:
        return 0.0, "no filiation in inscription", True
    if not dprr_family:
        return 0.0, "no family data in DPRR", True

    insc_father = inscription_filiation.get("father")
    insc_grandfather = inscription_filiation.get("grandfather")
    dprr_father = dprr_family.get("father_praenomen")
    dprr_grandfather = dprr_family.get("grandfather_praenomen")

    if not insc_father:
        return 0.0, "no father in filiation", True

    if not dprr_father:
        return 0.0, "DPRR father unknown", True

    if insc_father != dprr_father:
        return 0.0, f"father mismatch: inscription {insc_father}, DPRR {dprr_father}", False

    # Father matches
    if insc_grandfather and dprr_grandfather:
        if insc_grandfather == dprr_grandfather:
            return 1.0, f"father ({insc_father}) + grandfather ({insc_grandfather}) match", False
        else:
            return 0.0, f"grandfather mismatch: inscription {insc_grandfather}, DPRR {dprr_grandfather}", False

    return 0.5, f"father matches ({insc_father}), grandfather not verifiable", False


def score_geography(
    dprr_province_pleiades_uris: list[str],
    findspot_pleiades_uri: str | None,
    is_italian_findspot: bool = False,
    has_italian_career: bool = False,
) -> tuple[float, str, bool]:
    """Score geographic match between DPRR provincial posts and inscription findspot.
    Returns (score, explanation, is_absent).

    dprr_province_pleiades_uris: Pleiades URIs for provinces where DPRR person served
    findspot_pleiades_uri: Pleiades URI for the inscription's findspot
    is_italian_findspot: True if findspot is in Italia/Rome/Italian region
    has_italian_career: True if DPRR person held posts in Italia/Rome
    """
    if not findspot_pleiades_uri:
        return 0.0, "no findspot data", True
    if not dprr_province_pleiades_uris:
        # No provincial posts — check Italy fallback
        if is_italian_findspot and has_italian_career:
            return 0.3, "Italy-based career + Italian findspot", False
        return 0.0, "no provincial posts recorded", True

    if findspot_pleiades_uri in dprr_province_pleiades_uris:
        return 1.0, f"findspot matches provincial post ({findspot_pleiades_uri})", False

    # Check Italy fallback
    if is_italian_findspot and has_italian_career:
        return 0.3, "Italy-based career + Italian findspot (no provincial match)", False

    return 0.0, f"findspot {findspot_pleiades_uri} not in served provinces", False


class PersonDisambiguator:
    """Scores DPRR person candidates against contextual evidence."""

    def _compute_weighted_score(self, signals: dict[str, SignalResult]) -> float:
        """Compute weighted score with coverage penalty for sparse evidence.

        When most signals are absent, the raw normalized score is discounted
        by a coverage factor (proportion of total weight that is present).
        This prevents a candidate with only temporal overlap from tying with
        one that has filiation + temporal.
        """
        total_weight = sum(sig.weight for sig in signals.values())
        present_weight = 0.0
        weighted_sum = 0.0

        for sig in signals.values():
            if not sig.is_absent:
                present_weight += sig.weight
                weighted_sum += sig.weight * sig.score

        if present_weight == 0.0 or total_weight == 0.0:
            return 0.0

        raw_score = weighted_sum / present_weight
        coverage = present_weight / total_weight  # 0.0–1.0
        return raw_score * coverage

    @staticmethod
    def _classify_confidence(top_score: float, gap: float) -> str:
        """Classify match confidence based on top score and gap to next candidate."""
        if top_score >= 0.7 and gap >= 0.2:
            return "strong"
        elif top_score >= 0.5 and gap >= 0.1:
            return "probable"
        return "ambiguous"

    def rank_candidates(
        self,
        candidates_signals: list[tuple[str, str, dict[str, SignalResult]]],
    ) -> list[CandidateMatch]:
        """Rank candidates by weighted score.

        candidates_signals: list of (dprr_uri, dprr_label, signals_dict)
        """
        logger.info("rank_candidates: scoring %d candidates", len(candidates_signals))
        scored = []
        for dprr_uri, dprr_label, signals in candidates_signals:
            score = self._compute_weighted_score(signals)
            scored.append((score, dprr_uri, dprr_label, signals))

        scored.sort(key=lambda x: -x[0])

        results = []
        for i, (score, uri, label, signals) in enumerate(scored):
            gap = score - scored[i + 1][0] if i + 1 < len(scored) else score
            confidence = self._classify_confidence(score, gap)
            results.append(CandidateMatch(
                dprr_uri=uri,
                dprr_label=label,
                score=score,
                confidence=confidence,
                signals=signals,
            ))

        if results:
            logger.info(
                "rank_candidates: top=%s score=%.3f confidence=%s",
                results[0].dprr_uri, results[0].score, results[0].confidence,
            )
        return results

    def disambiguate(
        self,
        context: PersonContext,
        dprr_store,
        linkage=None,
        max_candidates: int = 10,
    ) -> list[CandidateMatch]:
        """Full disambiguation: find DPRR candidates by nomen and score each.

        This is the main entry point that orchestrates candidate lookup,
        signal scoring, and ranking.
        """
        if not context.nomen:
            return []

        candidates = fetch_dprr_candidates(dprr_store, context.nomen)
        if not candidates:
            return []

        # Parse filiation from context
        insc_filiation = {}
        if context.filiation:
            if isinstance(context.filiation, dict):
                insc_filiation = context.filiation
            else:
                insc_filiation = parse_filiation(context.filiation)

        candidates_signals = []
        for cand in candidates:
            person_uri = cand["person"]
            label = cand.get("label", "")
            era_from = int(cand["eraFrom"]) if cand.get("eraFrom") else None
            era_to = int(cand["eraTo"]) if cand.get("eraTo") else None

            offices = fetch_dprr_offices(dprr_store, person_uri)
            family = fetch_dprr_family(dprr_store, person_uri)
            province_uris = fetch_dprr_province_pleiades(
                dprr_store, linkage, person_uri,
            ) if linkage else []

            f_s, f_e, f_a = score_filiation(family, insc_filiation)
            c_s, c_e, c_a = score_career(
                offices, era_from, context.office, context.date_start,
            )
            g_s, g_e, g_a = score_geography(province_uris, context.findspot_uri)
            t_s, t_e, t_a = score_temporal(
                era_from, era_to, context.date_start, context.date_end,
            )

            signals = {
                "filiation": SignalResult(f_s, WEIGHTS["filiation"], f_e, f_a),
                "career": SignalResult(c_s, WEIGHTS["career"], c_e, c_a),
                "geography": SignalResult(g_s, WEIGHTS["geography"], g_e, g_a),
                "temporal": SignalResult(t_s, WEIGHTS["temporal"], t_e, t_a),
            }
            candidates_signals.append((person_uri, label, signals))

        ranked = self.rank_candidates(candidates_signals)
        return ranked[:max_candidates]


# ── Context extraction ──────────────────────────────────────────────────────


_OFFICE_ABBREV = {
    "cos.": "consul", "cos": "consul", "consul": "consul",
    "pr.": "praetor", "pr": "praetor", "praetor": "praetor",
    "q.": "quaestor", "q": "quaestor", "quaestor": "quaestor",
    "aed.": "aedilis", "aed": "aedilis", "aedilis": "aedilis",
    "tr. pl.": "tribunus plebis", "tr.pl.": "tribunus plebis",
    "tribunus plebis": "tribunus plebis",
    "procos.": "proconsul", "procos": "proconsul", "proconsul": "proconsul",
    "propr.": "propraetor", "propr": "propraetor", "propraetor": "propraetor",
    "leg.": "legatus", "leg": "legatus", "legatus": "legatus",
}


def _normalize_office_input(office: str) -> str | None:
    """Normalize an office input from the user or inscription text.

    First tries parse_office (regex-based, safe for inscription text).
    Falls back to direct abbreviation lookup (for user-provided short forms like 'q.').
    """
    result = parse_office(office)
    if result:
        return result
    return _OFFICE_ABBREV.get(office.lower().strip())


def extract_context_from_fields(
    name: str,
    filiation: str | None = None,
    office: str | None = None,
    date: int | None = None,
    province: str | None = None,
    uri: str | None = None,
) -> PersonContext:
    """Build PersonContext from manually provided fields."""
    if is_greek(name):
        normalized = transliterate_greek(name)
    else:
        normalized = name

    parsed = parse_roman_name(normalized)
    parsed_office = _normalize_office_input(office) if office else None

    return PersonContext(
        name=name,
        normalized_name=normalized,
        praenomen=parsed.get("praenomen"),
        nomen=parsed.get("nomen"),
        cognomen=parsed.get("cognomen"),
        filiation=filiation,
        office=parsed_office,
        date_start=date,
        date_end=date,
        findspot_uri=province,
        source_uri=uri,
    )


def extract_context_from_edh_uri(uri: str, edh_store) -> PersonContext | None:
    """Extract a PersonContext from an EDH person URI by querying the EDH store.

    Fetches: name, inscription text (for filiation/office parsing), dates, findspot.
    """
    from linked_past.core.store import execute_query

    # Step 1: Get person name and attestation
    person_sparql = f"""
    PREFIX foaf: <http://xmlns.com/foaf/0.1/>
    PREFIX lawd: <http://lawd.info/ontology/>
    SELECT ?name ?att WHERE {{
      <{uri}> foaf:name ?name .
      OPTIONAL {{ <{uri}> lawd:hasAttestation ?att }}
    }}
    LIMIT 1
    """
    person_rows = execute_query(edh_store, person_sparql)
    if not person_rows:
        return None

    name = person_rows[0].get("name", "")
    att_uri = person_rows[0].get("att")

    # Step 2: Get inscription data from attestation
    edition_text = None
    date_start = None
    date_end = None
    findspot_uri = None

    if att_uri:
        # Extract inscription URI from attestation (remove /N#ref suffix)
        insc_uri = re.sub(r"/\d+#.*$", "", att_uri)

        insc_sparql = f"""
        PREFIX epi: <http://edh-www.adw.uni-heidelberg.de/lod/ontology#>
        PREFIX nmo: <http://nomisma.org/ontology#>
        PREFIX lawd: <http://lawd.info/ontology/1.0/>
        SELECT ?editionText ?startDate ?endDate ?foundAt WHERE {{
          <{insc_uri}> epi:editionText ?editionText .
          OPTIONAL {{ <{insc_uri}> nmo:hasStartDate ?startDate }}
          OPTIONAL {{ <{insc_uri}> nmo:hasEndDate ?endDate }}
          OPTIONAL {{ <{insc_uri}> lawd:foundAt ?foundAt }}
        }}
        LIMIT 1
        """
        insc_rows = execute_query(edh_store, insc_sparql)
        if insc_rows:
            edition_text = insc_rows[0].get("editionText")
            raw_start = insc_rows[0].get("startDate")
            raw_end = insc_rows[0].get("endDate")
            findspot_uri = insc_rows[0].get("foundAt")
            try:
                date_start = int(raw_start) if raw_start else None
            except (ValueError, TypeError):
                date_start = None
            try:
                date_end = int(raw_end) if raw_end else None
            except (ValueError, TypeError):
                date_end = None

    # Step 3: Parse name (with Greek transliteration)
    if is_greek(name):
        normalized = transliterate_greek(name)
    else:
        normalized = name

    parsed = parse_roman_name(normalized)

    # Step 4: Parse filiation and office from edition text
    filiation_str = None
    office_str = None
    if edition_text:
        filiation_str = edition_text  # disambiguate() will call parse_filiation
        office_str = parse_office(edition_text)

    return PersonContext(
        name=name,
        normalized_name=normalized,
        praenomen=parsed.get("praenomen"),
        nomen=parsed.get("nomen"),
        cognomen=parsed.get("cognomen"),
        filiation=filiation_str,
        office=office_str,
        date_start=date_start,
        date_end=date_end,
        findspot_uri=findspot_uri,
        source_uri=uri,
    )


# ── SPARQL data fetchers ────────────────────────────────────────────────────


def fetch_dprr_candidates(dprr_store, nomen: str) -> list[dict]:
    """Find DPRR persons matching a nomen. Returns list of person dicts."""
    from linked_past.core.store import execute_query

    sparql = f"""
    PREFIX vocab: <http://romanrepublic.ac.uk/rdf/ontology#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    SELECT DISTINCT ?person ?label ?nomen ?cognomen ?praenomenLabel
           ?eraFrom ?eraTo WHERE {{
      ?person a vocab:Person ;
              vocab:hasPersonName ?label ;
              vocab:hasNomen ?nomen .
      FILTER(LCASE(?nomen) = "{nomen.lower()}")
      OPTIONAL {{ ?person vocab:hasCognomen ?cognomen }}
      OPTIONAL {{ ?person vocab:hasPraenomen ?prae . ?prae rdfs:label ?praenomenLabel }}
      OPTIONAL {{ ?person vocab:hasEraFrom ?eraFrom }}
      OPTIONAL {{ ?person vocab:hasEraTo ?eraTo }}
    }}
    """
    rows = execute_query(dprr_store, sparql)
    logger.debug("fetch_dprr_candidates: rows=%d nomen=%s", len(rows), nomen)
    return rows


def fetch_dprr_offices(dprr_store, person_uri: str) -> list[dict]:
    """Get all offices held by a DPRR person."""
    from linked_past.core.store import execute_query

    sparql = f"""
    PREFIX vocab: <http://romanrepublic.ac.uk/rdf/ontology#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    SELECT ?officeName ?dateStart WHERE {{
      ?pa a vocab:PostAssertion ;
          vocab:isAboutPerson <{person_uri}> ;
          vocab:hasOffice ?office .
      ?office rdfs:label ?officeName .
      OPTIONAL {{ ?pa vocab:hasDateStart ?dateStart }}
    }}
    """
    rows = execute_query(dprr_store, sparql)
    logger.debug("fetch_dprr_offices: rows=%d person=%s", len(rows), person_uri)
    return [{
        "office": r.get("officeName", ""),
        "date_start": int(r["dateStart"]) if r.get("dateStart") else None,
    } for r in rows]


def fetch_dprr_family(dprr_store, person_uri: str) -> dict[str, str | None]:
    """Get father's and grandfather's praenomina for a DPRR person.

    Chains RelationshipAssertions: person ← father of ← father → father of → grandfather.
    """
    from linked_past.core.store import execute_query

    sparql = f"""
    PREFIX vocab: <http://romanrepublic.ac.uk/rdf/ontology#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    SELECT ?fatherPrae ?grandfatherPrae WHERE {{
      # Find father: someone whose "father of" relationship points to person_uri
      ?ra1 a vocab:RelationshipAssertion ;
           vocab:isAboutPerson ?father ;
           vocab:hasRelatedPerson <{person_uri}> ;
           vocab:hasRelationship ?rel1 .
      ?rel1 rdfs:label "Relationship: father of" .
      ?father vocab:hasPraenomen ?fprae .
      ?fprae rdfs:label ?fatherPrae .

      # Find grandfather: someone whose "father of" relationship points to father
      OPTIONAL {{
        ?ra2 a vocab:RelationshipAssertion ;
             vocab:isAboutPerson ?grandfather ;
             vocab:hasRelatedPerson ?father ;
             vocab:hasRelationship ?rel2 .
        ?rel2 rdfs:label "Relationship: father of" .
        ?grandfather vocab:hasPraenomen ?gprae .
        ?gprae rdfs:label ?grandfatherPrae .
      }}
    }}
    LIMIT 1
    """
    rows = execute_query(dprr_store, sparql)
    logger.debug("fetch_dprr_family: rows=%d person=%s", len(rows), person_uri)
    result: dict[str, str | None] = {"father_praenomen": None, "grandfather_praenomen": None}
    for r in rows:
        father_label = r.get("fatherPrae", "")
        if father_label:
            result["father_praenomen"] = normalize_praenomen(father_label.replace("Praenomen: ", ""))
        grandfather_label = r.get("grandfatherPrae", "")
        if grandfather_label:
            result["grandfather_praenomen"] = normalize_praenomen(grandfather_label.replace("Praenomen: ", ""))
    return result


def fetch_dprr_province_pleiades(dprr_store, linkage, person_uri: str) -> list[str]:
    """Get Pleiades URIs for provinces where a DPRR person served."""
    from linked_past.core.store import execute_query

    sparql = f"""
    PREFIX vocab: <http://romanrepublic.ac.uk/rdf/ontology#>
    SELECT DISTINCT ?province WHERE {{
      ?pap a vocab:PostAssertionProvince ;
           vocab:hasPostAssertion ?pa ;
           vocab:hasProvince ?province .
      ?pa vocab:isAboutPerson <{person_uri}> .
    }}
    """
    rows = execute_query(dprr_store, sparql)
    logger.debug("fetch_dprr_province_pleiades: rows=%d person=%s", len(rows), person_uri)
    pleiades_uris = []
    for r in rows:
        province_uri = r.get("province", "")
        if province_uri and linkage:
            links = linkage.find_links(province_uri)
            for link in links:
                target = link.get("target", "")
                if "pleiades.stoa.org" in target:
                    pleiades_uris.append(target)
    return pleiades_uris
