"""Extract entity URIs from viewer message data payloads."""
from __future__ import annotations
import re

_KNOWN_PREFIXES = (
    "http://romanrepublic.ac.uk/",
    "http://nomisma.org/",
    "http://numismatics.org/crro/",
    "http://numismatics.org/ocre/",
    "https://edh.ub.uni-heidelberg.de/",
    "http://edh-hd.de/",
    "http://edh-www.adw.uni-heidelberg.de/edh/",
    "https://edh-www.adw.uni-heidelberg.de/edh/",
    "https://pleiades.stoa.org/",
    "http://n2t.net/ark:/99152/",
    "https://rpc.ashmus.ox.ac.uk/",
)

_URI_RE = re.compile(r"https?://[^\s\)\]\",><]+")

def _is_known(uri: str) -> bool:
    return any(uri.startswith(p) for p in _KNOWN_PREFIXES)

def extract_entity_uris(msg_type: str, data: dict) -> set[str]:
    """Return the set of resolvable entity URIs found in a message's data."""
    uris: set[str] = set()
    if msg_type == "query":
        for row in data.get("rows", []):
            for val in row.values():
                if isinstance(val, str) and _is_known(val):
                    uris.add(val)
    elif msg_type == "search":
        for result in data.get("results", []):
            uri = result.get("uri", "")
            if _is_known(uri):
                uris.add(uri)
    elif msg_type == "entity":
        entity_uri = data.get("uri", "")
        if _is_known(entity_uri):
            uris.add(entity_uri)
        for prop in data.get("properties", []):
            obj = prop.get("obj", "")
            if _is_known(obj):
                uris.add(obj)
        for xref in data.get("xrefs", []):
            target = xref.get("target", "")
            if _is_known(target):
                uris.add(target)
    elif msg_type == "links":
        links_uri = data.get("uri", "")
        if _is_known(links_uri):
            uris.add(links_uri)
        for link in data.get("links", []):
            target = link.get("target", "")
            if _is_known(target):
                uris.add(target)
    elif msg_type == "report":
        md = data.get("markdown", "")
        for m in _URI_RE.finditer(md):
            candidate = m.group(0)
            if _is_known(candidate):
                uris.add(candidate)
    return uris
