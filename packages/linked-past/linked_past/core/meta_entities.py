"""Meta-entity layer: unified entity resolution across datasets.

Clusters URIs from different datasets that refer to the same real-world
entity, generates rich descriptions, and provides semantic search.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class MetaEntity:
    id: str
    canonical_name: str
    entity_type: str
    description: str
    date_range: str | None = None
    uris: dict[str, list[str]] = field(default_factory=dict)
    wikidata_qid: str | None = None


class MetaEntityIndex:
    """Builds and queries meta-entity clusters from linkage data and dataset stores."""

    def __init__(self, db_path: Path | str | None = None):
        self._entities: dict[str, MetaEntity] = {}
        self._uri_to_id: dict[str, str] = {}  # Any URI → meta-entity ID
        self._db_path = db_path
        if db_path:
            self._conn = sqlite3.connect(str(db_path))
            self._init_db()
        else:
            self._conn = None

    def _init_db(self):
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS meta_entities (
                id TEXT PRIMARY KEY,
                canonical_name TEXT,
                entity_type TEXT,
                description TEXT,
                date_range TEXT,
                uris_json TEXT,
                wikidata_qid TEXT
            )
        """)
        self._conn.commit()

    def build_from_linkage(self, linkage, registry) -> int:
        """Build meta-entity clusters from the linkage graph and dataset stores.

        Args:
            linkage: LinkageGraph instance
            registry: DatasetRegistry instance

        Returns:
            Number of meta-entities created
        """

        # Step 1: Seed clusters from curated DPRR↔Nomisma links
        clusters = self._seed_from_linkage(linkage)

        # Step 2: Extend with Nomisma→Wikidata bridges
        self._extend_with_wikidata(clusters, registry)

        # Step 3: Extend with EDH→Wikidata bridges
        self._extend_with_edh(clusters, registry)

        # Step 4: Build descriptions from dataset properties
        for cluster_id, cluster in clusters.items():
            entity = self._build_entity(cluster_id, cluster, registry)
            self._entities[entity.id] = entity
            for uris in entity.uris.values():
                for uri in uris:
                    self._uri_to_id[uri] = entity.id

        # Step 5: Persist to SQLite
        if self._conn:
            self._persist()

        logger.info("Built %d meta-entities", len(self._entities))
        return len(self._entities)

    def _seed_from_linkage(self, linkage) -> dict[str, dict]:
        """Seed clusters from curated linkage graph (DPRR↔Nomisma confirmed links)."""
        clusters = {}
        if not linkage:
            return clusters

        # Query the linkage graph for all skos:closeMatch links
        try:
            results = linkage._store.query("""
                SELECT ?source ?target ?graph WHERE {
                    GRAPH ?graph { ?source ?rel ?target }
                }
            """)
            for row in results:
                source = row["source"].value
                target = row["target"].value

                # Find or create cluster
                cluster_id = None
                for cid, cluster in clusters.items():
                    all_uris = set()
                    for uris in cluster.values():
                        all_uris.update(uris)
                    if source in all_uris or target in all_uris:
                        cluster_id = cid
                        break

                if cluster_id is None:
                    cluster_id = f"cluster_{len(clusters)}"
                    clusters[cluster_id] = {}

                cluster = clusters[cluster_id]
                # Assign URIs to datasets based on namespace
                for uri in [source, target]:
                    ds = self._uri_to_dataset(uri)
                    if ds:
                        if ds not in cluster:
                            cluster[ds] = set()
                        cluster[ds].add(uri)
        except Exception as e:
            logger.warning("Failed to read linkage graph: %s", e)

        return clusters

    def _extend_with_wikidata(self, clusters: dict, registry) -> None:
        """Extend clusters with Nomisma→Wikidata skos:exactMatch bridges."""
        try:
            store = registry.get_store("nomisma")
        except KeyError:
            return

        from linked_past.core.store import execute_query

        for cluster in clusters.values():
            nomisma_uris = cluster.get("nomisma", set())
            for nm_uri in list(nomisma_uris):
                sparql = f"""
                SELECT ?wikidata WHERE {{
                    <{nm_uri}> <http://www.w3.org/2004/02/skos/core#exactMatch> ?wikidata .
                    FILTER(STRSTARTS(STR(?wikidata), "http://www.wikidata.org/entity/"))
                }}
                """
                try:
                    rows = execute_query(store, sparql)
                    for row in rows:
                        qid = row["wikidata"]
                        if "wikidata" not in cluster:
                            cluster["wikidata"] = set()
                        cluster["wikidata"].add(qid)
                except Exception:
                    pass

    def _extend_with_edh(self, clusters: dict, registry) -> None:
        """Extend clusters with EDH→Wikidata skos:sameAs bridges."""
        try:
            store = registry.get_store("edh")
        except KeyError:
            return

        from linked_past.core.store import execute_query

        for cluster in clusters.values():
            wikidata_uris = cluster.get("wikidata", set())
            for wd_uri in list(wikidata_uris):
                # EDH uses https://www.wikidata.org/wiki/Q... format
                wd_wiki = wd_uri.replace("http://www.wikidata.org/entity/", "https://www.wikidata.org/wiki/")
                sparql = f"""
                SELECT ?person WHERE {{
                    ?person <http://www.w3.org/2004/02/skos/core#sameAs> <{wd_wiki}> .
                }}
                LIMIT 50
                """
                try:
                    rows = execute_query(store, sparql)
                    if rows:
                        if "edh" not in cluster:
                            cluster["edh"] = set()
                        for row in rows:
                            cluster["edh"].add(row["person"])
                except Exception:
                    pass

    def _build_entity(self, cluster_id: str, cluster: dict, registry) -> MetaEntity:
        """Build a MetaEntity from a cluster of URIs."""
        from linked_past.core.store import execute_query

        # Convert sets to lists
        uris = {ds: sorted(uri_set) for ds, uri_set in cluster.items() if ds != "wikidata"}
        wikidata_qids = cluster.get("wikidata", set())
        qid = sorted(wikidata_qids)[0] if wikidata_qids else None

        # Extract canonical name and date range from DPRR
        canonical_name = cluster_id
        date_range = None
        highest_office = None

        dprr_uris = cluster.get("dprr", set())
        if dprr_uris:
            dprr_uri = sorted(dprr_uris)[0]
            try:
                store = registry.get_store("dprr")
                rows = execute_query(store, f"""
                    PREFIX vocab: <http://romanrepublic.ac.uk/rdf/ontology#>
                    SELECT ?name ?eraFrom ?eraTo ?office WHERE {{
                        <{dprr_uri}> vocab:hasPersonName ?name .
                        OPTIONAL {{ <{dprr_uri}> vocab:hasEraFrom ?eraFrom }}
                        OPTIONAL {{ <{dprr_uri}> vocab:hasEraTo ?eraTo }}
                        OPTIONAL {{ <{dprr_uri}> vocab:hasHighestOffice ?office }}
                    }}
                """)
                if rows:
                    r = rows[0]
                    # Clean up DPRR name: "IUNI0001 L. Iunius Brutus" → "L. Iunius Brutus"
                    raw_name = r.get("name", "")
                    canonical_name = raw_name.split(" ", 1)[-1] if " " in raw_name else raw_name
                    era_from = r.get("eraFrom")
                    era_to = r.get("eraTo")
                    if era_from:
                        from_bc = f"{abs(int(era_from))} BC" if int(era_from) < 0 else f"{era_from} AD"
                        if era_to and int(era_to) < 0:
                            to_bc = f"{abs(int(era_to))} BC"
                        elif era_to:
                            to_bc = f"{era_to} AD"
                        else:
                            to_bc = "?"
                        date_range = f"{from_bc}–{to_bc}"
                    highest_office = r.get("office")
            except Exception as e:
                logger.debug("Failed to get DPRR properties for %s: %s", dprr_uri, e)

        # Fall back to Nomisma label if no DPRR name
        if canonical_name == cluster_id:
            nomisma_uris = cluster.get("nomisma", set())
            if nomisma_uris:
                nm_uri = sorted(nomisma_uris)[0]
                try:
                    store = registry.get_store("nomisma")
                    rows = execute_query(store, f"""
                        SELECT ?label WHERE {{
                            <{nm_uri}> <http://www.w3.org/2004/02/skos/core#prefLabel> ?label .
                            FILTER(LANG(?label) = "en")
                        }}
                    """)
                    if rows:
                        canonical_name = rows[0]["label"]
                except Exception:
                    pass

        # Get Nomisma definition
        nomisma_def = ""
        nomisma_uris = cluster.get("nomisma", set())
        if nomisma_uris:
            nm_uri = sorted(nomisma_uris)[0]
            try:
                store = registry.get_store("nomisma")
                rows = execute_query(store, f"""
                    SELECT ?def WHERE {{
                        <{nm_uri}> <http://www.w3.org/2004/02/skos/core#definition> ?def .
                        FILTER(LANG(?def) = "en")
                    }}
                """)
                if rows:
                    nomisma_def = rows[0]["def"]
            except Exception:
                pass

        # Count EDH attestations
        edh_count = len(cluster.get("edh", set()))

        # Build stable ID from canonical name
        entity_id = f"person:{canonical_name.lower().replace(' ', '_').replace('.', '')}"

        # Assemble description
        parts = [canonical_name]
        if date_range:
            parts[0] += f" ({date_range})"
        parts[0] += "."
        if highest_office:
            parts.append(f"Highest office: {highest_office}.")
        if nomisma_def:
            parts.append(f"{nomisma_def}.")
        if edh_count > 0:
            parts.append(f"Mentioned in {edh_count} EDH inscription(s).")
        if qid:
            parts.append(f"Wikidata {qid.split('/')[-1]}.")

        description = " ".join(parts)

        return MetaEntity(
            id=entity_id,
            canonical_name=canonical_name,
            entity_type="person",
            description=description,
            date_range=date_range,
            uris=uris,
            wikidata_qid=qid,
        )

    def _persist(self):
        """Save meta-entities to SQLite."""
        for entity in self._entities.values():
            self._conn.execute(
                "INSERT OR REPLACE INTO meta_entities VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    entity.id,
                    entity.canonical_name,
                    entity.entity_type,
                    entity.description,
                    entity.date_range,
                    json.dumps(entity.uris),
                    entity.wikidata_qid,
                ),
            )
        self._conn.commit()

    def search(self, query: str, k: int = 5) -> list[MetaEntity]:
        """Search meta-entities by name (substring match). For semantic search, use embeddings."""
        query_lower = query.lower()
        scored = []
        for entity in self._entities.values():
            if query_lower in entity.canonical_name.lower() or query_lower in entity.description.lower():
                # Score by how early the match appears
                pos = entity.canonical_name.lower().find(query_lower)
                if pos == -1:
                    pos = 1000
                scored.append((pos, entity))
        scored.sort(key=lambda x: x[0])
        return [e for _, e in scored[:k]]

    def get_by_uri(self, uri: str) -> MetaEntity | None:
        """Look up a meta-entity by any of its constituent URIs."""
        entity_id = self._uri_to_id.get(uri)
        if entity_id:
            return self._entities.get(entity_id)
        return None

    def get_by_id(self, entity_id: str) -> MetaEntity | None:
        return self._entities.get(entity_id)

    def all_entities(self) -> list[MetaEntity]:
        return list(self._entities.values())

    @staticmethod
    def _uri_to_dataset(uri: str) -> str | None:
        """Determine dataset from URI namespace."""
        namespaces = {
            "http://romanrepublic.ac.uk/rdf/": "dprr",
            "https://pleiades.stoa.org/places/": "pleiades",
            "http://n2t.net/ark:/99152/": "periodo",
            "http://nomisma.org/id/": "nomisma",
            "http://numismatics.org/crro/id/": "crro",
            "http://numismatics.org/ocre/id/": "ocre",
            "http://edh-www.adw.uni-heidelberg.de/edh/": "edh",
            "https://edh-www.adw.uni-heidelberg.de/edh/": "edh",
            "http://www.wikidata.org/entity/": "wikidata",
            "https://www.wikidata.org/wiki/": "wikidata",
        }
        for ns, ds in namespaces.items():
            if uri.startswith(ns):
                return ds
        return None
