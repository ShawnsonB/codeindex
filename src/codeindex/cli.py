import argparse
import json
import sys
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.syntax import Syntax
from rich.table import Table

from codeindex.indexer import Indexer

console = Console()


def _positive_int(value: str) -> int:
    try:
        n = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"--n must be a positive integer, got {value!r}")
    if n < 1:
        raise argparse.ArgumentTypeError(f"--n must be a positive integer, got {n}")
    return n


def _find_store(start: Path) -> Path | None:
    for p in [start, *start.parents]:
        candidate = p / ".codeindex"
        if candidate.is_dir():
            return candidate
    return None


def _render_one_result(result: dict, index: int, total: int) -> None:
    lexer = Syntax.guess_lexer(result["path"], code=result["content"])
    syntax = Syntax(
        result["content"],
        lexer,
        line_numbers=True,
        start_line=result["start_line"],
        word_wrap=False,
        theme="monokai",
    )
    panel = Panel(
        syntax,
        title=f"[bold cyan]{result['path']}[/bold cyan]",
        title_align="left",
        subtitle=(
            f"lines {result['start_line']}–{result['end_line']}  "
            f"score [green]{result['score']:.3f}[/green]  "
            f"[dim]({index}/{total})[/dim]"
        ),
        subtitle_align="right",
        border_style="blue",
        padding=(0, 1),
    )
    console.print(panel)


def _render_results(results: list[dict], query: str) -> None:
    if not results:
        console.print(f"\n[yellow]No results found for:[/yellow] {query}")
        return
    console.print()
    for i, r in enumerate(results, 1):
        _render_one_result(r, i, len(results))


def _render_status(indexer: Indexer) -> None:
    s = indexer.status()
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column(style="bold")
    table.add_column()
    table.add_row("Root", s["root"])
    table.add_row("Indexed files", str(s["indexed_files"]))
    table.add_row("Indexed chunks", str(s["indexed_chunks"]))
    console.print(table)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="codeindex-query",
        description="Query a codeindex semantic search index.",
    )
    parser.add_argument(
        "query",
        nargs="?",
        default=None,
        help="Query string. Omit to enter interactive REPL mode.",
    )
    parser.add_argument(
        "--store",
        default=None,
        metavar="PATH",
        help="Path to .codeindex store directory (auto-detected from CWD if omitted).",
    )
    parser.add_argument(
        "--root",
        default=None,
        metavar="PATH",
        help="Root directory the index was built from (read from store meta.json if omitted).",
    )
    parser.add_argument(
        "--n",
        type=_positive_int,
        default=5,
        metavar="INT",
        help="Number of results to return (default: 5, must be >= 1).",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Show index statistics and exit.",
    )
    return parser


def _resolve_indexer(args) -> Indexer:
    cwd = Path.cwd()

    if args.store:
        store_path = Path(args.store).resolve()
    else:
        store_path = _find_store(cwd)
        if store_path is None:
            console.print(
                "[red]Error:[/red] No .codeindex store found walking up from CWD. "
                "Run the codeindex MCP server first to build an index, "
                "or pass [bold]--store PATH[/bold].",
                highlight=False,
            )
            sys.exit(1)

    if not store_path.is_dir():
        console.print(f"[red]Error:[/red] Store path does not exist: {store_path}")
        sys.exit(1)

    if args.root:
        root = Path(args.root).resolve()
    else:
        meta_file = store_path / "meta.json"
        if meta_file.exists():
            try:
                root = Path(json.loads(meta_file.read_text())["root"])
            except (KeyError, json.JSONDecodeError, OSError):
                root = store_path.parent
        else:
            root = store_path.parent

    if not root.is_dir():
        console.print(f"[red]Error:[/red] Root path does not exist: {root}")
        sys.exit(1)

    return Indexer(root, store_path)


def _main(args) -> None:
    indexer = _resolve_indexer(args)

    if args.status:
        _render_status(indexer)
        return

    if args.query is not None:
        results = indexer.search(args.query, args.n)
        _render_results(results, args.query)
        return

    console.print(
        "[bold]codeindex interactive query[/bold]  "
        "[dim](Ctrl-C or Ctrl-D to quit)[/dim]"
    )
    console.print(Rule(style="dim"))
    while True:
        try:
            query = console.input("[bold cyan]> [/bold cyan]").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n[dim]Bye.[/dim]")
            break
        if not query:
            continue
        results = indexer.search(query, args.n)
        _render_results(results, query)


def run() -> None:
    _main(_build_parser().parse_args())
