import argparse
import asyncio
import sys
import threading
from pathlib import Path
from typing import Any

import mcp.server.stdio
import mcp.types as types
from mcp.server.lowlevel import NotificationOptions, Server
from mcp.server.models import InitializationOptions

from indexer import Indexer
from watcher import FileWatcher

server = Server("codeindex")
_indexer: Indexer | None = None
_watcher: FileWatcher | None = None


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="search_codebase",
            description=(
                "Semantically search indexed source code. Returns matching code chunks "
                "with file path and line numbers. Use this to find where logic lives, "
                "how a system is implemented, or what uses a given type or method."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Natural language or code query, e.g. 'how is player health damage applied'",
                    },
                    "n_results": {
                        "type": "integer",
                        "description": "Number of results to return (default 5, max 20)",
                        "default": 5,
                    },
                },
                "required": ["query"],
            },
        ),
        types.Tool(
            name="index_status",
            description="Returns the current state of the code index: root path, file count, and chunk count.",
            inputSchema={"type": "object", "properties": {}},
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[types.TextContent]:
    if name == "search_codebase":
        query = arguments["query"]
        n = min(int(arguments.get("n_results", 5)), 20)
        loop = asyncio.get_event_loop()
        results = await loop.run_in_executor(None, lambda: _indexer.search(query, n))

        if not results:
            return [types.TextContent(type="text", text="No results found — index may still be building.")]

        parts = []
        for r in results:
            ext = Path(r["path"]).suffix.lower()
            lang = {".cs": "csharp", ".php": "php"}.get(ext, "")
            parts.append(f"### {r['path']} (lines {r['start_line']}–{r['end_line']}, score {r['score']})")
            parts.append(f"```{lang}")
            parts.append(r["content"])
            parts.append("```")
            parts.append("")
        return [types.TextContent(type="text", text="\n".join(parts))]

    if name == "index_status":
        s = _indexer.status()
        text = f"Root:           {s['root']}\nIndexed files:  {s['indexed_files']}\nIndexed chunks: {s['indexed_chunks']}"
        return [types.TextContent(type="text", text=text)]

    raise ValueError(f"Unknown tool: {name}")


def _initial_index(indexer: Indexer, extensions: tuple[str, ...]):
    count = indexer.index_all(extensions)
    print(f"[codeindex] initial index complete: {count} file(s) updated", file=sys.stderr, flush=True)


def _find_git_root(start: Path) -> Path | None:
    """Walk up from start until a .git directory is found."""
    for parent in [start, *start.parents]:
        if (parent / ".git").exists():
            return parent
    return None


async def main():
    global _indexer, _watcher

    parser = argparse.ArgumentParser(description="codeindex MCP server")
    parser.add_argument("--root", required=True, help="Root directory to index")
    parser.add_argument(
        "--ext",
        default=".cs",
        help="Comma-separated file extensions to index (default: .cs)",
    )
    parser.add_argument(
        "--store",
        default=None,
        help="Directory to persist the index (default: {git_root}/.codeindex or {root}/.codeindex)",
    )
    args = parser.parse_args()

    root = Path(args.root).resolve()
    extensions = tuple(e.strip() for e in args.ext.split(","))

    if not root.is_dir():
        print(f"[codeindex] ERROR: --root '{root}' is not a directory", file=sys.stderr)
        sys.exit(1)

    if args.store:
        store_path = Path(args.store).resolve()
    else:
        git_root = _find_git_root(root)
        store_path = (git_root if git_root else root) / ".codeindex"

    print(f"[codeindex] store: {store_path}", file=sys.stderr, flush=True)

    _indexer = Indexer(root, store_path)

    threading.Thread(target=_initial_index, args=(_indexer, extensions), daemon=True).start()

    _watcher = FileWatcher(_indexer, root, extensions)
    _watcher.start()

    print(f"[codeindex] watching {root} for {extensions}", file=sys.stderr, flush=True)

    try:
        async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
            await server.run(
                read_stream,
                write_stream,
                InitializationOptions(
                    server_name="codeindex",
                    server_version="0.1.0",
                    capabilities=server.get_capabilities(
                        notification_options=NotificationOptions(),
                        experimental_capabilities={},
                    ),
                ),
            )
    finally:
        _watcher.stop()


if __name__ == "__main__":
    asyncio.run(main())
