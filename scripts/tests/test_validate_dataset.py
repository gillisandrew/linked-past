"""Tests for validate_dataset schema diff logic."""


def test_diff_schemas_no_changes():
    from scripts.validate_dataset import diff_schemas

    old = {"Person": {"label": "Person", "properties": [{"pred": "name"}]}}
    new = {"Person": {"label": "Person", "properties": [{"pred": "name"}]}}
    result = diff_schemas(old, new)
    assert result["added"] == []
    assert result["removed"] == []
    assert result["changed"] == []


def test_diff_schemas_added_class():
    from scripts.validate_dataset import diff_schemas

    old = {"Person": {"label": "Person", "properties": []}}
    new = {
        "Person": {"label": "Person", "properties": []},
        "Office": {"label": "Office", "properties": [{"pred": "title"}]},
    }
    result = diff_schemas(old, new)
    assert result["added"] == [("Office", 1)]
    assert result["removed"] == []


def test_diff_schemas_removed_class():
    from scripts.validate_dataset import diff_schemas

    old = {
        "Person": {"label": "Person", "properties": []},
        "Office": {"label": "Office", "properties": [{"pred": "title"}]},
    }
    new = {"Person": {"label": "Person", "properties": []}}
    result = diff_schemas(old, new)
    assert result["removed"] == [("Office", 1)]
    assert result["added"] == []


def test_diff_schemas_changed_properties():
    from scripts.validate_dataset import diff_schemas

    old = {"Person": {"label": "Person", "properties": [{"pred": "name"}]}}
    new = {"Person": {"label": "Person", "properties": [{"pred": "name"}, {"pred": "age"}]}}
    result = diff_schemas(old, new)
    assert len(result["changed"]) == 1
    assert result["changed"][0] == ("Person", 1, 2)
