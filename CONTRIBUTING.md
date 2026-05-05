# Contributing to codeindex

Thanks for your interest in contributing!

---

## Dev environment setup

### Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/)

### Install

```bash
git clone https://github.com/ShawnsonB/codeindex codeindex
cd codeindex
uv venv .venv
uv pip install -e ".[dev]" --python .venv/bin/python
```

### Run the tests

```bash
.venv/bin/python tests/test_codeindex.py
```

The tests require `sentence-transformers` to download `BAAI/bge-base-en-v1.5`
(~440 MB) on first run. Subsequent runs use the cached model.

---

## Adding support for a new language

All language chunkers live in `src/codeindex/indexer.py`. To add a new one:

1. **Write a declaration regex** that matches the start of a top-level or
   member declaration (function, class, method, etc.) for your language.
   Name it `_LANG_DECL_RE` following the existing pattern.

2. **Register the extension(s)** in the `_CHUNKERS` dict:
   ```python
   _CHUNKERS: dict[str, re.Pattern] = {
       ...
       ".go": _GO_DECL_RE,
   }
   ```

3. **Add test fixtures** under `tests/fixtures/<lang>/` — 3–6 representative
   source files whose content covers the vocabulary of typical search queries.

4. **Add tests** in `tests/test_codeindex.py`:
   - A chunker unit test using an inline sample string (see `PHP_SAMPLE` or
     `CPP_SAMPLE` for the pattern). Check that declarations are split points
     and that anonymous functions / lambdas are **not**.
   - An indexer smoke test using `tempfile.TemporaryDirectory()`. Check file
     count, chunk count, and that 2–3 semantic queries return results from the
     correct extension.

5. **Update `tests/TESTING.md`** to document the new section.

See `tests/TESTING.md` for full guidance on writing and interpreting tests.

---

## Pull request expectations

- Keep PRs focused — one feature or fix per PR.
- All existing tests must pass before merging.
- New chunkers must include the fixture files and test sections described
  above.
- Match the existing code style (no new linters or formatters needed).
