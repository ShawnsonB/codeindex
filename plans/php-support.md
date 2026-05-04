# Plan: PHP Codebase Support

## Overview

codeindex currently works for any file extension (via `--ext`) but its chunking strategy is tightly coupled to C# syntax — the `_DECL_RE` regex in `indexer.py` only matches C# access/modifier keywords. For PHP files this means every file is stored as a single monolithic chunk rather than being split at meaningful declaration boundaries, which produces poor semantic search results.

This plan describes the changes needed to give PHP codebases the same method/class-level chunking granularity that C# projects already enjoy.

---

## What needs to change

### 1. PHP-aware chunking regex (`indexer.py`)

Add a `_PHP_DECL_RE` regex that matches the start of PHP declarations:

- **Functions and methods** — `function foo(`, including optional visibility and modifiers before it:
  - `public function foo(`
  - `private static function bar(`
  - `protected abstract function baz(`
  - `final public function qux(`
  - Top-level `function helper(` (no visibility keyword)
- **Class-like type declarations** — `class Foo`, `abstract class Foo`, `final class Foo`, `interface Foo`, `trait Foo`, `enum Foo`
- The regex must **not** split on anonymous functions / closures (e.g. `$fn = function() {`) or arrow functions (`fn() =>`), since those are inline expressions, not declaration boundaries.

Example pattern (illustrative):

```
^\s*(?:(?:abstract|final|readonly)\s+)*(?:class|interface|trait|enum)\s+\w
|
^\s*(?:(?:public|protected|private|static|abstract|final|static)\s+)*function\s+\w
```

The second arm must require at least one alphabetic character after `function ` to exclude anonymous closures assigned to variables (which are typically preceded by `=` on the same line or have `function(` with an immediate `(`).

---

### 2. Language-aware chunker dispatch (`indexer.py`)

Introduce a per-language chunker registry so that the correct regex is applied based on file extension. The simplest approach:

- Create a dict mapping extension → compiled regex, e.g.:
  ```python
  _CHUNKERS = {
      ".cs":  _DECL_RE,       # existing C# regex
      ".php": _PHP_DECL_RE,   # new PHP regex
  }
  ```
- Modify the `_chunk(content, rel_path)` function (or introduce a new signature) to accept a `language_re` parameter chosen by the caller based on the file extension.
- In `Indexer.index_file`, derive the extension from `path.suffix` and look up the correct regex before calling `_chunk`.
- For extensions with no registered chunker, fall back to the existing "one chunk per file" behaviour (same as today when `split_points` is empty).

---

### 3. `index_all` extension → language mapping (`indexer.py`)

`index_all` already iterates over the configured extensions. Update the call to `_chunk` inside `index_file` to pass the resolved regex so PHP files use the PHP chunker automatically when `.php` is included in `--ext`.

No changes are required to the watcher or server layers because they already call `index_file`, which handles per-file logic.

---

### 4. Server output language tag (`server.py`)

In `call_tool`, the search result is wrapped in a fenced code block tagged `\`\`\`csharp`. This is cosmetic but affects syntax highlighting in Claude's response. Change this to derive the fence language from the file extension of the matched chunk:

```python
FENCE_LANG = {".cs": "csharp", ".php": "php"}
lang = FENCE_LANG.get(Path(r["path"]).suffix, "")
parts.append(f"```{lang}")
```

---

### 5. Documentation updates (`README.md`)

- Update the **Chunking strategy** section to describe the multi-language approach and document that PHP is now natively supported alongside C#.
- Add a PHP usage example to the **Adding to a second project** section:
  ```json
  "--ext", ".php"
  ```
- Update the example startup log line to show `.php` extension output.
- Note that anonymous functions and arrow functions are intentionally not treated as chunk boundaries.

---

## What does NOT need to change

| Component | Reason unchanged |
|---|---|
| `watcher.py` | Extension-based file filtering is already generic; PHP files will be watched correctly once `.php` is passed via `--ext`. |
| ChromaDB / embedding layer | Embeddings are language-agnostic; the same `all-MiniLM-L6-v2` model handles PHP source text well. |
| CLI arguments (`server.py`) | `--ext .php` already works at the transport level; no new flags needed. |
| `pyproject.toml` | No new dependencies required. |
| Hash / incremental indexing | The MD5-based change detection in `hashes.json` is already file-agnostic. |

---

## File-by-file summary of changes

| File | Change |
|---|---|
| `indexer.py` | Add `_PHP_DECL_RE`, add `_CHUNKERS` dispatch dict, update `_chunk` to accept a regex param, update `Indexer.index_file` to resolve chunker by extension |
| `server.py` | Derive fence language tag from file extension in `call_tool` |
| `README.md` | Update chunking strategy docs, add PHP example |

---

## Validation

After implementation, test with a PHP project by running:

```bash
python server.py --root /path/to/php-project --ext .php
```

Verify with `index_status` that chunk count is significantly higher than file count (confirming the file is being split at declaration boundaries). Run a `search_codebase` query and confirm the returned chunks contain individual methods/classes rather than entire files.

---

## PHP chunking — edge cases to consider

| Edge case | Handling |
|---|---|
| Anonymous closures (`$fn = function() {`) | Exclude by requiring a word character directly after `function ` |
| Arrow functions (`fn($x) => $x * 2`) | Excluded — `fn` is a distinct keyword, not `function` |
| Abstract/interface method stubs (no body, ends with `;`) | Still valid split points; chunk will be short but semantically meaningful |
| PHP 8.1 `enum` with backed types (`enum Status: string`) | Regex arm for type declarations covers this |
| Nested anonymous classes (`new class {`) | `new class` pattern should be excluded from the class arm to avoid splitting on anonymous class instantiations |
| `__construct`, magic methods | Matched normally as `public function __construct(` — no special handling needed |
| Heredoc / nowdoc strings containing `function` keywords | Unlikely to match the leading-whitespace + modifier pattern; false positives are low risk |
