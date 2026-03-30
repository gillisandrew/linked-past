# tests/test_core_context.py

import yaml

from linked_past.core.context import (
    get_cross_cutting_tips,
    get_relevant_examples,
    get_relevant_tips,
    load_context_yaml,
    render_class_summary,
    render_examples,
    render_tips,
)

SAMPLE_SCHEMAS = {
    "Widget": {
        "label": "Widget",
        "comment": "A sample widget",
        "uri": "ex:Widget",
        "properties": [
            {"pred": "ex:hasName", "range": "xsd:string", "comment": "Name"},
            {"pred": "ex:hasColor", "range": "xsd:string", "comment": "Color"},
        ],
    }
}

SAMPLE_EXAMPLES = [
    {
        "question": "List all widgets",
        "sparql": "SELECT ?w WHERE { ?w a ex:Widget }",
        "classes": ["Widget"],
    },
    {
        "question": "Count things",
        "sparql": "SELECT (COUNT(*) AS ?c) WHERE { ?s ?p ?o }",
        "classes": [],
    },
]

SAMPLE_TIPS = [
    {"title": "Cross-cutting tip", "body": "Applies everywhere.", "classes": []},
    {"title": "Widget tip", "body": "Widgets are special.", "classes": ["Widget"]},
    {"title": "Gadget tip", "body": "Gadgets are different.", "classes": ["Gadget"]},
]


def test_load_context_yaml(tmp_path):
    data = {"prefixes": {"ex": "http://example.org/"}}
    path = tmp_path / "prefixes.yaml"
    path.write_text(yaml.dump(data))
    result = load_context_yaml(path)
    assert result == data


def test_render_class_summary():
    result = render_class_summary(SAMPLE_SCHEMAS)
    assert "Widget" in result
    assert "ex:Widget" in result
    assert "A sample widget" in result


def test_render_examples():
    result = render_examples(SAMPLE_EXAMPLES)
    assert "List all widgets" in result
    assert "SELECT ?w" in result


def test_render_tips():
    result = render_tips(SAMPLE_TIPS)
    assert "Cross-cutting tip" in result
    assert "Applies everywhere" in result


def test_get_cross_cutting_tips():
    result = get_cross_cutting_tips(SAMPLE_TIPS)
    assert len(result) == 1
    assert result[0]["title"] == "Cross-cutting tip"


def test_get_relevant_tips():
    result = get_relevant_tips(SAMPLE_TIPS, {"Widget"})
    assert len(result) == 1
    assert result[0]["title"] == "Widget tip"


def test_get_relevant_tips_no_match():
    result = get_relevant_tips(SAMPLE_TIPS, {"Nonexistent"})
    assert result == []


def test_get_relevant_examples():
    result = get_relevant_examples(SAMPLE_EXAMPLES, {"Widget"})
    assert len(result) == 1
    assert result[0]["question"] == "List all widgets"


def test_load_prefixes(tmp_path):
    data = {"prefixes": {"ex": "http://example.org/", "rdfs": "http://www.w3.org/2000/01/rdf-schema#"}}
    (tmp_path / "prefixes.yaml").write_text(yaml.dump(data))
    from linked_past.core.context import load_prefixes
    result = load_prefixes(tmp_path)
    assert result["ex"] == "http://example.org/"


def test_load_schemas(tmp_path):
    data = {"classes": {"Widget": {"label": "Widget", "uri": "ex:Widget", "properties": []}}}
    (tmp_path / "schemas.yaml").write_text(yaml.dump(data))
    from linked_past.core.context import load_schemas
    result = load_schemas(tmp_path)
    assert "Widget" in result


def test_load_examples(tmp_path):
    data = {"examples": [{"question": "Q1", "sparql": "SELECT ?x WHERE { ?x ?p ?o }"}]}
    (tmp_path / "examples.yaml").write_text(yaml.dump(data))
    from linked_past.core.context import load_examples
    result = load_examples(tmp_path)
    assert len(result) == 1


def test_load_tips(tmp_path):
    data = {"tips": [{"title": "Tip1", "body": "Do this", "classes": []}]}
    (tmp_path / "tips.yaml").write_text(yaml.dump(data))
    from linked_past.core.context import load_tips
    result = load_tips(tmp_path)
    assert len(result) == 1
