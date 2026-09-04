"""Search-index enrichment shared by Nomisma-based coin type corpora (CRRO, OCRE).

Coin type labels are catalogue numbers ("RRC 366/1") that no scholar searches
for by themselves. This helper appends the issuer's English name from the
Nomisma store so ``search_entities("Annius")`` finds the type.
"""

from __future__ import annotations

import logging

from pyoxigraph import Store

logger = logging.getLogger(__name__)

_ISSUER_QUERY = (
    "PREFIX nmo: <http://nomisma.org/ontology#> "
    "PREFIX skos: <http://www.w3.org/2004/02/skos/core#> "
    "SELECT DISTINCT ?coin ?coinLabel ?issuer WHERE { "
    "  ?coin a nmo:TypeSeriesItem ; "
    "        skos:prefLabel ?coinLabel ; "
    "        nmo:hasIssuer ?issuer . "
    "}"
)

_LABEL_QUERY = (
    "SELECT ?label WHERE {{ <{issuer}> <http://www.w3.org/2004/02/skos/core#prefLabel> ?label . "
    "FILTER(lang(?label) = 'en' || lang(?label) = '') }} LIMIT 1"
)


def issuer_enriched_labels(dataset: str, store: Store, registry) -> list[tuple[str, str]]:
    """Return ``("entity_label", "<coin label> — <issuer name>\\t<coin uri>")`` rows.

    Returns ``[]`` when the Nomisma store is not initialised.
    """
    if registry is None:
        return []
    try:
        nomisma_store = registry.get_store("nomisma")
    except KeyError:
        logger.info("skip issuer enrichment dataset=%s reason=nomisma not initialized", dataset)
        return []

    rows: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for coin, coin_label, issuer in store.query(_ISSUER_QUERY):
        labels = list(nomisma_store.query(_LABEL_QUERY.format(issuer=issuer.value)))
        if not labels:
            continue
        enriched = f"{coin_label.value} — {labels[0][0].value}"
        key = (coin.value, enriched)
        if key in seen:
            continue
        seen.add(key)
        rows.append(("entity_label", f"{enriched}\t{coin.value}"))
    logger.info("issuer enrichment dataset=%s rows=%d", dataset, len(rows))
    return rows
