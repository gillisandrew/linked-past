import tempfile
from click.testing import CliRunner
from dprr_tool.cli import cli


def test_cli_help():
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "ask" in result.output
    assert "query" in result.output
    assert "init" in result.output
    assert "info" in result.output


def test_cli_info_no_store():
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as tmpdir:
        result = runner.invoke(cli, ["--store-path", tmpdir, "info"])
        assert result.exit_code == 0
        assert "not initialized" in result.output.lower() or "no data" in result.output.lower()
