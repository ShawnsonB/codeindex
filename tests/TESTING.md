# codeindex Test Guide

How to run, extend, and interpret the smoke tests in `tests/test_codeindex.py`.

---

## Quick start

```bash
# From Workspace root:
/home/shawn/Workspace/codeindex/.venv/bin/python codeindex/tests/test_codeindex.py

# Or from inside codeindex/:
cd /home/shawn/Workspace/codeindex && .venv/bin/python tests/test_codeindex.py
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

### Workspace layout

```
codeindex/
├── indexer.py              ← the package under test
├── .venv/
└── tests/
    ├── test_codeindex.py
    ├── TESTING.md
    └── fixtures/
        ├── csharp/         ← 5 synthetic C# files (IDamageable, Player, Enemy, HealthSystem, CombatManager)
        ├── php/            ← 3 PHP files (UserRepository, Authenticator, Status)
        └── c/              ← 6 C/C++ files (player, physics, allocator — .h + .cpp each)
```

---

## Known issues (pre-existing, not regressions)

### 1. Negative scores from DefaultEmbeddingFunction

Several "top result has a positive score" checks **fail** for both C# and C/C++:

```
[FAIL] top result has a positive score: score=-0.019   ← C#
[FAIL] top result has a positive score: score=-0.224   ← C/C++
```

**Cause:** `DefaultEmbeddingFunction` from chromadb uses cosine distance.
The score is computed as `1.0 - distance`. When the distance exceeds 1.0
(which happens with this embedding function on short or out-of-domain
chunks), the score goes negative. This is not a bug in the chunker or
indexer logic — it is a limitation of the default embedder.

**Impact:** Semantic search still returns the right files; only the score
value is misleading. PHP tests pass this check because the PHP test corpus
is coherent enough that distances stay under 1.0.

**Fix when desired:** Replace `DefaultEmbeddingFunction` with a real model
(e.g. `SentenceTransformerEmbeddingFunction`). The test check is kept as-is
to surface if the situation changes.

### 2. `if (` / `for (` / `while (` are false-positive split points in C/C++

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

When a new language is added to `_CHUNKERS` in `indexer.py`:

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
from indexer import (
    _chunk,
    _CS_DECL_RE,   # C#
    _PHP_DECL_RE,  # PHP
    _C_DECL_RE,    # C / C++ / .h / .hpp
    Indexer,
)
```

`_CHUNKERS` (the extension→regex registry) and `_DECL_RE` (legacy alias for
`_CS_DECL_RE`) are also importable if needed for introspection.

---

## Interpreting output

```
[PASS] ...   green  — assertion held
[FAIL] ...   red    — assertion failed; detail printed after the colon
```

FAIL lines that match the known-issues above are expected. Any other FAIL
line indicates a genuine regression.

At the end of each section a summary line prints:
```
  PHP chunker: all good
  C/C++ chunker: all good
```
or `FAILURES ABOVE` if any check in that section failed.
