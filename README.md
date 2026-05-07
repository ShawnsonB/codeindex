# codeindex

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![MCP Compatible](https://img.shields.io/badge/MCP-compatible-purple.svg)](https://modelcontextprotocol.io/)

A local, free, self-hosted semantic code search tool that plugs into Claude Code as an MCP server. It indexes source files using vector embeddings, watches for changes, and exposes a `search_codebase` tool so Claude can find relevant code by meaning rather than exact text match.

No cloud, no subscription, no API keys. The index lives in your project directory and travels with it.

---

## How it works

1. On startup, the `codeindex` server indexes all source files under `--root` by splitting them into method-level chunks and embedding each chunk with `BAAI/bge-base-en-v1.5` via `sentence-transformers` (downloaded once on first run, ~440 MB).
2. Embeddings are stored in a local [ChromaDB](https://www.trychroma.com/) database at the configured store path.
3. A `watchdog` file watcher runs in the background and re-indexes any file the moment it's saved. Only changed files are re-processed (tracked via MD5 hash).
4. Claude Code connects to the server over stdio and calls `search_codebase` whenever it needs to locate code semantically.

---

## Requirements

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (used for venv and dependency management)

---

## Setup

### 1. Clone and install

```bash
cd ~/Workspace   # or wherever you keep tools
git clone https://github.com/ShawnsonB/codeindex codeindex
cd codeindex
uv venv .venv
uv pip install -e . --python .venv/bin/python
```

### 2. Register it with Claude Code

MCP servers for a project are configured in `~/.claude.json` under the `projects` key. Find the entry for your project path and add a `codeindex` entry to its `mcpServers` block:

```json
"codeindex": {
  "type": "stdio",
  "command": "/absolute/path/to/codeindex/.venv/bin/codeindex",
  "args": [
    "--root", "/path/to/your/project/src",
    "--store", "/path/to/your/project/.codeindex"
  ],
  "env": {}
}
```

**`--root`** — the directory to index (recursively). Point this at your source tree, e.g. `Assets/Scripts` for a Unity project.

**`--store`** — where to persist the ChromaDB database and hash file. Recommended: a `.codeindex/` directory at your repository root so the index location is consistent across machines. If omitted, the server auto-discovers the git root by walking up from `--root` and stores there.

### 3. Gitignore the store

Add `.codeindex/` to your project's `.gitignore`. The index is large binary data that changes on every file save — it rebuilds automatically on first run so there's no need to commit it.

```gitignore
.codeindex/
```

### 4. Restart Claude Code

The server starts automatically when Claude Code loads the project. Watch stderr for confirmation:

```
[codeindex] store: /your/project/.codeindex
[codeindex] watching /your/project/src for ('.cs',)
[codeindex] initial index complete: 47 file(s) updated
```

---

## Configuration reference

| Argument | Required | Default | Description |
|---|---|---|---|
| `--root` | Yes | — | Directory to index (recursive) |
| `--ext` | No | `.cs` | Comma-separated file extensions, e.g. `--ext .cs,.py` |
| `--store` | No | `{git_root}/.codeindex` | Where to persist ChromaDB data and the hash file |

---

## Querying from the terminal

In addition to Claude Code using `search_codebase` automatically during conversations, you can query the index yourself with `codeindex-query`.

### Invoking the CLI

Either activate the venv first:

```bash
source /path/to/codeindex/.venv/bin/activate
codeindex-query "your query here"
```

Or call the binary directly without activating:

```bash
/path/to/codeindex/.venv/bin/codeindex-query "your query here"
```

Run `codeindex-query` from anywhere inside the project you indexed — it walks up the directory tree to find the `.codeindex` store automatically.

### One-shot search

Pass a query as a positional argument and results print immediately:

```bash
codeindex-query "how is damage applied to the player"
codeindex-query --n 10 "entity spawning logic"
```

Each result renders as a syntax-highlighted panel showing the file path, the matching code with real line numbers, and a relevance score (higher is better, clamped to 0–1).

### Interactive REPL

Omit the query to enter a prompt loop — useful for exploring unfamiliar code:

```bash
codeindex-query
```

```
codeindex interactive query  (Ctrl-C or Ctrl-D to quit)
──────────────────────────────────────────────────────────────
> how is damage applied to the player
╭─ Combat/HealthComponent.cs ─────────────────────────────────╮
│  42  public void ApplyDamage(float amount, DamageType type) │
│  ...                                                        │
╰──────────────── lines 42–47  score 0.912  (1/5) ───────────╯
> player movement and jump logic
...
> ^C
Bye.
```

### Index status

```bash
codeindex-query --status
```

```
  Root            /home/you/Workspace/MyGame/Assets/Scripts
  Indexed files   47
  Indexed chunks  312
```

### Options

| Flag | Default | Description |
|---|---|---|
| `query` | — | Search query (positional, optional — omit for REPL mode) |
| `--n INT` | `5` | Number of results to return |
| `--status` | — | Print index statistics and exit |
| `--store PATH` | auto-detected | Path to `.codeindex` store directory |
| `--root PATH` | read from store meta.json | Root directory the index was built from |

`codeindex-query` auto-detects the store by walking up from the current directory looking for a `.codeindex` folder, so you can run it from anywhere inside your project without extra flags. Pass `--store` and `--root` explicitly when querying an index that lives outside the current directory tree.

---

## MCP tools

### `search_codebase`

Semantic search over the indexed source files.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `query` | string | required | Natural language or code query |
| `n_results` | integer | 5 | Number of chunks to return (max 20) |

Returns matching code chunks with file path, line range, and a relevance score (higher is better, clamped to 0–1).

Example queries:
- `"how is damage applied to the player"`
- `"ladder interaction and placement logic"`
- `"IDamageable implementation"`

### `index_status`

Returns the current state of the index: root path, store path, number of indexed files, and number of indexed chunks. Useful for confirming the server is running and the initial index has completed.

---

## Storage layout

```
your-project/
  .codeindex/           ← gitignored, auto-created on first run
    db/                 ← ChromaDB sqlite and vector data
    hashes.json         ← MD5 fingerprints for incremental indexing
```

---

## Chunking strategy

Source files are split at declaration boundaries by detecting lines that begin with language-specific keywords. Everything before the first detected declaration is kept as a preamble chunk (imports, namespace, class header). This gives method-level granularity without requiring a full language parser.

**C# (`.cs`)** — splits on lines that begin with one or more access/modifier keywords (`public`, `private`, `protected`, `internal`, `static`, `virtual`, `override`, `abstract`, `async`, `sealed`, `partial`, `readonly`, `new`, `extern`), covering methods, properties, constructors, and type declarations.

**PHP (`.php`)** — splits on named function/method declarations (including optional visibility and modifier keywords before `function`) and type declarations (`class`, `abstract class`, `final class`, `interface`, `trait`, `enum`). Anonymous closures (`$fn = function() {`) and arrow functions (`fn() =>`) are intentionally **not** treated as split points, since they are inline expressions rather than declaration boundaries.

**C/C++ (`.c`, `.cpp`, `.h`, `.hpp`)** — splits on function definitions (free functions, methods, operator overloads, constructors, and destructors) and type declarations (`struct`, `class`, `union`, `enum`, `enum class`). Common specifiers such as `inline`, `static`, `extern`, `virtual`, `explicit`, `constexpr`, and MSVC calling-convention attributes are recognised as optional prefixes. Preprocessor directives (`#define`, `#include`, etc.) are never treated as split points.

For extensions without a registered chunker the file is stored as a single chunk (same as if no split points were found). To add support for another language, add a compiled regex to the `_CHUNKERS` dict in `indexer.py`.

---

## Adding to a second project

Each project gets its own isolated index. Add a second entry to `~/.claude.json` under the new project's path, pointing `--root` and `--store` at the new project's directories. No other configuration is shared between projects.

**C# project:**

```json
"/home/you/Workspace/MyGame": {
  "mcpServers": {
    "codeindex": {
      "type": "stdio",
      "command": "/home/you/Workspace/codeindex/.venv/bin/codeindex",
      "args": [
        "--root", "/home/you/Workspace/MyGame/Assets/Scripts",
        "--store", "/home/you/Workspace/MyGame/.codeindex"
      ],
      "env": {}
    }
  }
}
```

**PHP project:**

```json
"/home/you/Workspace/MyApp": {
  "mcpServers": {
    "codeindex": {
      "type": "stdio",
      "command": "/home/you/Workspace/codeindex/.venv/bin/codeindex",
      "args": [
        "--root", "/home/you/Workspace/MyApp/src",
        "--store", "/home/you/Workspace/MyApp/.codeindex",
        "--ext", ".php"
      ],
      "env": {}
    }
  }
}
```

**C/C++ project:**

```json
"/home/you/Workspace/MyEngine": {
  "mcpServers": {
    "codeindex": {
      "type": "stdio",
      "command": "/home/you/Workspace/codeindex/.venv/bin/codeindex",
      "args": [
        "--root", "/home/you/Workspace/MyEngine/src",
        "--store", "/home/you/Workspace/MyEngine/.codeindex",
        "--ext", ".cpp,.h,.hpp,.c"
      ],
      "env": {}
    }
  }
}
```
