# dprr-tool Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a CLI tool that converts natural language questions about the Roman Republic into validated SPARQL queries, executes them against a local Oxigraph store, and synthesizes academic prose responses.

**Architecture:** A sequential pipeline of three Claude API calls (extraction, generation, synthesis) with a three-tier validation loop (syntax, semantic, execution) between generation and synthesis. All DPRR schema and example context is injected into every LLM call (no embeddings). Data lives in a local pyoxigraph store.

**Tech Stack:** Python 3.13, pyoxigraph, rdflib, anthropic SDK, click, rich, pyyaml, uv for package management.

---

### Task 1: Project Scaffolding and Dependencies

**Files:**
- Modify: `pyproject.toml`
- Create: `dprr_tool/__init__.py`
- Delete content of: `main.py` (will become CLI entry point later)

**Step 1: Update pyproject.toml with dependencies and package config**

```toml
[project]
name = "dprr-tool"
version = "0.1.0"
description = "Natural language SPARQL queries for the Digital Prosopography of the Roman Republic"
readme = "README.md"
requires-python = ">=3.13"
dependencies = [
    "anthropic",
    "pyoxigraph",
    "rdflib",
    "click",
    "rich",
    "pyyaml",
]

[project.scripts]
dprr-tool = "dprr_tool.cli:cli"

[dependency-groups]
dev = [
    "pytest",
]
```

**Step 2: Create package directory and __init__.py**

```bash
mkdir -p dprr_tool/context tests
```

```python
# dprr_tool/__init__.py
```

(Empty file - just marks it as a package.)

**Step 3: Install dependencies**

Run: `uv sync`
Expected: All dependencies install successfully.

**Step 4: Verify imports work**

Run: `uv run python -c "import pyoxigraph; import rdflib; import anthropic; import click; import rich; import yaml; print('All imports OK')"`
Expected: `All imports OK`

**Step 5: Commit**

```bash
git add pyproject.toml uv.lock dprr_tool/__init__.py
git commit -m "chore: add dependencies and package structure"
```

---

### Task 2: Context Files - Prefixes

**Files:**
- Create: `dprr_tool/context/prefixes.yaml`
- Create: `tests/test_context.py`

**Step 1: Write the failing test**

```python
# tests/test_context.py
from pathlib import Path

import yaml


CONTEXT_DIR = Path(__file__).parent.parent / "dprr_tool" / "context"


def test_prefixes_yaml_loads():
    with open(CONTEXT_DIR / "prefixes.yaml") as f:
        data = yaml.safe_load(f)
    assert "prefixes" in data
    prefixes = data["prefixes"]
    assert "vocab" in prefixes
    assert prefixes["vocab"] == "http://romanrepublic.ac.uk/rdf/entity/vocab/"
    assert "rdfs" in prefixes
    assert "rdf" in prefixes
    assert "xsd" in prefixes
    assert "entity" in prefixes
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_context.py::test_prefixes_yaml_loads -v`
Expected: FAIL (file not found)

**Step 3: Create prefixes.yaml**

```yaml
# dprr_tool/context/prefixes.yaml
prefixes:
  vocab: "http://romanrepublic.ac.uk/rdf/entity/vocab/"
  entity: "http://romanrepublic.ac.uk/rdf/entity/"
  rdfs: "http://www.w3.org/2000/01/rdf-schema#"
  rdf: "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
  xsd: "http://www.w3.org/2001/XMLSchema#"
  owl: "http://www.w3.org/2002/07/owl#"
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_context.py::test_prefixes_yaml_loads -v`
Expected: PASS

**Step 5: Commit**

```bash
git add dprr_tool/context/prefixes.yaml tests/test_context.py
git commit -m "feat: add DPRR prefix map"
```

---

### Task 3: Context Files - Schemas

The schemas describe every DPRR class and its valid predicates. This is the foundation for both LLM context injection and semantic validation.

**Reference:** The DPRR ontology uses namespace `http://romanrepublic.ac.uk/rdf/entity/vocab/`. The classes and properties are documented in the design doc under "Key DPRR Domain Notes" and were researched from the OWL ontology at `http://romanrepublic.ac.uk/rdf/ontology` and the Django models in `kingsdigitallab/dprr-django`.

**Files:**
- Create: `dprr_tool/context/schemas.yaml`
- Modify: `tests/test_context.py`

**Step 1: Write the failing test**

Append to `tests/test_context.py`:

```python
def test_schemas_yaml_loads():
    with open(CONTEXT_DIR / "schemas.yaml") as f:
        data = yaml.safe_load(f)
    assert "classes" in data
    classes = data["classes"]

    # Core classes must exist
    for cls_name in [
        "Person", "PostAssertion", "RelationshipAssertion",
        "StatusAssertion", "DateInformation", "Office",
        "Province", "Sex", "Praenomen", "Tribe",
        "SecondarySource", "PrimarySource", "Status",
        "Relationship", "DateType",
    ]:
        assert cls_name in classes, f"Missing class: {cls_name}"

    # Each class must have label, uri, and properties
    for cls_name, cls_data in classes.items():
        assert "label" in cls_data, f"{cls_name} missing label"
        assert "uri" in cls_data, f"{cls_name} missing uri"
        assert "properties" in cls_data, f"{cls_name} missing properties"
        assert len(cls_data["properties"]) > 0, f"{cls_name} has no properties"

        # Each property must have pred and range
        for prop in cls_data["properties"]:
            assert "pred" in prop, f"{cls_name} property missing pred"
            assert "range" in prop, f"{cls_name} property missing range"


def test_schemas_person_has_key_properties():
    with open(CONTEXT_DIR / "schemas.yaml") as f:
        data = yaml.safe_load(f)
    person = data["classes"]["Person"]
    preds = [p["pred"] for p in person["properties"]]
    assert "rdfs:label" in preds
    assert "vocab:hasDprrID" in preds
    assert "vocab:hasNomen" in preds
    assert "vocab:hasCognomen" in preds
    assert "vocab:isSex" in preds
    assert "vocab:hasEraFrom" in preds
    assert "vocab:hasEraTo" in preds
    assert "vocab:isPatrician" in preds


def test_schemas_post_assertion_has_key_properties():
    with open(CONTEXT_DIR / "schemas.yaml") as f:
        data = yaml.safe_load(f)
    pa = data["classes"]["PostAssertion"]
    preds = [p["pred"] for p in pa["properties"]]
    assert "vocab:isAboutPerson" in preds
    assert "vocab:hasOffice" in preds
    assert "vocab:hasDateStart" in preds
    assert "vocab:hasDateEnd" in preds
    assert "vocab:hasSecondarySource" in preds
    assert "vocab:isUncertain" in preds
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_context.py -k schemas -v`
Expected: FAIL (file not found)

**Step 3: Create schemas.yaml**

This file must be comprehensive - it's the single source of truth for both LLM context and semantic validation. Build it from the OWL ontology and Django models documented in the design research.

