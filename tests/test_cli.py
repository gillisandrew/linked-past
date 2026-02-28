import tempfile

from click.testing import CliRunner

from dprr_tool.cli import cli
from dprr_tool.store import get_or_create_store, load_rdf
from tests.test_store import SAMPLE_TURTLE


def test_cli_help():
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "query" in result.output
    assert "init" in result.output
    assert "info" in result.output
    assert "serve" in result.output


def test_cli_info_no_store():
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as tmpdir:
        result = runner.invoke(cli, ["--store-path", tmpdir, "info"])
        assert result.exit_code == 0
        assert "not initialized" in result.output.lower() or "no data" in result.output.lower()


def test_cli_init_loads_data(tmp_path):
    """init command loads RDF data and reports triple count."""
    runner = CliRunner()
    ttl_path = tmp_path / "test.ttl"
    ttl_path.write_text(SAMPLE_TURTLE)
    result = runner.invoke(cli, ["--store-path", str(tmp_path), "init", str(ttl_path)])
    assert result.exit_code == 0
    assert "Loaded" in result.output
    assert "triples" in result.output


def test_cli_info_with_data(tmp_path):
    """info command shows triple count when store has data."""
    runner = CliRunner()
    store_path = tmp_path / "store"
    store = get_or_create_store(store_path)
    ttl_path = tmp_path / "test.ttl"
    ttl_path.write_text(SAMPLE_TURTLE)
    load_rdf(store, ttl_path)
    del store
    result = runner.invoke(cli, ["--store-path", str(tmp_path), "info"])
    assert result.exit_code == 0
    assert "Triple count" in result.output


def test_cli_query_select(tmp_path):
    """query command executes SELECT and displays results."""
    runner = CliRunner()
    store_path = tmp_path / "store"
    store = get_or_create_store(store_path)
    ttl_path = tmp_path / "test.ttl"
    ttl_path.write_text(SAMPLE_TURTLE)
    load_rdf(store, ttl_path)
    del store
    sparql = (
        "PREFIX vocab: <http://romanrepublic.ac.uk/rdf/entity/vocab/> "
        "SELECT ?name WHERE { ?p a vocab:Person ; vocab:hasPersonName ?name }"
    )
    result = runner.invoke(cli, ["--store-path", str(tmp_path), "query", sparql])
    assert result.exit_code == 0
    assert "2 results" in result.output


def test_cli_query_no_store(tmp_path):
    """query command fails gracefully when store is not initialized."""
    runner = CliRunner()
    result = runner.invoke(cli, ["--store-path", str(tmp_path), "query", "SELECT ?x WHERE { ?x ?y ?z }"])
    assert result.exit_code != 0
    assert "not initialized" in result.output.lower()


def test_cli_serve_help():
    """serve command accepts --host and --port options."""
    runner = CliRunner()
    result = runner.invoke(cli, ["serve", "--help"])
    assert result.exit_code == 0
    assert "--host" in result.output
    assert "--port" in result.output
