import tempfile
from pathlib import Path
from unittest.mock import MagicMock

from dprr_tool.pipeline import (
    extract_question,
    generate_sparql,
    synthesize_response,
    run_pipeline,
    StructuredQuestion,
    PipelineResult,
)
from dprr_tool.store import get_or_create_store, load_rdf
from tests.test_store import SAMPLE_TURTLE


def _mock_extraction_client():
    mock_client = MagicMock()
    mock_block = MagicMock()
    mock_block.type = "tool_use"
    mock_block.name = "extract_question"
    mock_block.input = {
        "intent": "query_data",
        "extracted_classes": ["Person", "PostAssertion", "Office"],
        "extracted_entities": ["consul"],
        "question_steps": ["Find PostAssertions for consul office", "Get person names"],
    }
    mock_response = MagicMock()
    mock_response.content = [mock_block]
    mock_client.messages.create.return_value = mock_response
    return mock_client


def test_extract_question():
    client = _mock_extraction_client()
    result = extract_question("Who were the consuls in 200 BC?", client)
    assert isinstance(result, StructuredQuestion)
    assert result.intent == "query_data"
    assert "Person" in result.extracted_classes
    client.messages.create.assert_called_once()


def test_extract_question_api_params():
    client = _mock_extraction_client()
    extract_question("Test", client)
    kwargs = client.messages.create.call_args.kwargs
    assert kwargs["temperature"] == 0
    assert len(kwargs["tools"]) == 1
    assert kwargs["tools"][0]["name"] == "extract_question"
    assert kwargs["tool_choice"] == {"type": "tool", "name": "extract_question"}


def _mock_generation_client(sparql_text):
    mock_client = MagicMock()
    mock_block = MagicMock()
    mock_block.type = "text"
    mock_block.text = f"Here is the query:\n\n```sparql\n{sparql_text}\n```"
    mock_response = MagicMock()
    mock_response.content = [mock_block]
    mock_response.stop_reason = "end_turn"
    mock_client.messages.create.return_value = mock_response
    return mock_client


def test_generate_sparql():
    sparql = "PREFIX vocab: <http://romanrepublic.ac.uk/rdf/entity/vocab/>\nSELECT ?person WHERE { ?person a vocab:Person . }"
    client = _mock_generation_client(sparql)
    extraction = StructuredQuestion("query_data", ["Person"], [], ["Find persons"])
    result = generate_sparql("List persons", extraction, client)
    assert "SELECT" in result
    assert "vocab:Person" in result


def test_generate_sparql_retries():
    client = MagicMock()

    bad_block = MagicMock()
    bad_block.type = "text"
    bad_block.text = "```sparql\nSELCT ?x WHERE { ?x ?p ?o }\n```"
    bad_resp = MagicMock()
    bad_resp.content = [bad_block]
    bad_resp.stop_reason = "end_turn"

    good_sparql = "PREFIX vocab: <http://romanrepublic.ac.uk/rdf/entity/vocab/>\nSELECT ?x WHERE { ?x a vocab:Person . }"
    good_block = MagicMock()
    good_block.type = "text"
    good_block.text = f"```sparql\n{good_sparql}\n```"
    good_resp = MagicMock()
    good_resp.content = [good_block]
    good_resp.stop_reason = "end_turn"

    client.messages.create.side_effect = [bad_resp, good_resp]
    extraction = StructuredQuestion("query_data", ["Person"], [], ["Find persons"])
    result = generate_sparql("Find persons", extraction, client)
    assert "SELECT" in result
    assert client.messages.create.call_count == 2


def test_synthesize_response():
    client = MagicMock()
    mock_block = MagicMock()
    mock_block.type = "text"
    mock_block.text = "The DPRR records 2 consuls for 509 BC."
    mock_resp = MagicMock()
    mock_resp.content = [mock_block]
    client.messages.create.return_value = mock_resp

    result = synthesize_response(
        question="Who were the first consuls?",
        sparql="SELECT ...",
        rows=[{"name": "L. Iunius Brutus"}, {"name": "L. Tarquinius Collatinus"}],
        client=client,
    )
    assert "consuls" in result.lower() or "509" in result
    client.messages.create.assert_called_once()


def test_synthesize_includes_data_in_message():
    client = MagicMock()
    block = MagicMock()
    block.type = "text"
    block.text = "Summary."
    resp = MagicMock()
    resp.content = [block]
    client.messages.create.return_value = resp

    synthesize_response("Test", "SELECT ...", [{"a": "1"}], client)
    kwargs = client.messages.create.call_args.kwargs
    user_msg = kwargs["messages"][0]["content"]
    assert "SELECT ..." in user_msg
    assert "Test" in user_msg


def _make_test_store():
    tmpdir = tempfile.mkdtemp()
    store_path = Path(tmpdir) / "store"
    store = get_or_create_store(store_path)
    ttl_path = Path(tmpdir) / "test.ttl"
    ttl_path.write_text(SAMPLE_TURTLE)
    load_rdf(store, ttl_path)
    return store


def _mock_full_pipeline_client():
    client = MagicMock()

    # Call 1: extraction
    ext_block = MagicMock()
    ext_block.type = "tool_use"
    ext_block.name = "extract_question"
    ext_block.input = {
        "intent": "query_data",
        "extracted_classes": ["Person"],
        "extracted_entities": [],
        "question_steps": ["Find all persons"],
    }
    ext_resp = MagicMock()
    ext_resp.content = [ext_block]

    # Call 2: generation
    sparql = "PREFIX vocab: <http://romanrepublic.ac.uk/rdf/entity/vocab/>\nSELECT DISTINCT ?person ?name WHERE {\n    ?person a vocab:Person ;\n        vocab:hasPersonName ?name .\n}\nLIMIT 100"
    gen_block = MagicMock()
    gen_block.type = "text"
    gen_block.text = f"```sparql\n{sparql}\n```"
    gen_resp = MagicMock()
    gen_resp.content = [gen_block]
    gen_resp.stop_reason = "end_turn"

    # Call 3: synthesis
    synth_block = MagicMock()
    synth_block.type = "text"
    synth_block.text = "The DPRR contains 2 persons."
    synth_resp = MagicMock()
    synth_resp.content = [synth_block]

    client.messages.create.side_effect = [ext_resp, gen_resp, synth_resp]
    return client


def test_run_pipeline():
    store = _make_test_store()
    client = _mock_full_pipeline_client()
    result = run_pipeline("List all persons", store, client)

    assert isinstance(result, PipelineResult)
    assert result.sparql is not None
    assert "SELECT" in result.sparql
    assert len(result.rows) == 2
    assert result.synthesis is not None
    assert client.messages.create.call_count == 3
