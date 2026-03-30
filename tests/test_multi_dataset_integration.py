from linked_past.datasets.dprr.plugin import DPRRPlugin
from linked_past.datasets.pleiades.plugin import PleiadesPlugin
from linked_past.datasets.periodo.plugin import PeriodOPlugin
from linked_past.datasets.nomisma.plugin import NomismaPlugin
from linked_past.core.server import create_mcp_server


def test_all_plugins_instantiate():
    plugins = [DPRRPlugin(), PleiadesPlugin(), PeriodOPlugin(), NomismaPlugin()]
    names = {p.name for p in plugins}
    assert names == {"dprr", "pleiades", "periodo", "nomisma"}


def test_all_plugins_have_schemas():
    for Plugin in [DPRRPlugin, PleiadesPlugin, PeriodOPlugin, NomismaPlugin]:
        plugin = Plugin()
        schema = plugin.get_schema()
        assert "## Prefixes" in schema
        assert "## Classes" in schema


def test_all_plugins_have_prefixes():
    for Plugin in [DPRRPlugin, PleiadesPlugin, PeriodOPlugin, NomismaPlugin]:
        plugin = Plugin()
        prefixes = plugin.get_prefixes()
        assert len(prefixes) > 0


def test_all_plugins_validate():
    for Plugin in [DPRRPlugin, PleiadesPlugin, PeriodOPlugin, NomismaPlugin]:
        plugin = Plugin()
        result = plugin.validate("SELECT ?s WHERE { ?s ?p ?o } LIMIT 1")
        assert result.valid is True


def test_server_registers_all_plugins():
    mcp = create_mcp_server()
    tool_names = [t.name for t in mcp._tool_manager.list_tools()]
    assert "discover_datasets" in tool_names
    assert "query" in tool_names