```yaml
# dprr_tool/context/schemas.yaml
#
# DPRR ontology schema for LLM context injection and semantic validation.
# Namespace: http://romanrepublic.ac.uk/rdf/entity/vocab/
# All predicates use the "vocab:" prefix unless otherwise noted.
# Dates are xsd:integer where negative values = BC.
classes:
  Person:
    label: "Roman Republican Person"
    comment: "An individual in the DPRR database, spanning 509-31 BC. Properties are stored directly on the Person entity for core identification, but office-holding, status, and relationships are stored via assertion classes."
    uri: "vocab:Person"
    properties:
      - pred: "rdfs:label"
        range: "xsd:string"
        comment: "Full Roman name (e.g., 'L. Cornelius Scipio Africanus')"
      - pred: "vocab:hasDprrID"
        range: "xsd:string"
        comment: "DPRR identifier string (e.g., 'CORN0174')"
      - pred: "vocab:hasID"
        range: "xsd:integer"
        comment: "Numeric database ID"
      - pred: "vocab:hasPraenomen"
        range: "vocab:Praenomen"
        comment: "Links to a Praenomen entity (e.g., Lucius, Gaius)"
      - pred: "vocab:hasAltPraenomen"
        range: "vocab:Praenomen"
        comment: "Alternative praenomen if known"
      - pred: "vocab:hasNomen"
        range: "xsd:string"
        comment: "Family/gens name (e.g., 'Cornelius')"
      - pred: "vocab:hasCognomen"
        range: "xsd:string"
        comment: "Third name / cognomen (e.g., 'Scipio')"
      - pred: "vocab:hasOtherNames"
        range: "xsd:string"
        comment: "Additional name elements"
      - pred: "vocab:hasFiliation"
        range: "xsd:string"
        comment: "Descent notation (e.g., 'M. f.' = son of Marcus)"
      - pred: "vocab:isSex"
        range: "vocab:Sex"
        comment: "Links to Sex/Male or Sex/Female entity"
      - pred: "vocab:hasEraFrom"
        range: "xsd:integer"
        comment: "Estimated birth/floruit start year (negative = BC)"
      - pred: "vocab:hasEraTo"
        range: "xsd:integer"
        comment: "Estimated death/floruit end year (negative = BC)"
      - pred: "vocab:hasHighestOffice"
        range: "xsd:string"
        comment: "Highest office attained (string, e.g., 'Consul')"
      - pred: "vocab:hasOrigin"
        range: "xsd:string"
        comment: "Geographic origin if known"
      - pred: "vocab:isPatrician"
        range: "xsd:boolean"
      - pred: "vocab:isNobilis"
        range: "xsd:boolean"
      - pred: "vocab:isNovus"
        range: "xsd:boolean"
        comment: "Novus homo (new man) - first in family to reach consulship"
      - pred: "vocab:hasReNumber"
        range: "xsd:string"
        comment: "Pauly-Wissowa RE encyclopedia reference number"
      - pred: "vocab:hasPersonNote"
        range: "vocab:PersonNote"
      - pred: "vocab:isPraenomenUncertain"
        range: "xsd:boolean"
      - pred: "vocab:isNomenUncertain"
        range: "xsd:boolean"
      - pred: "vocab:isCognomenUncertain"
        range: "xsd:boolean"
      - pred: "vocab:isReNumberUncertain"
        range: "xsd:boolean"

  PostAssertion:
    label: "Office-Holding Assertion"
    comment: "A claim from a secondary source that a person held a specific Roman office during a date range. This is the main way office data is stored - not directly on Person."
    uri: "vocab:PostAssertion"
    properties:
      - pred: "vocab:isAboutPerson"
        range: "vocab:Person"
        comment: "The person who held the office"
      - pred: "vocab:hasOffice"
        range: "vocab:Office"
        comment: "The office held (e.g., consul, praetor, quaestor)"
      - pred: "vocab:hasDateStart"
        range: "xsd:integer"
        comment: "Start year of office tenure (negative = BC)"
      - pred: "vocab:hasDateEnd"
        range: "xsd:integer"
        comment: "End year of office tenure (negative = BC)"
      - pred: "vocab:hasSecondarySource"
        range: "vocab:SecondarySource"
        comment: "The scholarly source for this assertion"
      - pred: "vocab:isUncertain"
        range: "xsd:boolean"
        comment: "Whether this office-holding is uncertain"
      - pred: "vocab:isDateStartUncertain"
        range: "xsd:boolean"
      - pred: "vocab:isDateEndUncertain"
        range: "xsd:boolean"
      - pred: "vocab:hasPostAssertionNote"
        range: "vocab:PostAssertionNote"
      - pred: "vocab:hasOriginalText"
        range: "xsd:string"
        comment: "Original text from the source"

  RelationshipAssertion:
    label: "Family Relationship Assertion"
    comment: "A claim that two persons are related (e.g., father-son, husband-wife). Links two Person entities via a RelationshipType."
    uri: "vocab:RelationshipAssertion"
    properties:
      - pred: "vocab:isAboutPerson"
        range: "vocab:Person"
        comment: "The primary person in the relationship"
      - pred: "vocab:hasRelatedPerson"
        range: "vocab:Person"
        comment: "The other person in the relationship"
      - pred: "vocab:hasRelationship"
        range: "vocab:Relationship"
        comment: "The type of relationship (e.g., Father of, Wife of)"
      - pred: "vocab:hasSecondarySource"
        range: "vocab:SecondarySource"
      - pred: "vocab:isUncertain"
        range: "xsd:boolean"

  StatusAssertion:
    label: "Social Status Assertion"
    comment: "A claim that a person held a particular social status (e.g., Eques Romanus, Nobilis) during a date range."
    uri: "vocab:StatusAssertion"
    properties:
      - pred: "vocab:isAboutPerson"
        range: "vocab:Person"
      - pred: "vocab:hasStatus"
        range: "vocab:Status"
        comment: "The status type (e.g., Eques R., Nobilis)"
      - pred: "vocab:hasDateStart"
        range: "xsd:integer"
      - pred: "vocab:hasDateEnd"
        range: "xsd:integer"
      - pred: "vocab:hasSecondarySource"
        range: "vocab:SecondarySource"
      - pred: "vocab:isUncertain"
        range: "xsd:boolean"
      - pred: "vocab:isDateStartUncertain"
        range: "xsd:boolean"
      - pred: "vocab:isDateEndUncertain"
        range: "xsd:boolean"

  DateInformation:
    label: "Date Information"
    comment: "A specific life event date for a person (birth, death, exile, etc.)."
    uri: "vocab:DateInformation"
    properties:
      - pred: "vocab:isAboutPerson"
        range: "vocab:Person"
      - pred: "vocab:hasDateType"
        range: "vocab:DateType"
        comment: "Type of date event (Birth, Death, Exile, etc.)"
      - pred: "vocab:hasValue"
        range: "xsd:integer"
        comment: "The year value (negative = BC)"
      - pred: "vocab:hasDateInterval"
        range: "xsd:string"
        comment: "Temporal qualifier: S=Single/exact, B=Before, A=After"
      - pred: "vocab:hasSecondarySource"
        range: "vocab:SecondarySource"
      - pred: "vocab:isUncertain"
        range: "xsd:boolean"
      - pred: "vocab:hasSourceText"
        range: "xsd:string"

  TribeAssertion:
    label: "Tribe Membership Assertion"
    comment: "A claim that a person belonged to a particular Roman tribe."
    uri: "vocab:TribeAssertion"
    properties:
      - pred: "vocab:isAboutPerson"
        range: "vocab:Person"
      - pred: "vocab:hasTribe"
        range: "vocab:Tribe"
      - pred: "vocab:hasSecondarySource"
        range: "vocab:SecondarySource"
      - pred: "vocab:isUncertain"
        range: "xsd:boolean"

  Office:
    label: "Roman Office"
    comment: "A Roman state or religious position (e.g., Consul, Praetor, Quaestor, Pontifex). Offices are hierarchical - use hasParent for the parent category."
    uri: "vocab:Office"
    properties:
      - pred: "rdfs:label"
        range: "xsd:string"
        comment: "Office name (e.g., 'Consul', 'Praetor')"
      - pred: "vocab:hasID"
        range: "xsd:integer"
      - pred: "vocab:hasAbbrevName"
        range: "xsd:string"
        comment: "Abbreviated name"
      - pred: "vocab:hasDescription"
        range: "xsd:string"
      - pred: "vocab:hasParent"
        range: "vocab:Office"
        comment: "Parent office in hierarchy"

  Province:
    label: "Roman Province"
    comment: "A Roman administrative jurisdiction. Provinces are hierarchical."
    uri: "vocab:Province"
    properties:
      - pred: "rdfs:label"
        range: "xsd:string"
      - pred: "vocab:hasID"
        range: "xsd:integer"
      - pred: "vocab:hasDescription"
        range: "xsd:string"
      - pred: "vocab:hasParent"
        range: "vocab:Province"
        comment: "Parent province in hierarchy"

  Sex:
    label: "Sex/Gender"
    comment: "Gender entity. Two instances: Sex/Male and Sex/Female. Linked from Person via vocab:isSex."
    uri: "vocab:Sex"
    properties:
      - pred: "rdfs:label"
        range: "xsd:string"

  Praenomen:
    label: "Praenomen (First Name)"
    comment: "A Roman first name (e.g., Lucius, Gaius, Marcus). Linked from Person via vocab:hasPraenomen."
    uri: "vocab:Praenomen"
    properties:
      - pred: "rdfs:label"
        range: "xsd:string"
      - pred: "vocab:hasAbbrevName"
        range: "xsd:string"
        comment: "Abbreviated form (e.g., 'L.' for Lucius)"

  Tribe:
    label: "Roman Tribe"
    comment: "One of the Roman tribal groupings."
    uri: "vocab:Tribe"
    properties:
      - pred: "rdfs:label"
        range: "xsd:string"
      - pred: "vocab:hasAbbrevName"
        range: "xsd:string"

  SecondarySource:
    label: "Secondary Source"
    comment: "A modern scholarly source (e.g., Broughton MRR, Rupke FS, Zmeskal Adf)."
    uri: "vocab:SecondarySource"
    properties:
      - pred: "rdfs:label"
        range: "xsd:string"
      - pred: "vocab:hasAbbrevName"
        range: "xsd:string"
        comment: "Short citation form"
      - pred: "vocab:hasBiblio"
        range: "xsd:string"
        comment: "Full bibliographic reference"

  PrimarySource:
    label: "Primary Source"
    comment: "An ancient textual source (e.g., Livy, Cicero)."
    uri: "vocab:PrimarySource"
    properties:
      - pred: "rdfs:label"
        range: "xsd:string"
      - pred: "vocab:hasAbbrevName"
        range: "xsd:string"
      - pred: "vocab:hasBiblio"
        range: "xsd:string"

  Status:
    label: "Social Status Type"
    comment: "A social status category (e.g., Eques Romanus, Nobilis, Novus Homo)."
    uri: "vocab:Status"
    properties:
      - pred: "rdfs:label"
        range: "xsd:string"
      - pred: "vocab:hasAbbrevName"
        range: "xsd:string"
      - pred: "vocab:hasDescription"
        range: "xsd:string"

  Relationship:
    label: "Relationship Type"
    comment: "A family relationship type (e.g., Father of, Son of, Wife of, Brother of)."
    uri: "vocab:Relationship"
    properties:
      - pred: "rdfs:label"
        range: "xsd:string"
      - pred: "vocab:hasDescription"
        range: "xsd:string"

  DateType:
    label: "Date Event Type"
    comment: "Category of life event (e.g., Birth, Death, Exile, Return from Exile)."
    uri: "vocab:DateType"
    properties:
      - pred: "rdfs:label"
        range: "xsd:string"
      - pred: "vocab:hasDescription"
        range: "xsd:string"
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_context.py -k schemas -v`
Expected: All 3 tests PASS

**Step 5: Commit**

```bash
git add dprr_tool/context/schemas.yaml tests/test_context.py
git commit -m "feat: add DPRR ontology schema definitions"
```

---

### Task 4: Context Files - Example Queries

**Files:**
- Create: `dprr_tool/context/examples.yaml`
- Modify: `tests/test_context.py`

**Step 1: Write the failing test**

Append to `tests/test_context.py`:

```python
def test_examples_yaml_loads():
    with open(CONTEXT_DIR / "examples.yaml") as f:
        data = yaml.safe_load(f)
    assert "examples" in data
    examples = data["examples"]
    assert len(examples) >= 15, f"Expected at least 15 examples, got {len(examples)}"

    for i, ex in enumerate(examples):
        assert "question" in ex, f"Example {i} missing question"
        assert "sparql" in ex, f"Example {i} missing sparql"
        assert "PREFIX" in ex["sparql"] or "prefix" in ex["sparql"], (
            f"Example {i} SPARQL missing PREFIX declaration"
        )


def test_examples_cover_key_patterns():
    with open(CONTEXT_DIR / "examples.yaml") as f:
        data = yaml.safe_load(f)
    questions = [ex["question"].lower() for ex in data["examples"]]
    all_questions = " ".join(questions)

    # Must cover the core research patterns
    assert any("consul" in q for q in questions), "Missing consul/office query example"
    assert any("woman" in q or "female" in q for q in questions), "Missing gender query example"
    assert any("family" in q or "relationship" in q or "father" in q or "relative" in q for q in questions), "Missing relationship query example"
    assert any("patrician" in q or "status" in q or "nobil" in q for q in questions), "Missing status query example"
    assert any("tribe" in q for q in questions), "Missing tribe query example"
    assert any("province" in q for q in questions), "Missing province query example"
    assert any("uncertain" in q for q in questions), "Missing uncertainty query example"
    assert any("source" in q for q in questions), "Missing source citation query example"
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_context.py -k examples -v`
Expected: FAIL (file not found)

**Step 3: Create examples.yaml**

Create `dprr_tool/context/examples.yaml` with at least 20 curated SPARQL queries. Each example must have `question` and `sparql` fields. The queries should use `PREFIX vocab: <http://romanrepublic.ac.uk/rdf/entity/vocab/>` and `PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>`.

