"""REST endpoints for the viewer — entity lookups and session history."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse

from linked_past.core.store import execute_query, get_data_dir
from linked_past.core.viewer import get_manager

logger = logging.getLogger(__name__)

# Predicates commonly used as display names
_NAME_PREDICATES = (
    "hasPersonName", "label", "prefLabel", "skos:prefLabel",
    "rdfs:label", "title", "name", "foaf:name",
)


def _extract_name(uri: str, properties: list[dict[str, str]], store=None) -> str:
    """Extract a display name, preferring English labels.

    Does a dedicated label query with language preference first (catches
    multi-language datasets like Nomisma), then falls back to property
    scan, then URI fragment.
    """
    # Dedicated label query — prefer @en tagged, then untagged, then any
    if store:
        try:
            from linked_past.core.store import execute_query

            # Try English-tagged first (most reliable for multilingual datasets)
            for lang_filter in [
                "FILTER(lang(?label) = 'en')",
                "FILTER(lang(?label) = '')",
                "",
            ]:
                rows = execute_query(
                    store,
                    "SELECT ?label WHERE { "
                    f"  <{uri}> ?pred ?label . "
                    "  VALUES ?pred { "
                    "    <http://www.w3.org/2000/01/rdf-schema#label> "
                    "    <http://www.w3.org/2004/02/skos/core#prefLabel> "
                    "    <http://purl.org/dc/terms/title> "
                    "  } "
                    f"  {lang_filter} "
                    "} LIMIT 1",
                )
                if rows and rows[0].get("label"):
                    return rows[0]["label"]
        except Exception as e:
            logger.debug("Label query failed for %s: %s", uri, e)

    # Fall back to well-known name predicates from properties
    for pred in _NAME_PREDICATES:
        for prop in properties:
            pred_local = prop["pred"].rsplit("/", 1)[-1].rsplit("#", 1)[-1]
            if pred_local == pred:
                return prop["obj"]

    return uri.rstrip("/").rsplit("/", 1)[-1].rsplit("#", 1)[-1]


def resolve_entity(uri: str, registry, linkage) -> dict | None:
    """Resolve an entity URI to a data dict, or return None if not found.

    This is the core logic extracted from entity_handler so it can be called
    outside the request/response cycle (e.g. for pre-building an entity cache).

    Returns a dict with keys: uri, name, dataset, description, type_hierarchy,
    see_also, properties, predicate_meta, xrefs — or None if the URI is not
    known to any loaded dataset.
    """
    # Normalize URI to match canonical forms in the store.
    # Strip www., map known domain aliases, then try both http/https.
    canonical_uri = uri.replace("://www.", "://")
    # EDH public domain → canonical RDF domain
    canonical_uri = canonical_uri.replace(
        "://edh.ub.uni-heidelberg.de/edh/",
        "://edh-www.adw.uni-heidelberg.de/edh/",
    )

    # Try canonical URI, then with swapped scheme (some datasets use http, others https)
    ds_name = registry.dataset_for_uri(canonical_uri)
    if not ds_name:
        if canonical_uri.startswith("https://"):
            ds_name = registry.dataset_for_uri("http://" + canonical_uri[8:])
            if ds_name:
                canonical_uri = "http://" + canonical_uri[8:]
        elif canonical_uri.startswith("http://"):
            ds_name = registry.dataset_for_uri("https://" + canonical_uri[7:])
            if ds_name:
                canonical_uri = "https://" + canonical_uri[7:]

    if not ds_name:
        return None

    properties: list[dict[str, str]] = []
    description = ""
    see_also: list[str] = []
    type_hierarchy: list[str] = []
    predicate_meta: dict[str, dict] = {}  # pred URI → {label, comment, domain, range}

    try:
        store = registry.get_store(ds_name)

        # Entity properties — filter to English/Latin/untagged literals only.
        # Multilingual datasets (Nomisma) have 100+ language variants per entity;
        # without filtering, LIMIT truncates before reaching useful properties.
        def _query_props(query_uri: str) -> list[dict[str, str]]:
            rows = execute_query(
                store,
                f"SELECT ?pred ?obj WHERE {{ "
                f"  <{query_uri}> ?pred ?obj . "
                f"  FILTER(!isLiteral(?obj) || lang(?obj) = '' || lang(?obj) = 'en' || lang(?obj) = 'la') "
                f"}} LIMIT 100",
            )
            seen = set()
            deduped = []
            for r in rows:
                key = (r["pred"], r["obj"] or "")
                if key not in seen:
                    seen.add(key)
                    deduped.append({"pred": key[0], "obj": key[1]})
            return deduped

        properties = _query_props(canonical_uri)
        # If no results, try the opposite scheme (store may use different scheme than registry)
        if not properties:
            if canonical_uri.startswith("http://"):
                alt_uri = "https://" + canonical_uri[7:]
            else:
                alt_uri = "http://" + canonical_uri[8:]
            properties = _query_props(alt_uri)
            if properties:
                canonical_uri = alt_uri  # use the scheme that worked

        # rdfs:comment on the entity itself (Pleiades places have descriptions)
        rdfs_comment = "http://www.w3.org/2000/01/rdf-schema#comment"
        comment_rows = execute_query(
            store,
            f"SELECT ?comment WHERE {{ <{canonical_uri}> <{rdfs_comment}> ?comment . }} LIMIT 1",
        )
        if comment_rows:
            description = comment_rows[0].get("comment", "")

        # rdfs:seeAlso on the entity (Pleiades has ~30K external links)
        rdfs_see_also = "http://www.w3.org/2000/01/rdf-schema#seeAlso"
        see_also_rows = execute_query(
            store,
            f"SELECT ?target WHERE {{ <{canonical_uri}> <{rdfs_see_also}> ?target . }} LIMIT 10",
        )
        see_also = [r["target"] for r in see_also_rows if r.get("target")]

        # Type hierarchy: rdf:type → rdfs:subClassOf chain
        rdfs_sub = "http://www.w3.org/2000/01/rdf-schema#subClassOf"
        type_sparql = (
            f"SELECT ?type ?parent WHERE {{ <{canonical_uri}> a ?type . "
            f"OPTIONAL {{ ?type <{rdfs_sub}> ?parent }} }} LIMIT 20"
        )
        type_rows = execute_query(store, type_sparql)
        for r in type_rows:
            t = r.get("type", "")
            if t and not t.startswith("http://www.w3.org/"):
                local = t.rsplit("/", 1)[-1].rsplit("#", 1)[-1]
                if local not in type_hierarchy:
                    type_hierarchy.append(local)

        # Predicate metadata: rdfs:label, rdfs:comment, rdfs:domain, rdfs:range
        pred_uris = {p["pred"] for p in properties}
        if pred_uris:
            # Build VALUES clause for the predicates we actually have
            values = " ".join(f"<{p}>" for p in pred_uris if p.startswith("http"))
            if values:
                meta_rows = execute_query(
                    store,
                    f"""SELECT ?pred ?label ?comment ?domain ?range WHERE {{
                        VALUES ?pred {{ {values} }}
                        OPTIONAL {{ ?pred <http://www.w3.org/2000/01/rdf-schema#label> ?label }}
                        OPTIONAL {{ ?pred <http://www.w3.org/2000/01/rdf-schema#comment> ?comment }}
                        OPTIONAL {{ ?pred <http://www.w3.org/2000/01/rdf-schema#domain> ?domain }}
                        OPTIONAL {{ ?pred <http://www.w3.org/2000/01/rdf-schema#range> ?range }}
                    }} LIMIT 200""",
                )
                for r in meta_rows:
                    pred_uri = r.get("pred", "")
                    if pred_uri not in predicate_meta:
                        predicate_meta[pred_uri] = {}
                    m = predicate_meta[pred_uri]
                    if r.get("label") and "label" not in m:
                        m["label"] = r["label"]
                    if r.get("comment") and "comment" not in m:
                        m["comment"] = r["comment"]
                    if r.get("domain") and "domain" not in m:
                        m["domain"] = r["domain"].rsplit("/", 1)[-1].rsplit("#", 1)[-1]
                    if r.get("range") and "range" not in m:
                        m["range"] = r["range"].rsplit("/", 1)[-1].rsplit("#", 1)[-1]

    except Exception as e:
        logger.warning("Entity query failed for %s: %s", uri, e)

    # Cross-references
    xrefs = []
    if linkage:
        from linked_past.core.server import _find_store_xrefs

        linkage_links = linkage.find_links(canonical_uri)
        store_links = _find_store_xrefs(canonical_uri, registry)
        seen = set()
        for link in linkage_links + store_links:
            if link["target"] not in seen:
                seen.add(link["target"])
                xrefs.append(link)

    # Get the store for English label preference
    entity_store = None
    try:
        entity_store = registry.get_store(ds_name)
    except KeyError:
        pass
    name = _extract_name(canonical_uri, properties, store=entity_store)

    return {
        "uri": uri,
        "name": name,
        "dataset": ds_name,
        "description": description,
        "type_hierarchy": type_hierarchy,
        "see_also": see_also,
        "properties": properties,
        "predicate_meta": predicate_meta,
        "xrefs": xrefs,
    }


async def entity_handler(request: Request) -> JSONResponse | PlainTextResponse:
    """GET /viewer/api/entity?uri=... — return entity properties + xrefs as JSON."""
    mgr = get_manager()
    if mgr is None or not mgr.is_active:
        return PlainTextResponse("Viewer not active", status_code=404)

    uri = request.query_params.get("uri")
    if not uri:
        return JSONResponse({"error": "Missing 'uri' query parameter"}, status_code=400)
    if not uri.startswith(("http://", "https://")):
        return JSONResponse({"error": "Invalid URI scheme"}, status_code=400)

    registry = mgr.app_context.registry
    linkage = mgr.app_context.linkage
    result = resolve_entity(uri, registry, linkage)
    if result is None:
        return JSONResponse({
            "uri": uri,
            "name": uri.rstrip("/").rsplit("/", 1)[-1].rsplit("#", 1)[-1],
            "dataset": None,
            "description": "",
            "type_hierarchy": [],
            "see_also": [],
            "properties": [],
            "predicate_meta": {},
            "xrefs": [],
        })
    return JSONResponse(result)


# ── Session history ──────────────────────────────────────────────────────────


def _sessions_dir() -> Path:
    return Path(get_data_dir()) / "viewer" / "sessions"


async def sessions_list_handler(request: Request) -> JSONResponse:  # noqa: ARG001
    """GET /viewer/api/sessions — list available session files."""
    sessions_path = _sessions_dir()
    if not sessions_path.exists():
        return JSONResponse([])

    sessions = []
    for f in sorted(sessions_path.glob("*.jsonl"), reverse=True):
        # Count lines and read first/last timestamps
        lines = [ln for ln in f.read_text().strip().splitlines() if ln.strip()]
        if not lines:
            continue
        try:
            first = json.loads(lines[0])
            last = json.loads(lines[-1])
        except json.JSONDecodeError:
            continue
        mgr = get_manager()
        is_current = mgr is not None and mgr.session_id == f.stem

        sessions.append({
            "id": f.stem,
            "message_count": len(lines),
            "started": first.get("timestamp") or first.get("created_at"),
            "last_activity": last.get("timestamp"),
            "is_current": is_current,
        })

    return JSONResponse(sessions)


async def session_detail_handler(request: Request) -> JSONResponse | PlainTextResponse:
    """GET /viewer/api/sessions/{session_id} — return all messages for a session."""
    session_id = request.path_params.get("session_id", "")
    session_file = _sessions_dir() / f"{session_id}.jsonl"

    if not session_file.exists():
        return PlainTextResponse("Session not found", status_code=404)

    # Resolve to prevent path traversal
    if not str(session_file.resolve()).startswith(str(_sessions_dir().resolve())):
        return PlainTextResponse("Forbidden", status_code=403)

    fmt = request.query_params.get("format", "json")

    if fmt == "jsonl":
        content = session_file.read_text()
        # Ensure session_meta preamble exists (for sessions created before this feature)
        if not content.startswith('{"format_version"'):
            lines = content.strip().splitlines()
            first = json.loads(lines[0]) if lines else {}
            meta = json.dumps({
                "format_version": 1,
                "type": "session_meta",
                "session_id": session_id,
                "created_at": first.get("timestamp", datetime.now(timezone.utc).isoformat()),
            })
            content = meta + "\n" + content

        return PlainTextResponse(
            content,
            headers={
                "Content-Disposition": f'attachment; filename="linked-past-{session_id}.jsonl"',
            },
        )

    lines = session_file.read_text().strip().splitlines()
    messages = [json.loads(line) for line in lines if line.strip()]

    return JSONResponse(messages)
