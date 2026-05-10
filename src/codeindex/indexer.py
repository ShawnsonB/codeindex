import hashlib
import json
import re
from pathlib import Path

import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

# Matches C# method, property, constructor, and type declaration lines.
# Requires at least one access/modifier keyword so we don't split on variable
# assignments or attribute lines.
_CS_DECL_RE = re.compile(
    r"^\s*(?:(?:public|private|protected|internal|static|virtual|override|"
    r"abstract|async|sealed|partial|readonly|new|extern)\s+)+"
    r"[\w<>\[\]?,\s]*\w\s*[\(\{<]"
)

# Matches PHP named function/method and type declarations.
# Excludes anonymous closures ($fn = function() {) by requiring a word character
# immediately after "function ". Arrow functions (fn($x) => ...) use a distinct
# keyword and are not matched here.
# Also excludes anonymous class instantiations (new class {).
_PHP_DECL_RE = re.compile(
    r"^\s*(?:(?:abstract|final|readonly)\s+)*(?:class|interface|trait|enum)\s+\w"
    r"|"
    r"^\s*(?:(?:public|protected|private|static|abstract|final)\s+)*function\s+\w"
)

# Matches C and C++ function definitions and type declarations.
# Covers:
#   - Free functions and methods:  ReturnType name(  or  Type* name(
#   - Operator overloads:          operator<op>(
#   - Constructors/destructors:    ClassName(  or  ~ClassName(
#   - Type declarations:           struct/class/union/enum (name or template<…> name)
# Excluded on purpose:
#   - Pure forward declarations (no body) are still split points — they are rare
#     at file scope and the false-positive cost is low.
#   - Preprocessor lines (#define, #include) are excluded by the leading non-# check.
#   - Variable declarations that happen to end with ( would be unusual; the regex
#     requires a word character immediately before ( to reduce those cases.
_C_DECL_RE = re.compile(
    r"^(?!\s*#)"                             # not a preprocessor directive
    r"\s*"
    r"(?:"
    r"(?:(?:inline|static|extern|virtual|explicit|constexpr|consteval|constinit|"
    r"__forceinline|__inline|__cdecl|__stdcall|__fastcall)\s+)*"
    r"(?:[\w:~*&<>, \t]+?)\s*(?:operator\s*[^\s(]+|\w+)\s*\("  # return-type name( or operator<op>(
    r"|"
    r"(?:struct|class|union|enum(?:\s+class)?)\s+\w"  # type declaration
    r")"
)

# Matches Python function and class declarations at any indentation level.
# Handles `async def` as well as plain `def` and `class`.
_PY_DECL_RE = re.compile(
    r"^\s*(?:async\s+)?def\s+\w"
    r"|"
    r"^\s*class\s+\w"
)

# Matches JavaScript function/class declarations, arrow-function assignments, and
# method shorthands that carry at least one modifier keyword (static, async, get,
# set) so bare `if (`, `for (`, etc. are not treated as method boundaries.
_JS_DECL_RE = re.compile(
    r"^\s*(?:export\s+(?:default\s+)?)?(?:async\s+)?function\s*\*?\s*\w"  # function keyword
    r"|"
    r"^\s*(?:export\s+(?:default\s+)?)?class\s+\w"  # class declaration
    r"|"
    r"^\s*(?:export\s+)?(?:const|let|var)\s+\w+\s*=\s*(?:async\s+)?(?:function\b|\([^)]*\)\s*=>|\w+\s*=>)"  # fn assignment
    r"|"
    r"^\s*(?:(?:static|async|get|set)\s+)+(?!(?:if|for|while|switch|return|throw|new|typeof|await|yield|else)\b)\w+\s*[(\[]"  # method with modifier
)

# TypeScript extends JavaScript with interfaces, enums, type aliases, and typed
# method signatures that carry access-modifier keywords.
_TS_DECL_RE = re.compile(
    r"^\s*(?:export\s+(?:default\s+)?)?(?:async\s+)?function\s*\*?\s*\w"
    r"|"
    r"^\s*(?:export\s+(?:default\s+)?)?(?:abstract\s+)?class\s+\w"
    r"|"
    r"^\s*(?:export\s+)?(?:const|let|var)\s+\w+\s*=\s*(?:async\s+)?(?:function\b|\([^)]*\)\s*=>|\w+\s*=>)"
    r"|"
    r"^\s*(?:export\s+)?interface\s+\w"
    r"|"
    r"^\s*(?:export\s+)?(?:const\s+)?enum\s+\w"
    r"|"
    r"^\s*(?:export\s+)?type\s+\w+\s*(?:<[^>]*>)?\s*="
    r"|"
    r"^\s*(?:(?:public|private|protected|static|async|readonly|abstract|override|get|set)\s+)+(?!(?:if|for|while|switch|return|throw|new|typeof|await|yield|else)\b)\w+\s*[(<]"
)