Cover these patterns:
1. Office-holding by date range (consul, praetor, quaestor, tribune)
2. Persons by gender
3. Family relationships for a person
4. Status queries (patrician, nobilis, eques)
5. Tribe membership
6. Office-holding in a province
7. Uncertain assertions
8. Source citations
9. Date information (birth, death)
10. Office hierarchy
11. Person lookup by name/nomen
12. Counting/aggregation queries
13. Persons active in a date range (hasEraFrom/hasEraTo)
14. Combined filters (e.g., patrician consuls)
15. Relationship type queries

**Important SPARQL conventions for examples:**
- Use `vocab:` prefix for all DPRR properties
- Entity URIs: `<http://romanrepublic.ac.uk/rdf/entity/{Type}/{ID}>`
- Known entity IRIs for filters: `<http://romanrepublic.ac.uk/rdf/entity/Sex/Female>`, `<http://romanrepublic.ac.uk/rdf/entity/Sex/Male>`
- Negative integers for BC dates in FILTERs
- Always use `DISTINCT` and `LIMIT 100` where appropriate
- Include `ORDER BY` for readable results

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_context.py -k examples -v`
Expected: All 2 tests PASS

**Step 5: Commit**

```bash
git add dprr_tool/context/examples.yaml tests/test_context.py
git commit -m "feat: add curated SPARQL example queries"
```

---

### Task 5: Context Loader Module

A module that loads the YAML context files and renders them into prompt-ready text.

**Files:**
- Create: `dprr_tool/context/__init__.py`
- Create: `tests/test_context_loader.py`

**Step 1: Write the failing tests**

```python
# tests/test_context_loader.py
from dprr_tool.context import load_prefixes, load_schemas, load_examples, render_schemas_as_shex, render_examples


def test_load_prefixes():
    prefixes = load_prefixes()
    assert isinstance(prefixes, dict)
    assert prefixes["vocab"] == "http://romanrepublic.ac.uk/rdf/entity/vocab/"
    assert "rdfs" in prefixes


def test_load_schemas():
    schemas = load_schemas()
    assert "Person" in schemas
    assert "PostAssertion" in schemas
    assert "uri" in schemas["Person"]
    assert len(schemas["Person"]["properties"]) > 5


def test_load_examples():
    examples = load_examples()
    assert isinstance(examples, list)
    assert len(examples) >= 15
    assert "question" in examples[0]
    assert "sparql" in examples[0]


def test_render_schemas_as_shex():
    schemas = load_schemas()
    text = render_schemas_as_shex(schemas)
    assert "vocab:Person" in text
    assert "vocab:hasDprrID" in text
    assert "vocab:PostAssertion" in text
    assert "vocab:hasOffice" in text
    # Should contain ShEx-style formatting
    assert "{" in text
    assert "}" in text


def test_render_examples():
    examples = load_examples()
    text = render_examples(examples)
    assert "PREFIX" in text
    assert "SELECT" in text
    # Each example should have the question as a header
    assert examples[0]["question"] in text
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_context_loader.py -v`
Expected: FAIL (cannot import)

**Step 3: Implement the context loader**

```python
# dprr_tool/context/__init__.py
from pathlib import Path

import yaml

_CONTEXT_DIR = Path(__file__).parent


def load_prefixes() -> dict[str, str]:
    """Load the DPRR prefix map from prefixes.yaml."""
    with open(_CONTEXT_DIR / "prefixes.yaml") as f:
        return yaml.safe_load(f)["prefixes"]


def load_schemas() -> dict:
    """Load the DPRR class schemas from schemas.yaml. Returns the 'classes' dict."""
    with open(_CONTEXT_DIR / "schemas.yaml") as f:
        return yaml.safe_load(f)["classes"]


def load_examples() -> list[dict]:
    """Load the curated SPARQL examples from examples.yaml."""
    with open(_CONTEXT_DIR / "examples.yaml") as f:
        return yaml.safe_load(f)["examples"]


def render_schemas_as_shex(schemas: dict) -> str:
    """Render the schema dict as ShEx-style text for LLM context injection."""
    sections = []
    for cls_name, cls_data in schemas.items():
        lines = []
        comment = cls_data.get("comment", "")
        if comment:
            lines.append(f"# {cls_data['label']}: {comment}")
        lines.append(f"{cls_data['uri']} {{")
        for prop in cls_data["properties"]:
            prop_comment = prop.get("comment", "")
            suffix = f"  # {prop_comment}" if prop_comment else ""
            lines.append(f"  {prop['pred']} [ {prop['range']} ] ;{suffix}")
        lines.append("}")
        sections.append("\n".join(lines))
    return "\n\n".join(sections)


def render_examples(examples: list[dict]) -> str:
    """Render the example queries as formatted text for LLM context injection."""
    sections = []
    for ex in examples:
        section = f"Question: {ex['question']}\n\n```sparql\n{ex['sparql'].strip()}\n```"
        sections.append(section)
    return "\n\n---\n\n".join(sections)
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_context_loader.py -v`
Expected: All 5 tests PASS

**Step 5: Commit**

```bash
git add dprr_tool/context/__init__.py tests/test_context_loader.py
git commit -m "feat: add context loader with ShEx and example rendering"
```

---

### Task 6: Oxigraph Store Module

**Files:**
- Create: `dprr_tool/store.py`
- Create: `tests/test_store.py`

**Step 1: Write the failing tests**

```python
# tests/test_store.py
import tempfile
from pathlib import Path

from dprr_tool.store import get_or_create_store, load_rdf, execute_query, is_initialized


SAMPLE_TURTLE = """\
@prefix vocab: <http://romanrepublic.ac.uk/rdf/entity/vocab/> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
@prefix entity: <http://romanrepublic.ac.uk/rdf/entity/> .

entity:Person/1 a vocab:Person ;
    rdfs:label "L. Iunius Brutus" ;
    vocab:hasDprrID "IUNI0001" ;
    vocab:hasNomen "Iunius" ;
    vocab:hasCognomen "Brutus" ;
    vocab:isSex entity:Sex/Male ;
    vocab:hasEraFrom "-509"^^xsd:integer ;
    vocab:hasEraTo "-509"^^xsd:integer .

entity:Person/2 a vocab:Person ;
    rdfs:label "L. Tarquinius Collatinus" ;
    vocab:hasDprrID "TARQ0001" ;
    vocab:hasNomen "Tarquinius" ;
    vocab:hasCognomen "Collatinus" ;
    vocab:isSex entity:Sex/Male .

entity:PostAssertion/1 a vocab:PostAssertion ;
    vocab:isAboutPerson entity:Person/1 ;
    vocab:hasOffice entity:Office/3 ;
    vocab:hasDateStart "-509"^^xsd:integer ;
    vocab:hasDateEnd "-509"^^xsd:integer .

entity:PostAssertion/2 a vocab:PostAssertion ;
    vocab:isAboutPerson entity:Person/2 ;
    vocab:hasOffice entity:Office/3 ;
    vocab:hasDateStart "-509"^^xsd:integer ;
    vocab:hasDateEnd "-509"^^xsd:integer .

entity:Office/3 a vocab:Office ;
    rdfs:label "Consul" .

entity:Sex/Male a vocab:Sex ;
    rdfs:label "Male" .
"""


def test_get_or_create_store():
    with tempfile.TemporaryDirectory() as tmpdir:
        store_path = Path(tmpdir) / "store"
        store = get_or_create_store(store_path)
        assert store is not None


def test_load_rdf_returns_triple_count():
    with tempfile.TemporaryDirectory() as tmpdir:
        store_path = Path(tmpdir) / "store"
        store = get_or_create_store(store_path)
        ttl_path = Path(tmpdir) / "test.ttl"
        ttl_path.write_text(SAMPLE_TURTLE)
        count = load_rdf(store, ttl_path)
        assert count > 0


def test_execute_query_returns_results():
    with tempfile.TemporaryDirectory() as tmpdir:
        store_path = Path(tmpdir) / "store"
        store = get_or_create_store(store_path)
        ttl_path = Path(tmpdir) / "test.ttl"
        ttl_path.write_text(SAMPLE_TURTLE)
        load_rdf(store, ttl_path)

        results = execute_query(
            store,
            """
            PREFIX vocab: <http://romanrepublic.ac.uk/rdf/entity/vocab/>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            SELECT ?person ?name WHERE {
                ?person a vocab:Person ;
                    rdfs:label ?name .
            }
            ORDER BY ?name
            """,
        )
        assert len(results) == 2
        assert results[0]["name"] == "L. Iunius Brutus"
        assert results[1]["name"] == "L. Tarquinius Collatinus"


def test_execute_query_empty_results():
    with tempfile.TemporaryDirectory() as tmpdir:
        store_path = Path(tmpdir) / "store"
        store = get_or_create_store(store_path)
        ttl_path = Path(tmpdir) / "test.ttl"
        ttl_path.write_text(SAMPLE_TURTLE)
        load_rdf(store, ttl_path)

        results = execute_query(
            store,
            """
            PREFIX vocab: <http://romanrepublic.ac.uk/rdf/entity/vocab/>
            SELECT ?person WHERE {
                ?person a vocab:Person ;
                    vocab:hasNomen "Nonexistent" .
            }
            """,
        )
        assert results == []


def test_is_initialized():
    with tempfile.TemporaryDirectory() as tmpdir:
        store_path = Path(tmpdir) / "store"
        assert not is_initialized(store_path)
        store = get_or_create_store(store_path)
        ttl_path = Path(tmpdir) / "test.ttl"
        ttl_path.write_text(SAMPLE_TURTLE)
        load_rdf(store, ttl_path)
        assert is_initialized(store_path)
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_store.py -v`
Expected: FAIL (cannot import)

**Step 3: Implement the store module**

```python
# dprr_tool/store.py
from pathlib import Path

from pyoxigraph import Store, RdfFormat


def get_or_create_store(path: Path) -> Store:
    """Open or create a persistent Oxigraph store at the given directory."""
    path.mkdir(parents=True, exist_ok=True)
    return Store(str(path))


def load_rdf(store: Store, file_path: Path) -> int:
    """Bulk-load a Turtle RDF file into the store. Returns the number of triples after loading."""
    store.bulk_load(
        path=str(file_path),
        format=RdfFormat.TURTLE,
    )
    return len(store)


def execute_query(store: Store, sparql: str) -> list[dict[str, str]]:
    """Execute a SPARQL SELECT query and return results as a list of dicts.

    Each dict maps variable name to its string value.
    """
    results = store.query(sparql)
    variables = [v.value for v in results.variables]
    rows = []
    for solution in results:
        row = {}
        for var_name in variables:
            value = solution[var_name]
            if value is not None:
                row[var_name] = value.value
            else:
                row[var_name] = None
        rows.append(row)
    return rows


