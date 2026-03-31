# ShEx Shape Generation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate ShEx-like shape strings from merged schemas + tips and index them in FTS5 for richer context retrieval.

**Architecture:** A single pure function `generate_shex_shapes` in `ontology.py` takes the schemas dict, tips list, and prefix map, returns a dict of class_name → shape string. The search index builder calls it and adds each shape as a `shex_shape` document.

**Tech Stack:** Python, PyYAML (already a dep), SQLite FTS5 (already in use).

---

## File Structure

| File | Responsibility |
|------|----------------|
| `packages/linked-past-store/linked_past_store/ontology.py` | Add `generate_shex_shapes` function |
| `packages/linked-past-store/tests/test_ontology.py` | Tests for shape generation |
| `packages/linked-past/linked_past/core/server.py` | Call `generate_shex_shapes` in `_build_search_index` |

---

### Task 1: Implement `generate_shex_shapes`

**Files:**
- Modify: `packages/linked-past-store/linked_past_store/ontology.py`
- Modify: `packages/linked-past-store/tests/test_ontology.py`

- [ ] **Step 1: Write test**

Add to `packages/linked-past-store/tests/test_ontology.py`:

```python
from linked_past_store.ontology import generate_shex_shapes


def test_generate_shex_shapes_basic():
    schemas = {
        "Person": {
            "label": "Person",
            "comment": "A historical person.",
            "uri": "vocab:Person",
            "properties": [
                {"pred": "vocab:hasName", "range": "xsd:string", "comment": "Full name."},
                {"pred": "vocab:hasOffice", "range": "vocab:Office", "comment": "Office held."},
            ],
        },
        "Office": {
            "label": "Office",
            "comment": "A political office.",
            "uri": "vocab:Office",
            "properties": [
                {"pred": "rdfs:label", "range": "xsd:string", "comment": "Office label."},
            ],
        },
    }
    tips = [
        {"title": "Use COUNT(DISTINCT)", "body": "Always count distinct persons.", "classes": ["Person"]},
    ]
    prefix_map = {"vocab": "http://example.org/"}

    shapes = generate_shex_shapes(schemas, tips, prefix_map)

    assert "Person" in shapes
    assert "Office" in shapes

    person_shape = shapes["Person"]
    assert "vocab:Person {" in person_shape
    assert "vocab:hasName xsd:string" in person_shape
    assert "vocab:hasOffice [ vocab:Office ]" in person_shape
    assert "Full name." in person_shape
    assert "# TIP:" in person_shape
    assert "COUNT(DISTINCT)" in person_shape

    office_shape = shapes["Office"]
    assert "vocab:Office {" in office_shape
    assert "# TIP:" not in office_shape  # no tips reference Office


def test_generate_shex_shapes_no_tips():
    schemas = {
        "Thing": {
            "label": "Thing",
            "uri": "ex:Thing",
            "properties": [
                {"pred": "ex:name", "range": "xsd:string"},
            ],
        },
    }

    shapes = generate_shex_shapes(schemas, [], {})

    assert "Thing" in shapes
    assert "ex:Thing {" in shapes["Thing"]
    assert "ex:name xsd:string" in shapes["Thing"]


def test_generate_shex_shapes_range_types():
    schemas = {
        "Item": {
            "label": "Item",
            "uri": "ex:Item",
            "properties": [
                {"pred": "ex:label", "range": "xsd:string"},
                {"pred": "ex:related", "range": "ex:Other"},
                {"pred": "ex:count", "range": "xsd:integer"},
                {"pred": "ex:noRange"},
            ],
        },
    }

    shapes = generate_shex_shapes(schemas, [], {})
    shape = shapes["Item"]

    assert "ex:label xsd:string" in shape
    assert "ex:related [ ex:Other ]" in shape
    assert "ex:count xsd:integer" in shape
    assert "ex:noRange IRI" in shape  # fallback for missing range
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/linked-past-store/tests/test_ontology.py::test_generate_shex_shapes_basic -v`
Expected: FAIL (ImportError)

- [ ] **Step 3: Implement `generate_shex_shapes`**

Add to `packages/linked-past-store/linked_past_store/ontology.py`:

```python
def generate_shex_shapes(
    schemas: dict,
    tips: list[dict],
    prefix_map: dict[str, str],
) -> dict[str, str]:
    """Generate ShEx-like shape strings from schema classes with inline comments and tips.

    Args:
        schemas: Merged schema dict (class_name -> class_data with properties).
        tips: List of tip dicts with 'title', 'body', 'classes' keys.
        prefix_map: Namespace prefix map (unused for URI shortening here —
                     schemas already use prefixed URIs).

    Returns:
        Dict of class_name -> ShEx-like shape string.
    """
    # Build tip lookup: class_name -> list of tip strings
    tips_by_class: dict[str, list[str]] = {}
    for tip in tips:
        for cls_name in tip.get("classes", []):
            tips_by_class.setdefault(cls_name, []).append(tip["title"])

    shapes: dict[str, str] = {}
    for cls_name, cls_data in schemas.items():
        uri = cls_data.get("uri", cls_name)
        comment = cls_data.get("comment", "")
        properties = cls_data.get("properties", [])

        lines: list[str] = []

        # Class comment
        if comment:
            lines.append(f"# {cls_name}: {comment}")

        # Tips referencing this class
        for tip_title in tips_by_class.get(cls_name, []):
            lines.append(f"# TIP: {tip_title}")

        # Shape header
        lines.append(f"{uri} {{")
        lines.append(f"  a [ {uri} ] ;")

        # Properties
        for prop in properties:
            pred = prop.get("pred", "")
            range_val = prop.get("range", "")
            prop_comment = prop.get("comment", "")

            # Format range: xsd:* types are bare, class references are wrapped in [ ]
            if not range_val:
                range_str = "IRI"
            elif range_val.startswith("xsd:"):
                range_str = range_val
            else:
                range_str = f"[ {range_val} ]"

            line = f"  {pred} {range_str} ;"
            if prop_comment:
                line += f"  # {prop_comment}"
            lines.append(line)

        lines.append("}")

        shapes[cls_name] = "\n".join(lines)

    return shapes
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest packages/linked-past-store/tests/test_ontology.py -k shex -v`
Expected: All 3 PASS

- [ ] **Step 5: Lint and commit**

Run: `uv run ruff check packages/linked-past-store/linked_past_store/ontology.py packages/linked-past-store/tests/test_ontology.py`

```bash
git add packages/linked-past-store/linked_past_store/ontology.py packages/linked-past-store/tests/test_ontology.py
git commit -m "feat: generate_shex_shapes produces ShEx-like shapes with inline comments and tips"
```

---

### Task 2: Index Shapes in Search

**Files:**
- Modify: `packages/linked-past/linked_past/core/server.py`

- [ ] **Step 1: Add shape generation to `_build_search_index`**

In `packages/linked-past/linked_past/core/server.py`, after the schema label/comment indexing block (after line 81), add:

```python
            # Generate and index ShEx-like shapes
            if hasattr(plugin, "_schemas") and hasattr(plugin, "_prefixes"):
                from linked_past_store.ontology import generate_shex_shapes

                plugin_tips = plugin._tips if hasattr(plugin, "_tips") else []
                shapes = generate_shex_shapes(plugin._schemas, plugin_tips, plugin._prefixes)
                for cls_name, shape_text in shapes.items():
                    search.add(name, "shex_shape", shape_text)
```

- [ ] **Step 2: Lint**

Run: `uv run ruff check packages/linked-past/linked_past/core/server.py`

- [ ] **Step 3: Test end-to-end**

```bash
rm -f ~/.local/share/linked-past/search.db
uv run python -c "
from linked_past.core.server import build_app_context
ctx = build_app_context(skip_embeddings=False)
search = ctx.embeddings

# Check shapes are indexed
shape_count = search._conn.execute(\"SELECT COUNT(*) FROM documents WHERE doc_type = 'shex_shape'\").fetchone()[0]
print(f'ShEx shapes indexed: {shape_count}')

# Test search finds shapes
results = search.search('office consul date', k=3)
for r in results:
    if r['doc_type'] == 'shex_shape':
        print(f'Found shape via search:')
        print(r['text'][:300])
        break
"
```

Expected: shapes indexed (one per class per dataset), search for "office consul date" returns a PostAssertion shape.

- [ ] **Step 4: Commit**

```bash
git add packages/linked-past/linked_past/core/server.py
git commit -m "feat: index ShEx shapes in FTS5 search for richer context retrieval"
```
