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
    assert "BC" in prompt
    assert "PostAssertion" in prompt
    assert "SPARQL" in prompt
    assert "vocab:Person" in prompt
    assert "vocab:PostAssertion" in prompt
    assert "PREFIX" in prompt
    # Tips section
    assert "Query Tips" in prompt
    assert "FILTER NOT EXISTS" in prompt
    assert "STR(" in prompt
    assert "BIND" in prompt


def test_build_synthesis_prompt():
    prompt = build_synthesis_prompt()
    assert "Broughton" in prompt or "secondary source" in prompt.lower()
    assert "uncertain" in prompt.lower()
    assert "BC" in prompt