def is_initialized(store_path: Path) -> bool:
    """Check whether a store exists and contains data."""
    if not store_path.exists():
        return False
    try:
        store = Store(str(store_path))
        return len(store) > 0
    except OSError:
        return False
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_store.py -v`
Expected: All 5 tests PASS

**Step 5: Commit**

```bash
git add dprr_tool/store.py tests/test_store.py
git commit -m "feat: add Oxigraph store wrapper module"
```

---

### Task 7: Validation - Tier 1: Syntax Parsing and Prefix Repair

**Files:**
- Create: `dprr_tool/validate.py`
- Create: `tests/test_validate.py`

**Step 1: Write the failing tests**

```python
# tests/test_validate.py
from dprr_tool.validate import parse_and_fix_prefixes
from dprr_tool.context import load_prefixes


PREFIXES = load_prefixes()


def test_parse_valid_query():
    sparql = """\
PREFIX vocab: <http://romanrepublic.ac.uk/rdf/entity/vocab/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT ?person ?name WHERE {
    ?person a vocab:Person ;
        rdfs:label ?name .
}"""
    fixed, errors = parse_and_fix_prefixes(sparql, PREFIXES)
    assert errors == []
    assert fixed == sparql  # No changes needed


def test_parse_fixes_missing_prefix():
    # Missing vocab: prefix declaration
    sparql = """\
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT ?person ?name WHERE {
    ?person a vocab:Person ;
        rdfs:label ?name .
}"""
    fixed, errors = parse_and_fix_prefixes(sparql, PREFIXES)
    assert errors == []
    assert "PREFIX vocab:" in fixed
    assert "vocab:Person" in fixed


def test_parse_fixes_multiple_missing_prefixes():
    sparql = """\
SELECT ?person ?name WHERE {
    ?person a vocab:Person ;
        rdfs:label ?name .
}"""
    fixed, errors = parse_and_fix_prefixes(sparql, PREFIXES)
    assert errors == []
    assert "PREFIX vocab:" in fixed
    assert "PREFIX rdfs:" in fixed


def test_parse_returns_syntax_error():
    sparql = "SELCT ?person WHERE { ?person ?p ?o }"
    fixed, errors = parse_and_fix_prefixes(sparql, PREFIXES)
    assert len(errors) > 0
    assert "syntax" in errors[0].lower() or "expected" in errors[0].lower() or "parse" in errors[0].lower()


def test_parse_preserves_comments():
    sparql = """\
# Find all persons
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT ?name WHERE {
    ?person a vocab:Person ;
        rdfs:label ?name .
}"""
    fixed, errors = parse_and_fix_prefixes(sparql, PREFIXES)
    assert errors == []
    assert "# Find all persons" in fixed
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_validate.py -v`
Expected: FAIL (cannot import)

**Step 3: Implement Tier 1 validation**

```python
# dprr_tool/validate.py
import re

from pyparsing import ParseException
from rdflib.plugins.sparql import prepareQuery


def parse_and_fix_prefixes(
    sparql: str, prefix_map: dict[str, str]
) -> tuple[str, list[str]]:
    """Parse a SPARQL query, auto-fixing missing PREFIX declarations.

    Returns (fixed_sparql, errors). If errors is empty, the query is syntactically valid.
    """
    try:
        prepareQuery(sparql)
        return sparql, []
    except Exception as e:
        if "Unknown namespace prefix" not in str(e):
            # Not a prefix error - try to give a useful message
            try:
                prepareQuery(sparql)
            except ParseException as pe:
                return sparql, [f"SPARQL syntax error at line {pe.lineno}, column {pe.column}: {pe}"]
            except Exception:
                pass
            return sparql, [f"SPARQL error: {e}"]

    # It's a missing prefix error - fix it and retry
    fixed = _insert_missing_prefixes(sparql, prefix_map)

    try:
        prepareQuery(fixed)
        return fixed, []
    except ParseException as pe:
        return fixed, [f"SPARQL syntax error at line {pe.lineno}, column {pe.column}: {pe}"]
    except Exception as e:
        if "Unknown namespace prefix" in str(e):
            # Still missing a prefix we don't know about
            prefix = str(e).split("Unknown namespace prefix : ")[-1]
            return fixed, [f"Unknown prefix '{prefix}' is not in the DPRR prefix map"]
        return fixed, [f"SPARQL error: {e}"]


def _insert_missing_prefixes(sparql: str, prefix_map: dict[str, str]) -> str:
    """Scan the query for prefix usage and insert missing PREFIX declarations."""
    # Split into comment lines at the top and the rest
    lines = sparql.split("\n")
    comment_lines = []
    rest_lines = []
    in_comments = True
    for line in lines:
        stripped = line.strip()
        if in_comments and stripped.startswith("#"):
            comment_lines.append(line)
        else:
            in_comments = False
            rest_lines.append(line)

    rest = "\n".join(rest_lines)

    # Find which prefixes are already declared
    declared = set(re.findall(r"PREFIX\s+(\w+)\s*:", rest, re.IGNORECASE))

    # Find which prefixes are used in the query body
    used = set()
    for prefix in prefix_map:
        # Match prefix usage: word boundary or common delimiters before prefix:
        if re.search(rf"(?:^|[\s(,/|]){re.escape(prefix)}:", rest):
            used.add(prefix)

    # Insert missing declarations
    missing = used - declared
    if missing:
        prefix_decls = []
        for prefix in sorted(missing):
            prefix_decls.append(f"PREFIX {prefix}: <{prefix_map[prefix]}>")
        rest = "\n".join(prefix_decls) + "\n" + rest

    if comment_lines:
        return "\n".join(comment_lines) + "\n" + rest
    return rest
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_validate.py -v`
Expected: All 5 tests PASS

**Step 5: Commit**

```bash
git add dprr_tool/validate.py tests/test_validate.py
git commit -m "feat: add SPARQL syntax validation with automatic prefix repair"
```

---

### Task 8: Validation - Tier 2: Semantic Validation

**Files:**
- Modify: `dprr_tool/validate.py`
- Modify: `tests/test_validate.py`

**Step 1: Write the failing tests**

Append to `tests/test_validate.py`:

```python
from dprr_tool.validate import build_schema_dict, validate_semantics
from dprr_tool.context import load_schemas, load_prefixes


def _make_schema_dict():
    return build_schema_dict(load_schemas(), load_prefixes())


def test_build_schema_dict():
    sd = _make_schema_dict()
    person_uri = "http://romanrepublic.ac.uk/rdf/entity/vocab/Person"
    assert person_uri in sd
    nomen_uri = "http://romanrepublic.ac.uk/rdf/entity/vocab/hasNomen"
    assert nomen_uri in sd[person_uri]


def test_validate_semantics_valid_query():
    sd = _make_schema_dict()
    sparql = """\
PREFIX vocab: <http://romanrepublic.ac.uk/rdf/entity/vocab/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT ?person ?name WHERE {
    ?person a vocab:Person ;
        rdfs:label ?name ;
        vocab:hasNomen "Cornelius" .
}"""
    errors = validate_semantics(sparql, sd)
    assert errors == []


def test_validate_semantics_invalid_predicate():
    sd = _make_schema_dict()
    # vocab:hasOffice is not a valid predicate on vocab:Person
    sparql = """\
PREFIX vocab: <http://romanrepublic.ac.uk/rdf/entity/vocab/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT ?person WHERE {
    ?person a vocab:Person ;
        vocab:hasOffice ?office .
}"""
    errors = validate_semantics(sparql, sd)
    assert len(errors) > 0
    assert "hasOffice" in errors[0]
    # Should include valid alternatives
    assert "hasNomen" in errors[0] or "Valid predicates" in errors[0]


def test_validate_semantics_invalid_class():
    sd = _make_schema_dict()
    sparql = """\
PREFIX vocab: <http://romanrepublic.ac.uk/rdf/entity/vocab/>
SELECT ?x WHERE {
    ?x a vocab:NonexistentClass .
}"""
    errors = validate_semantics(sparql, sd)
    assert len(errors) > 0
    assert "NonexistentClass" in errors[0]
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_validate.py -k semantic -v`
Expected: FAIL (cannot import `build_schema_dict`, `validate_semantics`)

**Step 3: Implement semantic validation**

Add to `dprr_tool/validate.py`:

```python
from rdflib.plugins.sparql.algebra import traverse
from rdflib.plugins.sparql.parserutils import CompValue
from rdflib.term import Variable, URIRef


def build_schema_dict(
    schemas: dict, prefix_map: dict[str, str]
) -> dict[str, dict[str, list[str]]]:
    """Build a schema dictionary from the YAML schemas.

    Returns: dict[class_full_uri][predicate_full_uri] = [range_type_uris]
    """
    schema_dict: dict[str, dict[str, list[str]]] = {}

    for cls_data in schemas.values():
        cls_uri = _expand_uri(cls_data["uri"], prefix_map)
        predicates: dict[str, list[str]] = {}
        for prop in cls_data["properties"]:
            pred_uri = _expand_uri(prop["pred"], prefix_map)
            range_uri = _expand_uri(prop["range"], prefix_map)
            predicates.setdefault(pred_uri, []).append(range_uri)
        schema_dict[cls_uri] = predicates

    return schema_dict


def validate_semantics(sparql: str, schema_dict: dict) -> list[str]:
    """Validate a SPARQL query's triple patterns against the schema dictionary.

    Returns a list of error messages (empty if valid).
    """
    try:
        parsed = prepareQuery(sparql)
    except Exception:
        return []  # Syntax errors handled by Tier 1

    # Extract triple patterns from BGPs
    bgp_triples: list[tuple] = []
    traverse(parsed.algebra, visitPost=lambda node: _collect_bgps(node, bgp_triples))

    # Build a map of variable -> rdf:type from the triples
    var_types: dict[str, str] = {}
    rdf_type = URIRef("http://www.w3.org/1999/02/22-rdf-syntax-ns#type")
    for s, p, o in bgp_triples:
        if isinstance(p, URIRef) and p == rdf_type and isinstance(o, URIRef):
            if isinstance(s, Variable):
                var_types[s.n3()] = str(o)

    # Validate each triple pattern
    errors = []
    for s, p, o in bgp_triples:
        if not isinstance(p, URIRef) or p == rdf_type:
            continue

        if isinstance(s, Variable) and s.n3() in var_types:
            cls_uri = var_types[s.n3()]

            # Check class exists
            if cls_uri not in schema_dict:
                available = ", ".join(
                    _compress_uri(c, _COMMON_PREFIXES) for c in sorted(schema_dict.keys())
                )
                errors.append(
                    f"Class {_compress_uri(cls_uri, _COMMON_PREFIXES)} does not exist in the DPRR schema. "
                    f"Available classes: {available}"
                )
                continue

            # Check predicate valid for class
            pred_uri = str(p)
            if pred_uri not in schema_dict[cls_uri]:
                valid_preds = ", ".join(
                    _compress_uri(pr, _COMMON_PREFIXES)
                    for pr in sorted(schema_dict[cls_uri].keys())
                )
                errors.append(
                    f"Class {_compress_uri(cls_uri, _COMMON_PREFIXES)} does not have predicate "
                    f"{_compress_uri(pred_uri, _COMMON_PREFIXES)}. "
                    f"Valid predicates: {valid_preds}"
                )

    return errors


