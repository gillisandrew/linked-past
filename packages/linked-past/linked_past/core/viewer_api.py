"""REST endpoint for entity lookups — used by the viewer's EntityPopover component."""

from __future__ import annotations

import logging

from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse

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

    # Access registry and linkage from the app state stored on the manager
    registry = mgr.app_context.registry
    linkage = mgr.app_context.linkage

    ds_name = registry.dataset_for_uri(uri)
    properties: list[dict[str, str]] = []

    if ds_name:
        try:
            store = registry.get_store(ds_name)
            from linked_past.core.store import execute_query

            rows = execute_query(store, f"SELECT ?pred ?obj WHERE {{ <{uri}> ?pred ?obj . }} LIMIT 50")
            properties = [{"pred": r["pred"], "obj": r["obj"] or ""} for r in rows]
        except Exception as e:
            logger.warning("Entity query failed for %s: %s", uri, e)

    # Cross-references
    xrefs = []
    if linkage:
        from linked_past.core.server import _find_store_xrefs

        linkage_links = linkage.find_links(uri)
        store_links = _find_store_xrefs(uri, registry)
        seen = set()
        for link in linkage_links + store_links:
            if link["target"] not in seen:
                seen.add(link["target"])
                xrefs.append(link)

    name = _extract_name(uri, properties)

    return JSONResponse({
        "uri": uri,
        "name": name,
        "dataset": ds_name,
        "properties": properties,
        "xrefs": xrefs,
    })
