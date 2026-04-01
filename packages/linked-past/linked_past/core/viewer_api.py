"""REST endpoints for the viewer — entity lookups and session history."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse

from linked_past.core.store import get_data_dir
from linked_past.core.viewer import get_manager

logger = logging.getLogger(__name__)

# Predicates commonly used as display names
_NAME_PREDICATES = (
    "hasPersonName", "label", "prefLabel", "skos:prefLabel",
    "rdfs:label", "title", "name", "foaf:name",
)


def _extract_name(uri: str, properties: list[dict[str, str]]) -> str:
    """Extract a display name from entity properties, falling back to URI fragment."""
    for pred in _NAME_PREDICATES:
        for prop in properties:
            pred_local = prop["pred"].rsplit("/", 1)[-1].rsplit("#", 1)[-1]
            if pred_local == pred:
                return prop["obj"]
    return uri.rstrip("/").rsplit("/", 1)[-1].rsplit("#", 1)[-1]


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

    # Normalize URI: strip www., prefer http:// to match canonical forms in the store
    canonical_uri = uri.replace("://www.", "://")
    if canonical_uri.startswith("https://"):
        canonical_uri = "http://" + canonical_uri[8:]

    # Access registry and linkage from the app state stored on the manager
    registry = mgr.app_context.registry
    linkage = mgr.app_context.linkage

    ds_name = registry.dataset_for_uri(canonical_uri)
    properties: list[dict[str, str]] = []

    description = ""
    see_also: list[str] = []
    type_hierarchy: list[str] = []
    predicate_meta: dict[str, dict] = {}  # pred URI → {label, comment, domain, range}

    if ds_name:
        try:
            store = registry.get_store(ds_name)
            from linked_past.core.store import execute_query

            # Entity properties
            rows = execute_query(store, f"SELECT ?pred ?obj WHERE {{ <{canonical_uri}> ?pred ?obj . }} LIMIT 50")
            properties = [{"pred": r["pred"], "obj": r["obj"] or ""} for r in rows]

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

    name = _extract_name(canonical_uri, properties)

    return JSONResponse({
        "uri": uri,
        "name": name,
        "dataset": ds_name,
        "description": description,
        "type_hierarchy": type_hierarchy,
        "see_also": see_also,
        "properties": properties,
        "predicate_meta": predicate_meta,
        "xrefs": xrefs,
    })


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
        lines = f.read_text().strip().splitlines()
        if not lines:
            continue
        first = json.loads(lines[0])
        last = json.loads(lines[-1])
        mgr = get_manager()
        is_current = mgr is not None and mgr.session_id == f.stem

        sessions.append({
            "id": f.stem,
            "message_count": len(lines),
            "started": first.get("timestamp"),
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

    lines = session_file.read_text().strip().splitlines()
    messages = [json.loads(line) for line in lines if line.strip()]

    return JSONResponse(messages)
