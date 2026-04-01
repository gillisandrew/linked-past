"""Pure HTML fragment renderers for the linked-past result feed viewer."""

from __future__ import annotations

import html
import re
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


def render_query_table(rows: list[dict[str, str]], dataset: str, sparql: str | None = None) -> str:  # noqa: ARG001
    """Render a list of SPARQL result rows as an HTML table, optionally with the query."""
    sparql_block = ""
    if sparql:
        sparql_block = (
            f'<details class="sparql-details"><summary>SPARQL</summary>'
            f'<pre class="sparql-query">{_e(sparql)}</pre>'
            f"</details>"
        )

    if not rows:
        return sparql_block + '<p class="table-footer">No results</p>'

    columns = list(rows[0].keys())

    headers = "".join(f"<th>{_e(col)}</th>" for col in columns)
    body_rows = []
    for row in rows:
        cells = "".join(f"<td>{_e(row.get(col, ''))}</td>" for col in columns)
        body_rows.append(f"<tr>{cells}</tr>")

    count = len(rows)
    plural = "s" if count != 1 else ""

    return (
        f"{sparql_block}"
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
                f" <code>{_e(target)}</code>"
                f' <span style="color:var(--muted);font-size:11px">{_e(rel)}</span>'
                f' <span style="color:var(--muted);font-size:11px">{_e(basis)}</span>'
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


# ── Markdown to HTML ──────────────────────────────────────────────────────────

_MD_TABLE_ROW = re.compile(r"^\|(.+)\|$")
_MD_SEPARATOR = re.compile(r"^\|[\s:|-]+\|$")


def _md_table_to_html(lines: list[str]) -> str:
    """Convert a markdown table (list of | ... | lines) to an HTML table."""
    if len(lines) < 2:
        return "\n".join(_e(line) for line in lines)

    header_cells = [c.strip() for c in lines[0].strip("|").split("|")]
    header = "".join(f"<th>{_e(c)}</th>" for c in header_cells)

    body_rows = []
    for line in lines[2:]:  # skip header + separator
        cells = [c.strip() for c in line.strip("|").split("|")]
        row = "".join(f"<td>{_md_inline(_e(c))}</td>" for c in cells)
        body_rows.append(f"<tr>{row}</tr>")

    count = len(body_rows)
    plural = "s" if count != 1 else ""
    return (
        f'<table class="query-table">'
        f"<thead><tr>{header}</tr></thead>"
        f"<tbody>{''.join(body_rows)}</tbody>"
        f"</table>"
        f'<div class="table-footer">{count} row{plural}</div>'
    )


def _md_inline(text: str) -> str:
    """Apply inline markdown formatting (bold, italic, code, links) to already-escaped text."""
    # Code spans: `code` → <code>code</code>
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    # Bold: **text** → <strong>text</strong>
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    # Italic: *text* → <em>text</em>
    text = re.sub(r"\*(.+?)\*", r"<em>\1</em>", text)
    # Links: [text](url) → <code>url</code> (safe — no <a href> to avoid XSS)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    return text


def render_markdown(text: str) -> str:
    """Convert markdown text to styled HTML.

    Handles: headings, bold, italic, code spans, fenced code blocks,
    unordered/ordered lists, markdown tables (rendered as styled HTML tables),
    and paragraphs. Designed for LLM-generated markdown — not a full spec parser.
    """
    lines = text.split("\n")
    out: list[str] = []
    i = 0

    while i < len(lines):
        line = lines[i]

        # Fenced code block
        if line.startswith("```"):
            lang = line[3:].strip()
            code_lines = []
            i += 1
            while i < len(lines) and not lines[i].startswith("```"):
                code_lines.append(lines[i])
                i += 1
            i += 1  # skip closing ```
            code_text = _e("\n".join(code_lines))
            cls = f' class="language-{_e(lang)}"' if lang else ""
            out.append(f"<pre><code{cls}>{code_text}</code></pre>")
            continue

        # Markdown table (sequence of | ... | lines)
        if _MD_TABLE_ROW.match(line):
            table_lines = []
            while i < len(lines) and (_MD_TABLE_ROW.match(lines[i]) or _MD_SEPARATOR.match(lines[i])):
                table_lines.append(lines[i])
                i += 1
            out.append(_md_table_to_html(table_lines))
            continue

        # Headings
        if line.startswith("### "):
            out.append(f"<h4>{_md_inline(_e(line[4:]))}</h4>")
            i += 1
            continue
        if line.startswith("## "):
            out.append(f"<h3>{_md_inline(_e(line[3:]))}</h3>")
            i += 1
            continue
        if line.startswith("# "):
            out.append(f"<h2>{_md_inline(_e(line[2:]))}</h2>")
            i += 1
            continue

        # Unordered list
        if re.match(r"^[-*] ", line):
            items = []
            while i < len(lines) and re.match(r"^[-*] ", lines[i]):
                items.append(f"<li>{_md_inline(_e(lines[i][2:]))}</li>")
                i += 1
            out.append(f"<ul>{''.join(items)}</ul>")
            continue

        # Ordered list
        if re.match(r"^\d+\. ", line):
            items = []
            while i < len(lines) and re.match(r"^\d+\. ", lines[i]):
                content = re.sub(r"^\d+\. ", "", lines[i])
                items.append(f"<li>{_md_inline(_e(content))}</li>")
                i += 1
            out.append(f"<ol>{''.join(items)}</ol>")
            continue

        # Blank line
        if not line.strip():
            i += 1
            continue

        # Paragraph
        out.append(f"<p>{_md_inline(_e(line))}</p>")
        i += 1

    return "\n".join(out)