_COMMON_PREFIXES = {
    "http://romanrepublic.ac.uk/rdf/entity/vocab/": "vocab:",
    "http://www.w3.org/2000/01/rdf-schema#": "rdfs:",
    "http://www.w3.org/1999/02/22-rdf-syntax-ns#": "rdf:",
    "http://www.w3.org/2001/XMLSchema#": "xsd:",
}


def _expand_uri(compact: str, prefix_map: dict[str, str]) -> str:
    """Expand a prefixed URI like 'vocab:Person' to its full form."""
    for prefix, namespace in prefix_map.items():
        if compact.startswith(f"{prefix}:"):
            return namespace + compact[len(prefix) + 1 :]
    return compact


def _compress_uri(full: str, prefix_map: dict[str, str]) -> str:
    """Compress a full URI to its prefixed form for readable error messages."""
    for namespace, prefix in prefix_map.items():
        if full.startswith(namespace):
            return prefix + full[len(namespace) :]
    return full


def _collect_bgps(node, triples_list: list):
    """Visitor function to collect triples from BGP nodes."""
    if isinstance(node, CompValue) and node.name == "BGP":
        triples_list.extend(node.triples)
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_validate.py -v`
Expected: All 9 tests PASS (5 from Tier 1 + 4 new)

**Step 5: Commit**

```bash
git add dprr_tool/validate.py tests/test_validate.py
git commit -m "feat: add semantic validation of SPARQL against DPRR schema"
```

---

### Task 9: Validation - Full Validate-and-Execute Function

Combines all three tiers into a single function that the pipeline will call.

**Files:**
- Modify: `dprr_tool/validate.py`
- Modify: `tests/test_validate.py`

**Step 1: Write the failing tests**

Append to `tests/test_validate.py`:

```python
import tempfile
from pathlib import Path

from dprr_tool.store import get_or_create_store, load_rdf
from dprr_tool.validate import validate_and_execute, ValidationResult
from tests.test_store import SAMPLE_TURTLE


def _make_test_store():
    tmpdir = tempfile.mkdtemp()
    store_path = Path(tmpdir) / "store"
    store = get_or_create_store(store_path)
    ttl_path = Path(tmpdir) / "test.ttl"
    ttl_path.write_text(SAMPLE_TURTLE)
    load_rdf(store, ttl_path)
    return store


def test_validate_and_execute_success():
    store = _make_test_store()
    sd = _make_schema_dict()
    prefixes = load_prefixes()
    sparql = """\
PREFIX vocab: <http://romanrepublic.ac.uk/rdf/entity/vocab/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT ?person ?name WHERE {
    ?person a vocab:Person ;
        rdfs:label ?name .
}"""
    result = validate_and_execute(sparql, store, sd, prefixes)
    assert result.success
    assert len(result.rows) == 2
    assert result.errors == []


def test_validate_and_execute_fixes_prefix():
    store = _make_test_store()
    sd = _make_schema_dict()
    prefixes = load_prefixes()
    sparql = """\
SELECT ?person ?name WHERE {
    ?person a vocab:Person ;
        rdfs:label ?name .
}"""
    result = validate_and_execute(sparql, store, sd, prefixes)
    assert result.success
    assert "PREFIX vocab:" in result.sparql
    assert len(result.rows) == 2


def test_validate_and_execute_returns_semantic_errors():
    store = _make_test_store()
    sd = _make_schema_dict()
    prefixes = load_prefixes()
    sparql = """\
PREFIX vocab: <http://romanrepublic.ac.uk/rdf/entity/vocab/>
SELECT ?person WHERE {
    ?person a vocab:Person ;
        vocab:hasOffice ?office .
}"""
    result = validate_and_execute(sparql, store, sd, prefixes)
    assert not result.success
    assert len(result.errors) > 0
    assert "hasOffice" in result.errors[0]


def test_validation_result_fields():
    result = ValidationResult(
        success=True, sparql="SELECT ...", rows=[{"a": "1"}], errors=[]
    )
    assert result.success
    assert result.sparql == "SELECT ..."
    assert result.rows == [{"a": "1"}]
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_validate.py -k "validate_and_execute or validation_result" -v`
Expected: FAIL (cannot import)

**Step 3: Implement validate_and_execute**

Add to `dprr_tool/validate.py`:

```python
from dataclasses import dataclass, field

from dprr_tool.store import execute_query


@dataclass
class ValidationResult:
    success: bool
    sparql: str
    rows: list[dict[str, str]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def validate_and_execute(
    sparql: str,
    store,
    schema_dict: dict,
    prefix_map: dict[str, str],
) -> ValidationResult:
    """Run all three validation tiers: syntax, semantic, execution.

    Returns a ValidationResult with success=True if the query is valid and returned results.
    """
    # Tier 1: Syntax + prefix repair
    fixed, syntax_errors = parse_and_fix_prefixes(sparql, prefix_map)
    if syntax_errors:
        return ValidationResult(success=False, sparql=fixed, errors=syntax_errors)

    # Tier 2: Semantic validation
    semantic_errors = validate_semantics(fixed, schema_dict)
    if semantic_errors:
        return ValidationResult(success=False, sparql=fixed, errors=semantic_errors)

    # Tier 3: Execution
    try:
        rows = execute_query(store, fixed)
    except Exception as e:
        return ValidationResult(
            success=False, sparql=fixed, errors=[f"Query execution error: {e}"]
        )

    if not rows:
        return ValidationResult(
            success=False,
            sparql=fixed,
            rows=[],
            errors=["Query returned 0 results. Consider relaxing filters or using broader matching (e.g., REGEX with case-insensitive flag, removing unnecessary constraints)."],
        )

    return ValidationResult(success=True, sparql=fixed, rows=rows)
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_validate.py -v`
Expected: All 13 tests PASS

**Step 5: Commit**

```bash
git add dprr_tool/validate.py tests/test_validate.py
git commit -m "feat: add validate-and-execute combining all three validation tiers"
```

---

### Task 10: System Prompts

**Files:**
- Create: `dprr_tool/prompts.py`
- Create: `tests/test_prompts.py`

**Step 1: Write the failing tests**

```python
# tests/test_prompts.py
from dprr_tool.prompts import (
    build_extraction_prompt,
    build_generation_prompt,
    build_synthesis_prompt,
    EXTRACTION_TOOL_SCHEMA,
)


def test_extraction_tool_schema_is_valid():
    assert EXTRACTION_TOOL_SCHEMA["name"] == "extract_question"
    schema = EXTRACTION_TOOL_SCHEMA["input_schema"]
    assert "intent" in schema["properties"]
    assert "extracted_classes" in schema["properties"]
    assert "extracted_entities" in schema["properties"]
    assert "question_steps" in schema["properties"]


def test_build_extraction_prompt():
    prompt = build_extraction_prompt()
    assert "DPRR" in prompt
    assert "Roman Republic" in prompt


def test_build_generation_prompt():
    prompt = build_generation_prompt()
    assert "vocab:" in prompt
    assert "negative" in prompt.lower() or "BC" in prompt
    assert "assertion" in prompt.lower() or "PostAssertion" in prompt
    assert "SPARQL" in prompt
    # Must include all schemas and examples
    assert "vocab:Person" in prompt
    assert "vocab:PostAssertion" in prompt
    assert "PREFIX" in prompt


def test_build_synthesis_prompt():
    prompt = build_synthesis_prompt()
    assert "Broughton" in prompt or "secondary source" in prompt.lower()
    assert "uncertain" in prompt.lower()
    assert "509" in prompt or "BC" in prompt
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_prompts.py -v`
Expected: FAIL (cannot import)

**Step 3: Implement prompts module**

```python
# dprr_tool/prompts.py
from dprr_tool.context import load_schemas, load_examples, render_schemas_as_shex, render_examples


EXTRACTION_TOOL_SCHEMA = {
    "name": "extract_question",
    "description": "Extract structured information from a natural language question about the Roman Republic.",
    "strict": True,
    "input_schema": {
        "type": "object",
        "properties": {
            "intent": {
                "type": "string",
                "enum": ["query_data", "general_info"],
                "description": "Whether the user wants to query specific data or get general information about the DPRR.",
            },
            "extracted_classes": {
                "type": "array",
                "items": {"type": "string"},
                "description": "DPRR ontology classes relevant to the question (e.g., Person, PostAssertion, Office, RelationshipAssertion).",
            },
            "extracted_entities": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Specific named entities mentioned (e.g., 'Scipio Africanus', 'consul', 'Cornelii').",
            },
            "question_steps": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Break complex questions into simpler sub-questions that each map to a query pattern.",
            },
        },
        "required": ["intent", "extracted_classes", "extracted_entities", "question_steps"],
        "additionalProperties": False,
    },
}


def build_extraction_prompt() -> str:
    """Build the system prompt for the structured extraction call."""
    return """\
You are a specialist in the Digital Prosopography of the Roman Republic (DPRR).
The DPRR database contains approximately 4,800 individuals from 509-31 BC,
with their offices, family relationships, social statuses, and life dates.

Your task is to analyze the user's natural language question and extract structured
information that will be used to generate a SPARQL query against the DPRR RDF database.

The DPRR ontology has these core classes:
- Person: Roman individuals with names, dates, and identification
- PostAssertion: Claims that a person held an office during a date range
- RelationshipAssertion: Claims about family relationships between persons
- StatusAssertion: Claims about social status (Eques, Nobilis, etc.)
- DateInformation: Specific life event dates (birth, death, exile)
- TribeAssertion: Claims about tribal membership
- Office: Roman offices (Consul, Praetor, Quaestor, etc.)
- Province: Roman administrative jurisdictions
- SecondarySource: Modern scholarly sources (Broughton, Rupke, Zmeskal)

Call the extract_question tool with your analysis."""


