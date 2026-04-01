"""Pure HTML fragment renderers for the linked-past result feed viewer."""

from __future__ import annotations

import html
from datetime import datetime, timezone

# Predicates commonly used as "name" fields — checked in priority order
_NAME_PREDICATES = (
    "hasPersonName",
    "label",
    "prefLabel",
    "skos:prefLabel",
    "rdfs:label",
    "title",
    "name",
    "foaf:name",
)


def _e(text: str) -> str:
    """HTML-escape a string."""
    return html.escape(str(text))


def render_query_table(rows: list[dict[str, str]], dataset: str) -> str:  # noqa: ARG001
    """Render a list of SPARQL result rows as an HTML table."""
    if not rows:
        return '<p class="table-footer">No results</p>'

    columns = list(rows[0].keys())

    headers = "".join(f"<th>{_e(col)}</th>" for col in columns)
    body_rows = []
    for row in rows:
        cells = "".join(f"<td>{_e(row.get(col, ''))}</td>" for col in columns)
        body_rows.append(f"<tr>{cells}</tr>")

    count = len(rows)
    plural = "s" if count != 1 else ""

    return (
        f'<table class="query-table">'
        f"<thead><tr>{headers}</tr></thead>"
        f"<tbody>{''.join(body_rows)}</tbody>"
        f"</table>"
        f'<div class="table-footer">{count} row{plural}</div>'
    )


def render_entity_card(
    uri: str,
    properties: list[dict[str, str]],
    dataset: str,
    xrefs: list[dict] | None = None,
) -> str:
    """Render an entity as a card with property grid and optional cross-references."""
    # Detect display name from well-known predicates
    name = ""
    for pred in _NAME_PREDICATES:
        for prop in properties:
            if prop.get("pred") == pred:
                name = prop["obj"]
                break
        if name:
            break

    # Fallback: last path/fragment of URI
    if not name:
        name = uri.rstrip("/").rsplit("/", 1)[-1].rsplit("#", 1)[-1]

    badge = f'<span class="dataset-badge" data-ds="{_e(dataset)}">{_e(dataset)}</span>'

    heading = f"<h3>{_e(name)}</h3>"
    subtitle = f'<div class="subtitle">{_e(uri)}</div>'

    # Property grid (skip the predicate used as name to avoid duplication)
    prop_items = []
    for prop in properties:
        pred_local = prop.get("pred", "")
        obj = prop.get("obj", "")
        prop_items.append(f"<dt>{_e(pred_local)}</dt><dd>{_e(obj)}</dd>")

    props_html = (
        f'<dl class="props">{"".join(prop_items)}</dl>' if prop_items else ""
    )

    xrefs_html = ""
    if xrefs:
        xrefs_html = f'<div class="xrefs">{render_xref_list(xrefs)}</div>'

    return (
        f'<div class="entity-card">'
        f"{badge}"
        f"{heading}"
        f"{subtitle}"
        f"{props_html}"
        f"{xrefs_html}"
        f"</div>"
    )


def render_xref_list(links: list[dict]) -> str:
    """Render cross-reference links grouped by confidence level."""
    if not links:
        return ""

    # Group by confidence
    order = ("confirmed", "probable", "candidate")
    groups: dict[str, list[dict]] = {k: [] for k in order}
    for link in links:
        conf = link.get("confidence", "candidate")
        if conf not in groups:
            groups[conf] = []
        groups[conf].append(link)

    parts = []
    for conf in order:
        items = groups.get(conf, [])
        if not items:
            continue
        badge_cls = _e(conf)
        item_htmls = []
        for link in items:
            target = link.get("target", "")
            rel = link.get("relationship", "")
            basis = link.get("basis", "")
            item_htmls.append(
                f'<div class="xref-item">'
                f'<span class="confidence-badge {badge_cls}">{badge_cls}</span>'
                f'<a href="{_e(target)}" target="_blank" rel="noopener">{_e(target)}</a>'
                f'<span style="color:var(--muted);font-size:11px">{_e(rel)}</span>'
                f'<span style="color:var(--muted);font-size:11px">{_e(basis)}</span>'
                f"</div>"
            )
        parts.append(
            f'<div class="xref-group">'
            f'<div class="xref-group-label">{_e(conf)}</div>'
            f"{''.join(item_htmls)}"
            f"</div>"
        )

    return "".join(parts)


def render_generic(text: str) -> str:
    """Render arbitrary text as a preformatted monospace block."""
    return f'<div class="generic-result">{_e(text)}</div>'


def render_feed_item(
    tool_name: str,
    dataset: str | None,
    body_html: str,
) -> str:
    """Wrap an HTML fragment in a collapsible feed item with header."""
    tool_badge = f'<span class="tool-badge">{_e(tool_name)}</span>'

    ds_badge = ""
    if dataset:
        ds_badge = (
            f'<span class="dataset-badge" data-ds="{_e(dataset)}">'
            f"{_e(dataset)}"
            f"</span>"
        )

    now = datetime.now(tz=timezone.utc).strftime("%H:%M:%S")
    timestamp = f'<span class="timestamp">{now}</span>'
    collapse = '<span class="collapse-toggle"></span>'

    header = (
        f'<div class="feed-header">'
        f"{tool_badge}{ds_badge}{timestamp}{collapse}"
        f"</div>"
    )
    body = f'<div class="feed-body">{body_html}</div>'

    return f'<div class="feed-item">{header}{body}</div>'