# Matches Java method, constructor, and type declarations.
# Requires at least one access/modifier keyword for method declarations to avoid
# matching control-flow lines. Top-level type declarations are matched directly.
_JAVA_DECL_RE = re.compile(
    r"^\s*(?:(?:public|protected|private|static|final|abstract|synchronized|"
    r"native|transient|volatile|default|strictfp)\s+)+"
    r"(?:[\w<>\[\]@.,\s]*\w\s*\(|(?:class|interface|enum|record)\s+\w)"
    r"|"
    r"^\s*(?:class|interface|enum|record)\s+\w"
    r"|"
    r"^\s*@interface\s+\w"  # annotation type declaration
)

# Matches Go function and method declarations, and named struct/interface types.
# Method receivers (`func (r *Receiver) Name(`) are handled by the optional
# `(?:\([^)]+\)\s*)?` group before the function name.
_GO_DECL_RE = re.compile(
    r"^\s*func\s+(?:\([^)]+\)\s*)?\w"
    r"|"
    r"^\s*type\s+\w+\s+(?:struct|interface)\b"
)

# Matches Ruby method, class, and module declarations.
# Handles `def self.method` class-level methods and common `attr_*` macros.
_RUBY_DECL_RE = re.compile(
    r"^\s*def\s+(?:self\.)?\w"
    r"|"
    r"^\s*(?:class|module)\s+\w"
    r"|"
    r"^\s*attr_(?:reader|writer|accessor)\b"
)

# Matches Rust item declarations: functions, impls, structs, enums, traits,
# unions, and macro_rules! blocks.  Handles optional visibility qualifiers
# (pub, pub(crate), pub(super), pub(in path)).
_RUST_DECL_RE = re.compile(
    r"^\s*(?:pub(?:\([^)]*\))?\s+)?(?:unsafe\s+)?(?:async\s+)?fn\s+\w"
    r"|"
    r"^\s*(?:pub(?:\([^)]*\))?\s+)?(?:unsafe\s+)?impl(?:\s*<[^>]*>)?\s+\w"
    r"|"
    r"^\s*(?:pub(?:\([^)]*\))?\s+)?(?:struct|enum|trait|union)\s+\w"
    r"|"
    r"^\s*macro_rules!\s+\w"
)

# Matches SQL DDL statements that open a new object definition.
# Intentionally conservative: only CREATE/ALTER/DROP so routine DML queries
# (INSERT, UPDATE, DELETE, SELECT) do not create excessive split points.
_SQL_DECL_RE = re.compile(
    r"(?i)^\s*(?:CREATE|ALTER|DROP)\s+(?:OR\s+REPLACE\s+)?"
    r"(?:TABLE|VIEW|INDEX|UNIQUE\s+INDEX|PROCEDURE|FUNCTION|TRIGGER|"
    r"DATABASE|SCHEMA|SEQUENCE|TYPE|ROLE|USER)\b"
)

# Matches assembly language entry points: named labels at column 0, ELF/NASM
# section directives, and MASM-style PROC/ENDP markers.  The IGNORECASE flag
# covers assembler mnemonics and directives that may be upper or lower case.
_ASM_DECL_RE = re.compile(
    r"^[\w.@?$]+\s*:"  # label definition — no leading whitespace (column-0)
    r"|"
    r"^\s*section\s+\."  # ELF/NASM section directive
    r"|"
    r"^\s*\w+\s+(?:proc|endp)\b",  # MASM proc/endp
    re.IGNORECASE,
)

# Registry mapping file extension to the compiled declaration regex for chunking.
# Extensions not listed here fall back to the single-chunk behaviour.
_CHUNKERS: dict[str, re.Pattern] = {
    # C#
    ".cs": _CS_DECL_RE,
    # PHP
    ".php": _PHP_DECL_RE,
    # C / C++
    ".c": _C_DECL_RE,
    ".cpp": _C_DECL_RE,
    ".h": _C_DECL_RE,
    ".hpp": _C_DECL_RE,
    ".cc": _C_DECL_RE,
    ".cxx": _C_DECL_RE,
    ".hh": _C_DECL_RE,
    ".hxx": _C_DECL_RE,
    # Python
    ".py": _PY_DECL_RE,
    # JavaScript
    ".js": _JS_DECL_RE,
    ".mjs": _JS_DECL_RE,
    ".cjs": _JS_DECL_RE,
    # TypeScript
    ".ts": _TS_DECL_RE,
    ".tsx": _TS_DECL_RE,
    # Java
    ".java": _JAVA_DECL_RE,
    # Go
    ".go": _GO_DECL_RE,
    # Ruby
    ".rb": _RUBY_DECL_RE,
    # Rust
    ".rs": _RUST_DECL_RE,
    # SQL
    ".sql": _SQL_DECL_RE,
    # Assembly
    ".asm": _ASM_DECL_RE,
    ".s": _ASM_DECL_RE,
    ".S": _ASM_DECL_RE,
}