def build_generation_prompt() -> str:
    """Build the system prompt for SPARQL generation, including full schema and examples context."""
    schemas = load_schemas()
    examples = load_examples()
    schema_text = render_schemas_as_shex(schemas)
    examples_text = render_examples(examples)

    return f"""\
You are a SPARQL query generator for the Digital Prosopography of the Roman Republic (DPRR).
Generate a single SPARQL query that answers the user's question using ONLY the schema and
examples provided below. Do not invent predicates or classes that are not in the schema.

## Critical DPRR Rules

1. **Namespace**: Use `PREFIX vocab: <http://romanrepublic.ac.uk/rdf/entity/vocab/>` for all DPRR properties.
2. **Entity URIs**: Entities follow the pattern `<http://romanrepublic.ac.uk/rdf/entity/{{Type}}/{{ID}}>`.
   Known entities: `<.../Sex/Male>`, `<.../Sex/Female>`.
3. **Dates are integers**: Negative values = BC (e.g., -200 = 200 BC). Use integer comparison in FILTERs.
4. **Assertion-based model**: Office-holding is stored on PostAssertion, NOT on Person directly.
   To find who held an office: query PostAssertion with `vocab:isAboutPerson` and `vocab:hasOffice`.
   Similarly for relationships (RelationshipAssertion), status (StatusAssertion), dates (DateInformation).
5. **Always use DISTINCT** in SELECT queries.
6. **Use LIMIT 100** unless the user asks for all results.
7. **Include uncertainty**: When relevant, include `vocab:isUncertain` in the query to flag uncertain assertions.

## Output Format

Put the SPARQL query inside a markdown code block with the `sparql` language tag.
Briefly explain the query before the code block.

## DPRR Schema (all classes and their valid predicates)

```shex
{schema_text}
```

## Example Queries

{examples_text}"""


def build_synthesis_prompt() -> str:
    """Build the system prompt for response synthesis."""
    return """\
You are a scholarly assistant presenting results from the Digital Prosopography
of the Roman Republic (DPRR) database (509-31 BC).

Given the user's original question, the SPARQL query that was executed, and the
result set, produce an academic prose summary.

## Requirements

1. **Cite sources**: When results include secondary source information, cite them
   (e.g., "according to Broughton's MRR", "as recorded in Zmeskal's Adfinitas",
   "per Rupke's Fasti Sacerdotum").
2. **Flag uncertainty**: If any results have isUncertain = true, explicitly note this
   (e.g., "this attribution is marked as uncertain in the source material").
3. **Data completeness caveats**: Note that the DPRR covers only the period 509-31 BC
   and draws from specific secondary sources. Not all known Romans are included.
4. **Roman naming conventions**: Use standard prosopographic notation for Roman names
   (e.g., "L. Cornelius Scipio Africanus" not just "Scipio").
5. **Date formatting**: Present dates in standard historical format (e.g., "200 BC" not "-200").
6. **Results table**: Include a formatted table of the key results before the prose summary.
7. **Keep it concise**: 2-4 paragraphs of prose after the table. Focus on what the data shows,
   don't speculate beyond the evidence."""
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_prompts.py -v`
Expected: All 4 tests PASS

**Step 5: Commit**

```bash
git add dprr_tool/prompts.py tests/test_prompts.py
git commit -m "feat: add system prompts for extraction, generation, and synthesis"
```

---

### Task 11: LLM Pipeline - Extraction Call

**Files:**
- Create: `dprr_tool/pipeline.py`
- Create: `tests/test_pipeline.py`

**Step 1: Write the failing test**

```python
# tests/test_pipeline.py
from unittest.mock import MagicMock, patch
from dprr_tool.pipeline import extract_question, StructuredQuestion


def _mock_anthropic_extraction():
    """Create a mock Anthropic client that returns a structured extraction."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_block = MagicMock()
    mock_block.type = "tool_use"
    mock_block.name = "extract_question"
    mock_block.input = {
        "intent": "query_data",
        "extracted_classes": ["Person", "PostAssertion", "Office"],
        "extracted_entities": ["consul"],
        "question_steps": ["Find all PostAssertions for the consul office", "Get person names"],
    }
    mock_response.content = [mock_block]
    mock_client.messages.create.return_value = mock_response
    return mock_client


def test_extract_question():
    mock_client = _mock_anthropic_extraction()
    result = extract_question("Who were the consuls in 200 BC?", mock_client)
    assert isinstance(result, StructuredQuestion)
    assert result.intent == "query_data"
    assert "Person" in result.extracted_classes
    assert "PostAssertion" in result.extracted_classes
    mock_client.messages.create.assert_called_once()


def test_extract_question_calls_api_correctly():
    mock_client = _mock_anthropic_extraction()
    extract_question("Who were the consuls in 200 BC?", mock_client)
    call_kwargs = mock_client.messages.create.call_args.kwargs
    assert call_kwargs["temperature"] == 0
    assert len(call_kwargs["tools"]) == 1
    assert call_kwargs["tools"][0]["name"] == "extract_question"
    assert call_kwargs["tool_choice"] == {"type": "tool", "name": "extract_question"}
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_pipeline.py -v`
Expected: FAIL (cannot import)

**Step 3: Implement extraction**

```python
# dprr_tool/pipeline.py
from dataclasses import dataclass

from anthropic import Anthropic

from dprr_tool.prompts import (
    EXTRACTION_TOOL_SCHEMA,
    build_extraction_prompt,
    build_generation_prompt,
    build_synthesis_prompt,
)


@dataclass
class StructuredQuestion:
    intent: str
    extracted_classes: list[str]
    extracted_entities: list[str]
    question_steps: list[str]


def extract_question(question: str, client: Anthropic) -> StructuredQuestion:
    """Call Claude to decompose a natural language question into structured parts."""
    response = client.messages.create(
        model="claude-sonnet-4-5-20250514",
        max_tokens=1024,
        temperature=0,
        system=build_extraction_prompt(),
        tools=[EXTRACTION_TOOL_SCHEMA],
        tool_choice={"type": "tool", "name": "extract_question"},
        messages=[{"role": "user", "content": question}],
    )

    for block in response.content:
        if block.type == "tool_use" and block.name == "extract_question":
            data = block.input
            return StructuredQuestion(
                intent=data["intent"],
                extracted_classes=data["extracted_classes"],
                extracted_entities=data["extracted_entities"],
                question_steps=data["question_steps"],
            )

    raise RuntimeError("Claude did not return a tool_use response for extraction")
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_pipeline.py -v`
Expected: All 2 tests PASS

**Step 5: Commit**

```bash
git add dprr_tool/pipeline.py tests/test_pipeline.py
git commit -m "feat: add structured question extraction via Claude tool use"
```

---

### Task 12: LLM Pipeline - Generation with Validation Loop

**Files:**
- Modify: `dprr_tool/pipeline.py`
- Modify: `tests/test_pipeline.py`

**Step 1: Write the failing tests**

Append to `tests/test_pipeline.py`:

```python
import re
from dprr_tool.pipeline import generate_sparql


def _mock_anthropic_generation(sparql_response: str):
    """Create a mock client that returns a SPARQL query in markdown."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_block = MagicMock()
    mock_block.type = "text"
    mock_block.text = f"Here is the query:\n\n```sparql\n{sparql_response}\n```"
    mock_response.content = [mock_block]
    mock_response.stop_reason = "end_turn"
    mock_client.messages.create.return_value = mock_response
    return mock_client


def test_generate_sparql_extracts_from_markdown():
    sparql = """\
PREFIX vocab: <http://romanrepublic.ac.uk/rdf/entity/vocab/>
SELECT ?person WHERE { ?person a vocab:Person . }"""
    mock_client = _mock_anthropic_generation(sparql)
    extraction = StructuredQuestion(
        intent="query_data",
        extracted_classes=["Person"],
        extracted_entities=[],
        question_steps=["Find all persons"],
    )
    result = generate_sparql("List all persons", extraction, mock_client)
    assert "SELECT" in result
    assert "vocab:Person" in result


def test_generate_sparql_retries_on_error():
    """On first call returns bad SPARQL, on second call returns good SPARQL."""
    mock_client = MagicMock()

    bad_block = MagicMock()
    bad_block.type = "text"
    bad_block.text = "```sparql\nSELCT ?x WHERE { ?x ?p ?o }\n```"
    bad_response = MagicMock()
    bad_response.content = [bad_block]
    bad_response.stop_reason = "end_turn"

    good_sparql = "PREFIX vocab: <http://romanrepublic.ac.uk/rdf/entity/vocab/>\nSELECT ?x WHERE { ?x a vocab:Person . }"
    good_block = MagicMock()
    good_block.type = "text"
    good_block.text = f"```sparql\n{good_sparql}\n```"
    good_response = MagicMock()
    good_response.content = [good_block]
    good_response.stop_reason = "end_turn"

    mock_client.messages.create.side_effect = [bad_response, good_response]

    extraction = StructuredQuestion(
        intent="query_data",
        extracted_classes=["Person"],
        extracted_entities=[],
        question_steps=["Find persons"],
    )
    result = generate_sparql("Find persons", extraction, mock_client)
    assert "SELECT" in result
    assert mock_client.messages.create.call_count == 2
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_pipeline.py -k generate -v`
Expected: FAIL (cannot import `generate_sparql`)

**Step 3: Implement generation with retry loop**

Add to `dprr_tool/pipeline.py`:

```python
import re

from dprr_tool.context import load_prefixes
from dprr_tool.validate import parse_and_fix_prefixes


MAX_RETRIES = 3


