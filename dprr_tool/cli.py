import logging
from pathlib import Path

import click
from rich.console import Console
from rich.syntax import Syntax
from rich.table import Table

from dprr_tool.store import execute_query, get_or_create_store, get_read_only_store, is_initialized, load_rdf

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
@click.option(
    "--log-level",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR"], case_sensitive=False),
    default="WARNING",
    help="Set logging level.",
)
@click.pass_context
def cli(ctx, store_path: Path, log_level: str):
    """dprr-tool: Natural language SPARQL for the Roman Republic."""
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format="%(levelname)s: %(name)s: %(message)s",
    )
    ctx.ensure_object(dict)
    ctx.obj["store_path"] = store_path


@cli.command()
@click.argument("rdf_file", type=click.Path(exists=True, path_type=Path))
@click.option("--force", is_flag=True, help="Reinitialize even if the store already contains data.")
@click.pass_context
def init(ctx, rdf_file: Path, force: bool):
    """Load DPRR RDF data into the local Oxigraph store."""
    import shutil

    store_path = ctx.obj["store_path"] / "store"
    if is_initialized(store_path) and not force:
        store = get_read_only_store(store_path)
        console.print(
            f"[yellow]Store already contains {len(store)} triples. "
            f"Use --force to reinitialize.[/yellow]"
        )
        return
    if force and store_path.exists():
        shutil.rmtree(store_path)
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
        console.print("Run [bold]dprr-tool init <rdf-file>[/bold] to load DPRR data.")
        return
    store = get_read_only_store(store_path)
    console.print(f"Store path: [bold]{store_path}[/bold]")
    console.print(f"Triple count: [bold]{len(store)}[/bold]")


@cli.command()
@click.argument("sparql_query", type=str)
@click.pass_context
def query(ctx, sparql_query: str):
    """Execute a raw SPARQL query against the local store."""
    store_path = ctx.obj["store_path"] / "store"
    if not is_initialized(store_path):
        console.print("[red]Store is not initialized. Run 'dprr-tool init' first.[/red]")
        raise SystemExit(1)
    store = get_read_only_store(store_path)
    console.print(Syntax(sparql_query, "sparql", theme="monokai"))
    try:
        rows = execute_query(store, sparql_query)
    except Exception as e:
        console.print(f"[red]Query error: {e}[/red]")
        raise SystemExit(1)
    _print_results_table(rows)


@cli.command()
@click.option("--host", default="127.0.0.1", help="Bind host (default: 127.0.0.1)")
@click.option("--port", default=8000, type=int, help="Bind port (default: 8000)")
@click.pass_context
def serve(ctx, host, port):
    """Start the MCP server over HTTP for use with Claude Code, Claude Desktop, etc."""
    import os

    store_path = ctx.obj["store_path"]
    os.environ.setdefault("DPRR_STORE_PATH", str(store_path / "store"))

    from dprr_tool.mcp_server import mcp

    mcp.settings.host = host
    mcp.settings.port = port
    mcp.run(transport="streamable-http")


MAX_DISPLAY_ROWS = 100


def _print_results_table(rows: list[dict]):
    if not rows:
        console.print("[yellow]No results.[/yellow]")
        return
    table = Table(show_header=True, header_style="bold")
    for col in rows[0].keys():
        table.add_column(col)
    for row in rows[:MAX_DISPLAY_ROWS]:
        table.add_row(*(str(row.get(col, "")) for col in rows[0].keys()))
    console.print(f"\n[bold]{len(rows)} results:[/bold]")
    console.print(table)
    if len(rows) > MAX_DISPLAY_ROWS:
        console.print(f"[yellow](Showing first {MAX_DISPLAY_ROWS} of {len(rows)} results)[/yellow]")