# Ordered tuple of all extensions that codeindex can index.  Used as the
# default for index_all() and the server --ext argument so users get broad
# language coverage out of the box.
_ALL_EXTENSIONS: tuple[str, ...] = tuple(_CHUNKERS.keys())

_EMBEDDING_MODEL = "BAAI/bge-base-en-v1.5"


def _file_hash(path: Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()


def _chunk(content: str, rel_path: str, decl_re: re.Pattern | None = None) -> list[dict]:
    lines = content.splitlines()

    if decl_re is None:
        return [{"content": content, "start": 0, "end": len(lines) - 1, "path": rel_path}]

    split_points = [
        i for i, ln in enumerate(lines)
        if decl_re.match(ln) and not ln.strip().startswith("//")
    ]

    if not split_points:
        return [{"content": content, "start": 0, "end": len(lines) - 1, "path": rel_path}]

    # Include everything before the first declaration as a preamble chunk
    boundaries = ([0] if split_points[0] > 0 else []) + split_points + [len(lines)]
    chunks = []
    for i in range(len(boundaries) - 1):
        start, end = boundaries[i], boundaries[i + 1] - 1
        text = "\n".join(lines[start : end + 1]).strip()
        if text:
            chunks.append({"content": text, "start": start, "end": end, "path": rel_path})
    return chunks


class Indexer:
    def __init__(self, root: Path, store_path: Path):
        self._root = root.resolve()
        store_path.mkdir(parents=True, exist_ok=True)

        # Persist root so codeindex-query can recover it without --root.
        (store_path / "meta.json").write_text(json.dumps({"root": str(self._root)}))

        self._client = chromadb.PersistentClient(path=str(store_path / "db"))
        self._collection = self._client.get_or_create_collection(
            name="code",
            embedding_function=SentenceTransformerEmbeddingFunction(model_name=_EMBEDDING_MODEL),
        )

        self._hash_file = store_path / "hashes.json"
        self._hashes: dict[str, str] = (
            json.loads(self._hash_file.read_text()) if self._hash_file.exists() else {}
        )

    def _save_hashes(self):
        self._hash_file.write_text(json.dumps(self._hashes))

    def _delete_by_path(self, rel: str):
        results = self._collection.get(where={"path": rel})
        if results["ids"]:
            self._collection.delete(ids=results["ids"])

    def index_file(self, path: Path) -> bool:
        """Index or re-index a single file. Returns True if work was done."""
        try:
            rel = str(path.relative_to(self._root))
        except ValueError:
            return False

        h = _file_hash(path)
        if self._hashes.get(rel) == h:
            return False

        self._delete_by_path(rel)

        content = path.read_text(encoding="utf-8", errors="replace")
        decl_re = _CHUNKERS.get(path.suffix.lower())
        chunks = _chunk(content, rel, decl_re)

        self._collection.upsert(
            ids=[f"{rel}:{c['start']}" for c in chunks],
            documents=[c["content"] for c in chunks],
            metadatas=[{"path": rel, "start": c["start"], "end": c["end"]} for c in chunks],
        )

        self._hashes[rel] = h
        self._save_hashes()
        return True

    def delete_file(self, path: Path):
        try:
            rel = str(path.relative_to(self._root))
        except ValueError:
            return
        self._delete_by_path(rel)
        self._hashes.pop(rel, None)
        self._save_hashes()

    def index_all(self, extensions: tuple[str, ...] = _ALL_EXTENSIONS) -> int:
        count = 0
        for ext in extensions:
            for f in self._root.rglob(f"*{ext}"):
                if self.index_file(f):
                    count += 1
        return count

    def search(self, query: str, n: int = 5) -> list[dict]:
        total = self._collection.count()
        if total == 0:
            return []
        results = self._collection.query(
            query_texts=[query],
            n_results=min(n, total),
        )
        out = []
        for i, doc in enumerate(results["documents"][0]):
            meta = results["metadatas"][0][i]
            dist = results["distances"][0][i]
            out.append({
                "path": meta["path"],
                "start_line": meta["start"] + 1,
                "end_line": meta["end"] + 1,
                "content": doc,
                "score": round(max(0.0, min(1.0, 1.0 - dist)), 3),
            })
        return out

    def status(self) -> dict:
        return {
            "root": str(self._root),
            "indexed_files": len(self._hashes),
            "indexed_chunks": self._collection.count(),
        }