def generate_sparql(
    question: str,
    extraction: StructuredQuestion,
    client: Anthropic,
) -> str:
    """Call Claude to generate a SPARQL query, with syntax-level retry loop.

    Returns the SPARQL query string (with prefixes fixed if needed).
    Raises RuntimeError if all retries fail.
    """
    prefix_map = load_prefixes()
    system_prompt = build_generation_prompt()
    extraction_context = (
        f"Extracted information:\n"
        f"- Intent: {extraction.intent}\n"
        f"- Classes: {', '.join(extraction.extracted_classes)}\n"
        f"- Entities: {', '.join(extraction.extracted_entities)}\n"
        f"- Steps: {'; '.join(extraction.question_steps)}"
    )

    messages = [
        {"role": "user", "content": f"{extraction_context}\n\nQuestion: {question}"},
    ]

    last_errors = []
    for attempt in range(MAX_RETRIES):
        response = client.messages.create(
            model="claude-sonnet-4-5-20250514",
            max_tokens=4096,
            temperature=0,
            system=system_prompt,
            messages=messages,
        )

        response_text = ""
        for block in response.content:
            if block.type == "text":
                response_text += block.text

        sparql = _extract_sparql_from_markdown(response_text)
        if not sparql:
            last_errors = ["No SPARQL code block found in the response."]
            messages.append({"role": "assistant", "content": response_text})
            messages.append({"role": "user", "content": "Please provide a SPARQL query inside a ```sparql code block."})
            continue

        fixed, errors = parse_and_fix_prefixes(sparql, prefix_map)
        if not errors:
            return fixed

        last_errors = errors
        messages.append({"role": "assistant", "content": response_text})
        messages.append({
            "role": "user",
            "content": f"The generated query has errors:\n\n" + "\n".join(f"- {e}" for e in errors) + "\n\nPlease fix the query and try again.",
        })

    raise RuntimeError(
        f"Failed to generate valid SPARQL after {MAX_RETRIES} attempts. Last errors: {last_errors}"
    )


