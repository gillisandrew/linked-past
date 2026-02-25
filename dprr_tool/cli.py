from pathlib import Path

import click
from rich.console import Console
from rich.markdown import Markdown
from rich.syntax import Syntax
from rich.table import Table

from dprr_tool.store import get_or_create_store, is_initialized, load_rdf, execute_query

DEFAULT_STORE_PATH = Path.home() / ".dprr-tool"
console = Console()


@click.group()
@click.option("--store-path", type=click.Path(path_type=Path), default=DEFAULT_STORE_PATH, envvar="DPRR_STORE_PATH", help="Path to the Oxigraph store directory.")
@click.pass_context
def cli(ctx, store_path: Path):
    """dprr-tool: Natural language SPARQL for the Roman Republic."""
    ctx.ensure_object(dict)
    ctx.obj["store_path"] = store_path


@cli.command()
@click.argument("rdf_file", type=click.Path(exists=True, path_type=Path))
@click.pass_context
def init(ctx, rdf_file: Path):
    """Load DPRR RDF data into the local Oxigraph store."""
    store_path = ctx.obj["store_path"] / "store"
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
    from pyoxigraph import Store as OxStore
    store = OxStore(str(store_path))
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
    store = get_or_create_store(store_path)
    console.print(Syntax(sparql_query, "sparql", theme="monokai"))
    try:
        rows = execute_query(store, sparql_query)
    except Exception as e:
        console.print(f"[red]Query error: {e}[/red]")
        raise SystemExit(1)
    _print_results_table(rows)


@cli.command()
@click.argument("question", type=str)
@click.pass_context
def ask(ctx, question: str):
    """Ask a natural language question about the Roman Republic."""
    store_path = ctx.obj["store_path"] / "store"
    if not is_initialized(store_path):
        console.print("[red]Store is not initialized. Run 'dprr-tool init' first.[/red]")
        raise SystemExit(1)
    from anthropic import Anthropic
    from dprr_tool.pipeline import run_pipeline
    store = get_or_create_store(store_path)
    client = Anthropic()
    console.print(f"\n[bold]Question:[/bold] {question}\n")
    with console.status("Thinking..."):
        result = run_pipeline(question, store, client)
    if result.sparql:
        console.print("[bold]Generated SPARQL:[/bold]")
        console.print(Syntax(result.sparql, "sparql", theme="monokai"))
        console.print()
    if result.errors:
        for error in result.errors:
            console.print(f"[red]Error: {error}[/red]")
    if result.rows:
        _print_results_table(result.rows)
    if result.synthesis:
        console.print("\n[bold]Summary:[/bold]\n")
        console.print(Markdown(result.synthesis))


def _print_results_table(rows: list[dict]):
    if not rows:
        console.print("[yellow]No results.[/yellow]")
        return
    table = Table(show_header=True, header_style="bold")
    for col in rows[0].keys():
        table.add_column(col)
    for row in rows[:100]:
        table.add_row(*(str(row.get(col, "")) for col in rows[0].keys()))
    console.print(f"\n[bold]{len(rows)} results:[/bold]")
    console.print(table)
