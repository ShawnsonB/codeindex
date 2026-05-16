# codeindex Test Guide

How to run, extend, and interpret the smoke tests in `tests/test_codeindex.py`.

---

## Quick start

```bash
# From the repository root:
.venv/bin/python tests/test_codeindex.py
```

Running with plain `python tests/test_codeindex.py` fails with
`ModuleNotFoundError: No module named 'chromadb'` because the system Python
doesn't have the project's dependencies. Always use the venv.

---

## What the test covers

| Section | What it tests |
|---|---|
| 1. PHP chunker unit test | Split points, excluded anonymous closures/arrow fns, enum/trait/interface detection |
| 2. C# indexer smoke test | Indexes `tests/fixtures/csharp` (5 synthetic files), semantic search |
| 3. PHP indexer smoke test | Indexes `tests/fixtures/php` (3 files), semantic search |
| 4. C/C++ chunker unit test | Split points for struct/enum/union/class/operator/ctor/dtor, lambda exclusion |
| 5. C/C++ indexer smoke test | Indexes `tests/fixtures/c` (6 files: 3 `.h` + 3 `.cpp`), semantic search |
| 6. Python chunker unit test | `def`, `async def`, `class` split points; lambda exclusion |
| 7. Python indexer smoke test | Indexes `tests/fixtures/python` (1 file), semantic search |
| 8. Java chunker unit test | `class`, `interface`, `enum`, constructor, method, `@FunctionalInterface` handling |
| 9. Java indexer smoke test | Indexes `tests/fixtures/java` (2 files), semantic search |
| 10. Go chunker unit test | `func`, `type … struct/interface`, goroutine literal exclusion |
| 11. Go indexer smoke test | Indexes `tests/fixtures/go` (2 files), semantic search |
| 12. Rust chunker unit test | `fn`, `impl`, `struct`, `enum`, `trait`, `macro_rules!`, `pub(crate)`, `unsafe fn` |
| 13. Rust indexer smoke test | Indexes `tests/fixtures/rust` (1 file), semantic search |
| 14. JavaScript chunker unit test | `function`, `class`, arrow/expression assignments, `export default` |
| 15. JavaScript indexer smoke test | Indexes `tests/fixtures/javascript` (1 file), semantic search |
| 16. TypeScript chunker unit test | All JS patterns plus `interface`, `enum`, `type`, `export abstract class` |
| 17. TypeScript indexer smoke test | Indexes `tests/fixtures/typescript` (1 file), semantic search |
| 18. Ruby chunker unit test | `def`, `def self.*`, `module`, `class`, `attr_reader` |
| 19. Ruby indexer smoke test | Indexes `tests/fixtures/ruby` (1 file), semantic search |
| 20. SQL chunker unit test | `CREATE TABLE/VIEW/INDEX`, `ALTER TABLE`, `DROP TABLE`, `CREATE OR REPLACE VIEW` |
| 21. SQL indexer smoke test | Indexes `tests/fixtures/sql` (1 file), semantic search |
| 22. Assembly chunker unit test | Column-0 labels, `section .…` directives |
| 23. Assembly indexer smoke test | Indexes `tests/fixtures/assembly` (1 file), semantic search |

### Workspace layout

```
codeindex/
├── src/
│   └── codeindex/
│       ├── __init__.py
│       ├── indexer.py      ← the package under test
│       ├── server.py
│       └── watcher.py
├── .venv/
└── tests/
    ├── test_codeindex.py
    ├── TESTING.md
    └── fixtures/
        ├── csharp/         ← 5 synthetic C# files
        ├── php/            ← 3 PHP files
        ├── c/              ← 6 C/C++ files (3 .h + 3 .cpp)
        ├── python/         ← 1 Python file (combat.py)
        ├── java/           ← 2 Java files (Player.java, CombatSystem.java)
        ├── go/             ← 2 Go files (server.go, database.go)
        ├── rust/           ← 1 Rust file (engine.rs)
        ├── javascript/     ← 1 JS file (api.js)
        ├── typescript/     ← 1 TS file (models.ts)
        ├── ruby/           ← 1 Ruby file (user.rb)
        ├── sql/            ← 1 SQL file (schema.sql)
        └── assembly/       ← 1 ASM file (math.asm)
```