def _extract_sparql_from_markdown(text: str) -> str | None:
    """Extract a SPARQL query from a markdown code block."""
    match = re.search(r"```sparql\s*\n(.*?)```", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return None
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_pipeline.py -v`
Expected: All 4 tests PASS

**Step 5: Commit**

```bash
git add dprr_tool/pipeline.py tests/test_pipeline.py
git commit -m "feat: add SPARQL generation with syntax-level retry loop"
```

---

### Task 13: LLM Pipeline - Synthesis Call

**Files:**
- Modify: `dprr_tool/pipeline.py`
- Modify: `tests/test_pipeline.py`

**Step 1: Write the failing test**

Append to `tests/test_pipeline.py`:

```python
from dprr_tool.pipeline import synthesize_response


def test_synthesize_response():
    mock_client = MagicMock()
    mock_block = MagicMock()
    mock_block.type = "text"
    mock_block.text = "The DPRR records 2 consuls for 509 BC: L. Iunius Brutus and L. Tarquinius Collatinus."
    mock_response = MagicMock()
    mock_response.content = [mock_block]
    mock_client.messages.create.return_value = mock_response

    result = synthesize_response(
        question="Who were the first consuls?",
        sparql="SELECT ...",
        rows=[
            {"name": "L. Iunius Brutus", "dateStart": "-509"},
            {"name": "L. Tarquinius Collatinus", "dateStart": "-509"},
        ],
        client=mock_client,
    )
    assert "Brutus" in result or "consuls" in result.lower()
    mock_client.messages.create.assert_called_once()


def test_synthesize_response_includes_results_in_message():
    mock_client = MagicMock()
    mock_block = MagicMock()
    mock_block.type = "text"
    mock_block.text = "Summary."
    mock_response = MagicMock()
    mock_response.content = [mock_block]
    mock_client.messages.create.return_value = mock_response

    synthesize_response(
        question="Test",
        sparql="SELECT ...",
        rows=[{"a": "1"}],
        client=mock_client,
    )
    call_kwargs = mock_client.messages.create.call_args.kwargs
    user_msg = call_kwargs["messages"][0]["content"]
    assert "SELECT ..." in user_msg
    assert "Test" in user_msg
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_pipeline.py -k synthesize -v`
Expected: FAIL

**Step 3: Implement synthesis**

Add to `dprr_tool/pipeline.py`:

```python
def synthesize_response(
    question: str,
    sparql: str,
    rows: list[dict[str, str]],
    client: Anthropic,
) -> str:
    """Call Claude to synthesize an academic prose response from query results."""
    # Format the results as a simple table for the LLM
    if rows:
        headers = list(rows[0].keys())
        table_lines = [" | ".join(headers)]
        table_lines.append(" | ".join("---" for _ in headers))
        for row in rows[:50]:  # Cap at 50 rows for context
            table_lines.append(" | ".join(str(row.get(h, "")) for h in headers))
        results_table = "\n".join(table_lines)
    else:
        results_table = "(no results)"

    user_content = (
        f"## Original Question\n{question}\n\n"
        f"## SPARQL Query Executed\n```sparql\n{sparql}\n```\n\n"
        f"## Results ({len(rows)} rows)\n{results_table}"
    )

    response = client.messages.create(
        model="claude-sonnet-4-5-20250514",
        max_tokens=8192,
        temperature=0,
        system=build_synthesis_prompt(),
        messages=[{"role": "user", "content": user_content}],
    )

    for block in response.content:
        if block.type == "text":
            return block.text

    return "(No synthesis generated)"
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_pipeline.py -v`
Expected: All 6 tests PASS

**Step 5: Commit**

```bash
git add dprr_tool/pipeline.py tests/test_pipeline.py
git commit -m "feat: add response synthesis with academic prose generation"
```

---

### Task 14: LLM Pipeline - Full Pipeline Orchestrator

Ties extraction, generation (with validation), and synthesis together.

**Files:**
- Modify: `dprr_tool/pipeline.py`
- Modify: `tests/test_pipeline.py`

**Step 1: Write the failing test**

Append to `tests/test_pipeline.py`:

```python
import tempfile
from pathlib import Path

from dprr_tool.pipeline import run_pipeline, PipelineResult
from tests.test_store import SAMPLE_TURTLE
from dprr_tool.store import get_or_create_store, load_rdf


def _mock_full_pipeline_client():
    """Mock client that handles extraction, generation, and synthesis calls in sequence."""
    mock_client = MagicMock()

    # Call 1: extraction
    extract_block = MagicMock()
    extract_block.type = "tool_use"
    extract_block.name = "extract_question"
    extract_block.input = {
        "intent": "query_data",
        "extracted_classes": ["Person"],
        "extracted_entities": [],
        "question_steps": ["Find all persons"],
    }
    extract_response = MagicMock()
    extract_response.content = [extract_block]

    # Call 2: generation
    sparql = """\
PREFIX vocab: <http://romanrepublic.ac.uk/rdf/entity/vocab/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT DISTINCT ?person ?name WHERE {
    ?person a vocab:Person ;
        rdfs:label ?name .
}
LIMIT 100"""
    gen_block = MagicMock()
    gen_block.type = "text"
    gen_block.text = f"```sparql\n{sparql}\n```"
    gen_response = MagicMock()
    gen_response.content = [gen_block]
    gen_response.stop_reason = "end_turn"

    # Call 3: synthesis
    synth_block = MagicMock()
    synth_block.type = "text"
    synth_block.text = "The DPRR contains 2 persons."
    synth_response = MagicMock()
    synth_response.content = [synth_block]

    mock_client.messages.create.side_effect = [extract_response, gen_response, synth_response]
    return mock_client


def test_run_pipeline():
    tmpdir = tempfile.mkdtemp()
    store_path = Path(tmpdir) / "store"
    store = get_or_create_store(store_path)
    ttl_path = Path(tmpdir) / "test.ttl"
    ttl_path.write_text(SAMPLE_TURTLE)
    load_rdf(store, ttl_path)

    mock_client = _mock_full_pipeline_client()
    result = run_pipeline("List all persons", store, mock_client)

    assert isinstance(result, PipelineResult)
    assert result.sparql is not None
    assert "SELECT" in result.sparql
    assert len(result.rows) == 2
    assert result.synthesis is not None
    assert mock_client.messages.create.call_count == 3
```

**Step 2: Run tests to verify it fails**

Run: `uv run pytest tests/test_pipeline.py -k run_pipeline -v`
Expected: FAIL (cannot import `run_pipeline`, `PipelineResult`)

**Step 3: Implement the full pipeline orchestrator**

Add to `dprr_tool/pipeline.py`:

```python
from dprr_tool.context import load_prefixes, load_schemas
from dprr_tool.validate import build_schema_dict, validate_and_execute


@dataclass
class PipelineResult:
    question: str
    extraction: StructuredQuestion | None
    sparql: str | None
    rows: list[dict[str, str]]
    synthesis: str | None
    errors: list[str]


def run_pipeline(
    question: str,
    store,
    client: Anthropic,
) -> PipelineResult:
    """Run the full NL-to-SPARQL pipeline: extract -> generate -> validate -> execute -> synthesize."""
    errors = []

    # Step 1: Extract structured question
    try:
        extraction = extract_question(question, client)
    except Exception as e:
        return PipelineResult(
            question=question, extraction=None, sparql=None,
            rows=[], synthesis=None, errors=[f"Extraction failed: {e}"],
        )

    # Step 2: Generate SPARQL (with syntax-level retry)
    try:
        sparql = generate_sparql(question, extraction, client)
    except RuntimeError as e:
        return PipelineResult(
            question=question, extraction=extraction, sparql=None,
            rows=[], synthesis=None, errors=[str(e)],
        )

    # Step 3: Validate and execute (with semantic retry)
    prefix_map = load_prefixes()
    schema_dict = build_schema_dict(load_schemas(), prefix_map)
    validation = validate_and_execute(sparql, store, schema_dict, prefix_map)

    if not validation.success:
        # Try to get Claude to fix semantic / execution errors
        sparql, validation = _retry_with_semantic_errors(
            question, extraction, sparql, validation, store, schema_dict, prefix_map, client,
        )

    if not validation.success:
        return PipelineResult(
            question=question, extraction=extraction, sparql=validation.sparql,
            rows=[], synthesis=None, errors=validation.errors,
        )

    # Step 4: Synthesize response
    try:
        synthesis = synthesize_response(question, validation.sparql, validation.rows, client)
    except Exception as e:
        synthesis = None
        errors.append(f"Synthesis failed: {e}")

    return PipelineResult(
        question=question, extraction=extraction, sparql=validation.sparql,
        rows=validation.rows, synthesis=synthesis, errors=errors,
    )


def _retry_with_semantic_errors(
    question: str,
    extraction: StructuredQuestion,
    sparql: str,
    validation,
    store,
    schema_dict: dict,
    prefix_map: dict[str, str],
    client: Anthropic,
    max_retries: int = 2,
):
    """Retry SPARQL generation when semantic validation or execution fails."""
    system_prompt = build_generation_prompt()
    extraction_context = (
        f"Extracted information:\n"
        f"- Intent: {extraction.intent}\n"
        f"- Classes: {', '.join(extraction.extracted_classes)}\n"
        f"- Entities: {', '.join(extraction.extracted_entities)}\n"
        f"- Steps: {'; '.join(extraction.question_steps)}"
    )

    messages = [
        {"role": "user", "content": f"{extraction_context}\n\nQuestion: {question}"},
        {"role": "assistant", "content": f"```sparql\n{sparql}\n```"},
    ]

    for _ in range(max_retries):
        error_text = "\n".join(f"- {e}" for e in validation.errors)
        messages.append({
            "role": "user",
            "content": f"The query has validation errors:\n\n{error_text}\n\nPlease fix the query.",
        })

        response = client.messages.create(
            model="claude-sonnet-4-5-20250514",
            max_tokens=4096,
            temperature=0,
            system=system_prompt,
            messages=messages,
        )

        response_text = ""
        for block in response.content:
            if block.type == "text":
                response_text += block.text

        new_sparql = _extract_sparql_from_markdown(response_text)
        if not new_sparql:
            continue

        fixed, syntax_errors = parse_and_fix_prefixes(new_sparql, prefix_map)
        if syntax_errors:
            messages.append({"role": "assistant", "content": response_text})
            continue

        validation = validate_and_execute(fixed, store, schema_dict, prefix_map)
        if validation.success:
            return fixed, validation

        sparql = fixed
        messages.append({"role": "assistant", "content": response_text})

    return sparql, validation
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_pipeline.py -v`
Expected: All 7 tests PASS

**Step 5: Commit**

```bash
git add dprr_tool/pipeline.py tests/test_pipeline.py
git commit -m "feat: add full pipeline orchestrator with semantic retry loop"
```

---

### Task 15: CLI - Init and Info Commands

**Files:**
- Create: `dprr_tool/cli.py`
- Replace: `main.py`
- Create: `tests/test_cli.py`

**Step 1: Write the failing tests**

```python
# tests/test_cli.py
import tempfile
from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

from dprr_tool.cli import cli


def test_cli_info_no_store():
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as tmpdir:
        result = runner.invoke(cli, ["info", "--store-path", tmpdir])
        assert result.exit_code == 0
        assert "not initialized" in result.output.lower() or "no data" in result.output.lower()


def test_cli_help():
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "ask" in result.output
    assert "query" in result.output
    assert "init" in result.output
    assert "info" in result.output
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_cli.py -v`
Expected: FAIL (cannot import)

**Step 3: Implement CLI**

```python
# dprr_tool/cli.py
from pathlib import Path

import click
from rich.console import Console
from rich.markdown import Markdown
from rich.syntax import Syntax
from rich.table import Table

from dprr_tool.store import get_or_create_store, is_initialized, load_rdf, execute_query

DEFAULT_STORE_PATH = Path.home() / ".dprr-tool"
console = Console()


@click.group()
@click.option(
    "--store-path",
    type=click.Path(path_type=Path),
    default=DEFAULT_STORE_PATH,
    envvar="DPRR_STORE_PATH",
    help="Path to the Oxigraph store directory.",
)
@click.pass_context
def cli(ctx, store_path: Path):
    """dprr-tool: Natural language SPARQL for the Roman Republic."""
    ctx.ensure_object(dict)
    ctx.obj["store_path"] = store_path


@cli.command()
@click.argument("rdf_file", type=click.Path(exists=True, path_type=Path))
@click.pass_context
def init(ctx, rdf_file: Path):
    """Load DPRR RDF data into the local Oxigraph store."""
    store_path = ctx.obj["store_path"] / "store"
    console.print(f"Loading RDF data from [bold]{rdf_file}[/bold]...")
    store = get_or_create_store(store_path)
    count = load_rdf(store, rdf_file)
    console.print(f"[green]Loaded {count} triples into {store_path}[/green]")


@cli.command()
@click.pass_context
def info(ctx):
    """Show store status and statistics."""
    store_path = ctx.obj["store_path"] / "store"
    if not is_initialized(store_path):
        console.print("[yellow]Store is not initialized. No data loaded.[/yellow]")
        console.print(f"Run [bold]dprr-tool init <rdf-file>[/bold] to load DPRR data.")
        return

    from pyoxigraph import Store

    store = Store(str(store_path))
    count = len(store)
    console.print(f"Store path: [bold]{store_path}[/bold]")
    console.print(f"Triple count: [bold]{count}[/bold]")


@cli.command()
@click.argument("sparql_query", type=str)
@click.pass_context
def query(ctx, sparql_query: str):
    """Execute a raw SPARQL query against the local store."""
    store_path = ctx.obj["store_path"] / "store"
    if not is_initialized(store_path):
        console.print("[red]Store is not initialized. Run 'dprr-tool init' first.[/red]")
        raise SystemExit(1)

    store = get_or_create_store(store_path)
    console.print(Syntax(sparql_query, "sparql", theme="monokai"))

    try:
        rows = execute_query(store, sparql_query)
    except Exception as e:
        console.print(f"[red]Query error: {e}[/red]")
        raise SystemExit(1)

    _print_results_table(rows)


@cli.command()
@click.argument("question", type=str)
@click.pass_context
def ask(ctx, question: str):
    """Ask a natural language question about the Roman Republic."""
    store_path = ctx.obj["store_path"] / "store"
    if not is_initialized(store_path):
        console.print("[red]Store is not initialized. Run 'dprr-tool init' first.[/red]")
        raise SystemExit(1)

    from anthropic import Anthropic

    from dprr_tool.pipeline import run_pipeline

    store = get_or_create_store(store_path)
    client = Anthropic()

    console.print(f"\n[bold]Question:[/bold] {question}\n")

    with console.status("Thinking..."):
        result = run_pipeline(question, store, client)

    if result.sparql:
        console.print("[bold]Generated SPARQL:[/bold]")
        console.print(Syntax(result.sparql, "sparql", theme="monokai"))
        console.print()

    if result.errors:
        for error in result.errors:
            console.print(f"[red]Error: {error}[/red]")

    if result.rows:
        _print_results_table(result.rows)

    if result.synthesis:
        console.print("\n[bold]Summary:[/bold]\n")
        console.print(Markdown(result.synthesis))


def _print_results_table(rows: list[dict]):
    """Print query results as a rich table."""
    if not rows:
        console.print("[yellow]No results.[/yellow]")
        return

    table = Table(show_header=True, header_style="bold")
    for col in rows[0].keys():
        table.add_column(col)
    for row in rows[:100]:
        table.add_row(*(str(row.get(col, "")) for col in rows[0].keys()))

    console.print(f"\n[bold]{len(rows)} results:[/bold]")
    console.print(table)
```

Replace `main.py`:

```python
# main.py
from dprr_tool.cli import cli

if __name__ == "__main__":
    cli()
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_cli.py -v`
Expected: All 2 tests PASS

**Step 5: Verify CLI runs**

Run: `uv run dprr-tool --help`
Expected: Shows help text with all four commands.

**Step 6: Commit**

```bash
git add dprr_tool/cli.py main.py tests/test_cli.py
git commit -m "feat: add CLI with init, info, query, and ask commands"
```

---

### Task 16: Integration Test with Sample Data

**Files:**
- Create: `tests/test_integration.py`

**Step 1: Write the integration test**

```python
# tests/test_integration.py
"""Integration tests using sample data and mocked LLM calls."""
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

from dprr_tool.store import get_or_create_store, load_rdf
from dprr_tool.context import load_prefixes, load_schemas
from dprr_tool.validate import (
    build_schema_dict,
    parse_and_fix_prefixes,
    validate_semantics,
    validate_and_execute,
)
from dprr_tool.pipeline import run_pipeline, PipelineResult
from tests.test_store import SAMPLE_TURTLE


def _setup_store():
    tmpdir = tempfile.mkdtemp()
    store_path = Path(tmpdir) / "store"
    store = get_or_create_store(store_path)
    ttl_path = Path(tmpdir) / "test.ttl"
    ttl_path.write_text(SAMPLE_TURTLE)
    load_rdf(store, ttl_path)
    return store


def test_full_validation_pipeline_with_valid_query():
    store = _setup_store()
    prefixes = load_prefixes()
    sd = build_schema_dict(load_schemas(), prefixes)

    sparql = """\
PREFIX vocab: <http://romanrepublic.ac.uk/rdf/entity/vocab/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT DISTINCT ?person ?name WHERE {
    ?person a vocab:Person ;
        rdfs:label ?name .
}
LIMIT 100"""

    result = validate_and_execute(sparql, store, sd, prefixes)
    assert result.success
    assert len(result.rows) == 2


def test_full_validation_pipeline_with_missing_prefix():
    store = _setup_store()
    prefixes = load_prefixes()
    sd = build_schema_dict(load_schemas(), prefixes)

    # Missing both PREFIX declarations
    sparql = """\
SELECT DISTINCT ?person ?name WHERE {
    ?person a vocab:Person ;
        rdfs:label ?name .
}"""

    result = validate_and_execute(sparql, store, sd, prefixes)
    assert result.success
    assert len(result.rows) == 2
    assert "PREFIX" in result.sparql


def test_full_validation_catches_bad_predicate():
    store = _setup_store()
    prefixes = load_prefixes()
    sd = build_schema_dict(load_schemas(), prefixes)

    sparql = """\
PREFIX vocab: <http://romanrepublic.ac.uk/rdf/entity/vocab/>
SELECT ?person WHERE {
    ?person a vocab:Person ;
        vocab:hasOffice ?office .
}"""

    result = validate_and_execute(sparql, store, sd, prefixes)
    assert not result.success
    assert any("hasOffice" in e for e in result.errors)


def test_context_rendering_is_nonempty():
    """Sanity check that the context for LLM injection is substantial."""
    from dprr_tool.prompts import build_generation_prompt

    prompt = build_generation_prompt()
    assert len(prompt) > 1000
    assert "vocab:Person" in prompt
    assert "vocab:PostAssertion" in prompt
    assert "PREFIX" in prompt
```

**Step 2: Run the integration tests**

Run: `uv run pytest tests/test_integration.py -v`
Expected: All 4 tests PASS

**Step 3: Run full test suite**

Run: `uv run pytest -v`
Expected: All tests PASS

**Step 4: Commit**

```bash
git add tests/test_integration.py
git commit -m "test: add integration tests for validation pipeline"
```

---

### Task 17: Run Full Test Suite and Clean Up

**Step 1: Run all tests**

Run: `uv run pytest -v --tb=short`
Expected: All tests PASS, no warnings

**Step 2: Verify CLI end-to-end**

Run: `uv run dprr-tool --help`
Run: `uv run dprr-tool info`
Expected: Help text shows all commands. Info reports store not initialized.

**Step 3: Final commit if any cleanup was needed**

```bash
git add -A
git commit -m "chore: final cleanup and test pass"
```
