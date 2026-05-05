# Fix: Replace DefaultEmbeddingFunction with a code-aware model

## Problem

`DefaultEmbeddingFunction` (chromadb's built-in) uses `all-MiniLM-L6-v2` via ONNX — a
general-purpose sentence model trained on natural language, not code. When it embeds short
code chunks, the cosine distance between a natural-language query and a code document
regularly exceeds 1.0, which makes the score (`1.0 - distance`) go negative:

```
[FAIL] top result has a positive score: score=-0.119   ← C#
[FAIL] top result has a positive score: score=-0.224   ← C/C++
```

The correct files are still returned, but relevance ranking is unreliable and the scores
are meaningless.

## Fix

Replace `DefaultEmbeddingFunction` with `SentenceTransformerEmbeddingFunction` using
`BAAI/bge-base-en-v1.5`. This model scores significantly better on code search benchmarks
than `all-MiniLM-L6-v2` while remaining fast enough for local use (~400 MB download,
runs on CPU).

### 1. Add `sentence-transformers` to `pyproject.toml`

```toml
dependencies = [
    "chromadb>=0.6",
    "mcp>=1.0",
    "sentence-transformers>=3.0",
    "watchdog>=4.0",
]
```

### 2. Install it into the venv

```bash
.venv/bin/pip install sentence-transformers
```

### 3. Update `indexer.py`

Replace the import:

```python
# before
from chromadb.utils.embedding_functions import DefaultEmbeddingFunction
```

```python
# after
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
```

Replace the embedding function passed to `get_or_create_collection`:

```python
# before
embedding_function=DefaultEmbeddingFunction(),
```

```python
# after
embedding_function=SentenceTransformerEmbeddingFunction(model_name="BAAI/bge-base-en-v1.5"),
```

That is the only code change required.

### 4. Re-index all existing stores

The embedding function is baked into each ChromaDB collection at creation time. Any
collection created with `DefaultEmbeddingFunction` must be deleted and re-indexed:

```bash
# If using the persistent store location (default: ~/.codeindex or wherever server.py points):
rm -rf <store_path>/db

# Then re-index:
.venv/bin/python -m codeindex  # or however the server is started
```

The test suite uses `tempfile.TemporaryDirectory()` for every indexer test, so tests
automatically use the new function without any cleanup step.

### 5. Update `tests/TESTING.md`

Remove the known-issue entry for negative scores once the fix is confirmed.

## Why `BAAI/bge-base-en-v1.5`

| Model | Size | Notes |
|---|---|---|
| `all-MiniLM-L6-v2` (current) | ~80 MB | Fast, general NLP. Breaks on code. |
| `BAAI/bge-base-en-v1.5` | ~440 MB | Strong on asymmetric search (short query vs long doc). Handles mixed prose+code well. |
| `jinaai/jina-embeddings-v2-base-code` | ~320 MB | Code-first, supports 30 languages. Better if queries are code snippets rather than natural language. |

`bge-base-en-v1.5` is the right default here because the search queries are natural
language ("how is damage applied to the player") against code documents — an asymmetric
task where BGE excels. Jina's code model would be preferable if the primary use case
shifts to code-to-code search (e.g. "find functions that call TakeDamage").

## Expected outcome

Scores for the C# and C/C++ indexer tests should turn positive, and the
"top result has a positive score" checks should flip from `[FAIL]` to `[PASS]`.