---

## Known issues (pre-existing, not regressions)

### `if (` / `for (` / `while (` are false-positive split points in C/C++

`_C_DECL_RE` matches any `word(` pattern at line start (unless the line
begins with `#`). This means control-flow keywords inside function bodies
also trigger splits. Example from `player.cpp`:

```cpp
void Player::applyDamage(int amount) {
    m_health -= amount;
    if (m_health < 0) m_health = 0;   // ← "if (" matches _C_DECL_RE
    updateState();
}
```

**Observable symptom:** 74 chunks for only 6 small files (~12 chunks/file).
The "damage" query's top chunk was the single line
`void Player::heal(int amount) {` instead of the full `applyDamage` body.

**Impact:** Search still returns the correct file; the snippet just lands in
a smaller fragment. The code comment in `indexer.py` acknowledges this
trade-off ("the false-positive cost is low").

---

## Adding tests for a new language

When a new language is added to `_CHUNKERS` in `src/codeindex/indexer.py`:

1. **Create a test corpus directory** inside `tests/fixtures/`, e.g. `tests/fixtures/go/`
   with 3–6 source files that cover the domain vocabulary you'll search against.

2. **Add a chunker unit test** using a self-contained inline sample string
   (see `CPP_SAMPLE` or `PHP_SAMPLE` in the test file). Verify:
   - Type declarations are split points
   - Lambdas / anonymous functions / closures are NOT their own chunks
   - Preprocessor / decorator / attribute lines are NOT split points
   - At least one qualifier keyword (static, public, async…) is recognised

3. **Add an indexer smoke test** using `tempfile.TemporaryDirectory()` so
   the ChromaDB store is always fresh. Check:
   - `count` equals the number of source files
   - `indexed_chunks > indexed_files`
   - 2–3 semantic queries each return at least one result
   - Top result path ends in the expected extension(s)

4. **Update the import line** at the top of `test_codeindex.py` to include
   the new `_LANG_DECL_RE` symbol.

5. **Update the docstring** and the `C_ROOT` / `PHP_ROOT` style constant
   block near the top of the file.

---

## Importing from the indexer

```python
from codeindex.indexer import (
    _chunk,
    _CS_DECL_RE,    # C#
    _PHP_DECL_RE,   # PHP
    _C_DECL_RE,     # C / C++ / .h / .hpp / .cc / .cxx / .hh / .hxx
    _PY_DECL_RE,    # Python
    _JS_DECL_RE,    # JavaScript (.js / .mjs / .cjs)
    _TS_DECL_RE,    # TypeScript (.ts / .tsx)
    _JAVA_DECL_RE,  # Java
    _GO_DECL_RE,    # Go
    _RUBY_DECL_RE,  # Ruby
    _RUST_DECL_RE,  # Rust
    _SQL_DECL_RE,   # SQL
    _ASM_DECL_RE,   # Assembly (.asm / .s / .S)
    Indexer,
)
```

`_CHUNKERS` (the extension→regex registry) and `_ALL_EXTENSIONS` (a tuple of
all supported extensions, used as the default for `index_all()`) are also
importable if needed for introspection.

---

## Interpreting output

```
[PASS] ...   green  — assertion held
[FAIL] ...   red    — assertion failed; detail printed after the colon
```

FAIL lines that match the known issues above are expected. Any other FAIL
line indicates a genuine regression.

At the end of each section a summary line prints:
```
  PHP chunker: all good
  C/C++ chunker: all good
```
or `FAILURES ABOVE` if any check in that section failed.

