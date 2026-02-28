from dprr_tool.context import (
    load_examples,
    load_prefixes,
    load_schemas,
    load_tips,
    render_examples,
    render_schemas_as_shex,
    render_tips,
)


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
    assert len(examples) >= 25
    assert "question" in examples[0]
    assert "sparql" in examples[0]


def test_render_schemas_as_shex():
    schemas = load_schemas()
    text = render_schemas_as_shex(schemas)
    assert "vocab:Person" in text
    assert "vocab:hasDprrID" in text
    assert "vocab:PostAssertion" in text
    assert "vocab:hasOffice" in text
    assert "{" in text
    assert "}" in text


def test_render_examples():
    examples = load_examples()
    text = render_examples(examples)
    assert "PREFIX" in text
    assert "SELECT" in text
    assert examples[0]["question"] in text


def test_load_tips():
    tips = load_tips()
    assert isinstance(tips, list)
    assert len(tips) >= 7
    assert "id" in tips[0]
    assert "title" in tips[0]
    assert "body" in tips[0]


def test_render_tips():
    tips = load_tips()
    text = render_tips(tips)
    assert "FILTER NOT EXISTS" in text
    assert "STR(" in text
    assert "BIND" in text
    assert "COUNT(DISTINCT" in text
