from pathlib import Path
import yaml

CONTEXT_DIR = Path(__file__).parent.parent / "dprr_tool" / "context"


def test_prefixes_yaml_loads():
    with open(CONTEXT_DIR / "prefixes.yaml") as f:
        data = yaml.safe_load(f)
    assert "prefixes" in data
    prefixes = data["prefixes"]
    assert prefixes["vocab"] == "http://romanrepublic.ac.uk/rdf/entity/vocab/"
    assert "rdfs" in prefixes
    assert "rdf" in prefixes
    assert "xsd" in prefixes
    assert "entity" in prefixes


def test_schemas_yaml_loads():
    with open(CONTEXT_DIR / "schemas.yaml") as f:
        data = yaml.safe_load(f)
    assert "classes" in data
    classes = data["classes"]
    for cls_name in [
        "Person",
        "PostAssertion",
        "PostAssertionProvince",
        "RelationshipAssertion",
        "StatusAssertion",
        "DateInformation",
        "TribeAssertion",
        "Office",
        "Province",
        "Sex",
        "Praenomen",
        "Tribe",
        "SecondarySource",
        "PrimarySource",
        "Status",
        "Relationship",
        "DateType",
    ]:
        assert cls_name in classes, f"Missing class: {cls_name}"
    for cls_name, cls_data in classes.items():
        assert "label" in cls_data, f"{cls_name} missing label"
        assert "uri" in cls_data, f"{cls_name} missing uri"
        assert "properties" in cls_data, f"{cls_name} missing properties"
        assert len(cls_data["properties"]) > 0, f"{cls_name} has no properties"
        for prop in cls_data["properties"]:
            assert "pred" in prop, f"{cls_name} property missing pred"
            assert "range" in prop, f"{cls_name} property missing range"


def test_schemas_person_has_key_properties():
    with open(CONTEXT_DIR / "schemas.yaml") as f:
        data = yaml.safe_load(f)
    person = data["classes"]["Person"]
    preds = [p["pred"] for p in person["properties"]]
    for expected in [
        "vocab:hasPersonName",
        "vocab:hasDprrID",
        "vocab:hasNomen",
        "vocab:hasCognomen",
        "vocab:isSex",
        "vocab:hasEraFrom",
        "vocab:hasEraTo",
        "vocab:isPatrician",
    ]:
        assert expected in preds, f"Person missing {expected}"


def test_schemas_post_assertion_has_key_properties():
    with open(CONTEXT_DIR / "schemas.yaml") as f:
        data = yaml.safe_load(f)
    pa = data["classes"]["PostAssertion"]
    preds = [p["pred"] for p in pa["properties"]]
    for expected in [
        "vocab:isAboutPerson",
        "vocab:hasOffice",
        "vocab:hasDateStart",
        "vocab:hasDateEnd",
        "vocab:hasSecondarySource",
        "vocab:isUncertain",
    ]:
        assert expected in preds, f"PostAssertion missing {expected}"


def test_examples_yaml_loads():
    with open(CONTEXT_DIR / "examples.yaml") as f:
        data = yaml.safe_load(f)
    assert "examples" in data
    examples = data["examples"]
    assert len(examples) >= 15
    for i, ex in enumerate(examples):
        assert "question" in ex, f"Example {i} missing question"
        assert "sparql" in ex, f"Example {i} missing sparql"
        assert "PREFIX" in ex["sparql"] or "prefix" in ex["sparql"], (
            f"Example {i} missing PREFIX"
        )


def test_examples_cover_key_patterns():
    with open(CONTEXT_DIR / "examples.yaml") as f:
        data = yaml.safe_load(f)
    questions = [ex["question"].lower() for ex in data["examples"]]
    assert any("consul" in q for q in questions), "Missing consul query"
    assert any("woman" in q or "female" in q for q in questions), (
        "Missing gender query"
    )
    assert any(
        "family" in q
        or "relationship" in q
        or "father" in q
        or "relative" in q
        for q in questions
    ), "Missing relationship query"
    assert any(
        "patrician" in q or "status" in q or "nobil" in q for q in questions
    ), "Missing status query"
    assert any("tribe" in q for q in questions), "Missing tribe query"
    assert any("province" in q for q in questions), "Missing province query"
    assert any("uncertain" in q for q in questions), "Missing uncertainty query"
    assert any("source" in q for q in questions), "Missing source query"
