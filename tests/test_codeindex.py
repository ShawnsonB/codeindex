"""
Smoke test for codeindex indexer.

Tests:
  1. PHP chunker — checks split points, excluded closures, and enum/trait/interface detection
  2. C# indexer — indexes tests/fixtures/csharp (5 synthetic .cs files) and runs a semantic search
  3. PHP indexer — indexes tests/fixtures/php and runs a semantic search
  4. C/C++ chunker — checks split points, excluded lambdas, struct/enum/union/operator detection
  5. C/C++ indexer — indexes tests/fixtures/c (6 files: 3 .h + 3 .cpp), semantic search
"""

import json
import sys
import tempfile
from pathlib import Path

# File lives at codeindex/tests/test_codeindex.py; src/ is at parent.parent/src
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from codeindex.indexer import (  # noqa: E402
    _CHROMADB_VERSION,
    _check_store_compat,
    _chunk,
    _PHP_DECL_RE, _CS_DECL_RE, _C_DECL_RE,
    _PY_DECL_RE, _JS_DECL_RE, _TS_DECL_RE,
    _JAVA_DECL_RE, _GO_DECL_RE, _RUBY_DECL_RE,
    _RUST_DECL_RE, _SQL_DECL_RE, _ASM_DECL_RE,
    Indexer,
)

TESTS_DIR   = Path(__file__).parent
FIXTURES    = TESTS_DIR / "fixtures"
CSHARP_ROOT = FIXTURES / "csharp"
PHP_ROOT    = FIXTURES / "php"
C_ROOT      = FIXTURES / "c"

PYTHON_ROOT     = FIXTURES / "python"
JAVA_ROOT       = FIXTURES / "java"
GO_ROOT         = FIXTURES / "go"
RUST_ROOT       = FIXTURES / "rust"
JS_ROOT         = FIXTURES / "javascript"
TS_ROOT         = FIXTURES / "typescript"
RUBY_ROOT       = FIXTURES / "ruby"
SQL_ROOT        = FIXTURES / "sql"
ASM_ROOT        = FIXTURES / "assembly"

PASS = "\033[32mPASS\033[0m"
FAIL = "\033[31mFAIL\033[0m"


def check(label: str, condition: bool, detail: str = ""):
    status = PASS if condition else FAIL
    print(f"  [{status}] {label}" + (f": {detail}" if detail else ""))
    return condition


# ---------------------------------------------------------------------------
# 1. PHP chunker unit tests
# ---------------------------------------------------------------------------
print("\n=== PHP chunker unit tests ===")

PHP_SAMPLE = """\
<?php
namespace App;

use App\\Model\\User;

class Foo
{
    private string $x;

    public function __construct(string $x)
    {
        $this->x = $x;
    }

    public static function create(string $x): self
    {
        return new self($x);
    }

    private function helper(): void
    {
        // anonymous closure — must NOT be a chunk boundary
        $fn = function () { return 42; };
        // arrow function — must NOT be a chunk boundary
        $double = fn($n) => $n * 2;
    }
}

interface Countable
{
    public function count(): int;
}

trait Loggable
{
    public function log(string $msg): void {}
}

abstract class Base
{
    abstract protected function run(): void;
}

final class Concrete extends Base
{
    protected function run(): void {}
}
"""

php_chunks = _chunk(PHP_SAMPLE, "Foo.php", _PHP_DECL_RE)
chunk_texts = [c["content"] for c in php_chunks]
chunk_starts = [c["start"] for c in php_chunks]

# Should have split on: class Foo, __construct, create, helper,
#                       interface Countable, count, trait Loggable, log,
#                       abstract class Base, run (abstract), final class Concrete, run (concrete)
# The preamble (<?php ... use line) should be chunk 0.

ok = True
ok &= check("more than 5 chunks produced", len(php_chunks) > 5, f"got {len(php_chunks)}")

# Preamble chunk contains the namespace/use lines
preamble = chunk_texts[0]
ok &= check("preamble contains namespace", "namespace" in preamble)

# class Foo should appear as a split point
ok &= check("class Foo is a split point", any("class Foo" in t for t in chunk_texts))

# anonymous closure body should be inside helper(), not its own chunk
closure_chunk = next((t for t in chunk_texts if "$fn = function" in t), None)
ok &= check("anonymous closure is NOT its own chunk", closure_chunk is not None and "helper" in closure_chunk or
            all("$fn = function" not in t or "private function helper" in t for t in chunk_texts),
            "closure should stay in helper() chunk")

# interface, trait, abstract class, final class should each be split points
ok &= check("interface is a split point", any("interface Countable" in t for t in chunk_texts))
ok &= check("trait is a split point", any("trait Loggable" in t for t in chunk_texts))
ok &= check("abstract class is a split point", any("abstract class Base" in t for t in chunk_texts))
ok &= check("final class is a split point", any("final class Concrete" in t for t in chunk_texts))

print(f"\n  PHP chunker: {'all good' if ok else 'FAILURES ABOVE'}")


# ---------------------------------------------------------------------------
# 2. C# indexer + search
# ---------------------------------------------------------------------------
print("\n=== C# indexer (synthetic fixtures) ===")

with tempfile.TemporaryDirectory() as tmpdir:
    store = Path(tmpdir) / "cs_store"
    indexer = Indexer(CSHARP_ROOT, store)
    count = indexer.index_all((".cs",))
    status = indexer.status()

    check("all 5 C# files indexed", count == 5, f"indexed {count} file(s)")
    check("chunk count > file count", status["indexed_chunks"] > status["indexed_files"],
          f"{status['indexed_chunks']} chunks / {status['indexed_files']} files")

    results = indexer.search("how is damage applied to the player", n=3)
    check("damage search returns results", len(results) > 0, f"got {len(results)} result(s)")
    if results:
        top = results[0]
        check("top result is a .cs file", top["path"].endswith(".cs"), top["path"])
        check("top result has a positive score", top["score"] > 0, f"score={top['score']}")
        print(f"\n  Top C# hit: {top['path']} lines {top['start_line']}–{top['end_line']} (score {top['score']})")
        print(f"  Snippet: {top['content'][:120].strip()!r}…")

    results2 = indexer.search("IDamageable implementation", n=3)
    check("IDamageable search returns results", len(results2) > 0, f"got {len(results2)} result(s)")


# ---------------------------------------------------------------------------
# 3. PHP indexer + search
# ---------------------------------------------------------------------------
print("\n=== PHP indexer (TestPHP) ===")

with tempfile.TemporaryDirectory() as tmpdir:
    store = Path(tmpdir) / "php_store"
    indexer = Indexer(PHP_ROOT, store)
    count = indexer.index_all((".php",))
    status = indexer.status()

    check("all 3 PHP files indexed", count == 3, f"indexed {count} file(s)")
    check("chunk count > file count (chunking worked)", status["indexed_chunks"] > status["indexed_files"],
          f"{status['indexed_chunks']} chunks / {status['indexed_files']} files")

    results = indexer.search("authenticate a user with a JWT token", n=3)
    check("JWT auth search returns results", len(results) > 0, f"got {len(results)} result(s)")
    if results:
        top = results[0]
        check("top result is a .php file", top["path"].endswith(".php"), top["path"])
        check("top result has a positive score", top["score"] > 0, f"score={top['score']}")
        print(f"\n  Top PHP hit: {top['path']} lines {top['start_line']}–{top['end_line']} (score {top['score']})")
        print(f"  Snippet: {top['content'][:120].strip()!r}…")

    results2 = indexer.search("user account status enum active banned", n=3)
    check("status enum search returns results", len(results2) > 0, f"got {len(results2)} result(s)")
    if results2:
        top2 = results2[0]
        print(f"\n  Top enum hit: {top2['path']} lines {top2['start_line']}–{top2['end_line']} (score {top2['score']})")

    results3 = indexer.search("save or insert a user record to the database", n=3)
    check("DB save search returns results", len(results3) > 0, f"got {len(results3)} result(s)")

# ---------------------------------------------------------------------------
# 4. C/C++ chunker unit tests
# ---------------------------------------------------------------------------
print("\n=== C/C++ chunker unit tests ===")

# Sample exercises: struct, enum class, union, free functions (with qualifiers),
# class with in-body decls, out-of-line ctor/dtor/operator=, and a lambda that
# must NOT become its own chunk boundary.
CPP_SAMPLE = """\
#include <cmath>
#include <functional>
#define PI 3.14159f

struct Vec3 {
    float x, y, z;
};

enum class Axis { X, Y, Z };

union FloatBits {
    float f;
    unsigned int bits;
};

float dot(Vec3 a, Vec3 b) {
    return a.x * b.x + a.y * b.y + a.z * b.z;
}

static float magnitude(Vec3 v) {
    auto sq = [](float n) { return n * n; };
    return std::sqrt(sq(v.x) + sq(v.y) + sq(v.z));
}

class Camera {
public:
    Camera(float fov, float aspect);
    ~Camera();
    void lookAt(Vec3 target);
    Camera& operator=(const Camera& rhs);
private:
    float m_fov;
    float m_aspect;
};

Camera::Camera(float fov, float aspect) : m_fov(fov), m_aspect(aspect) {}

Camera::~Camera() {}

void Camera::lookAt(Vec3 target) {}

Camera& Camera::operator=(const Camera& rhs) {
    m_fov    = rhs.m_fov;
    m_aspect = rhs.m_aspect;
    return *this;
}
"""

cpp_chunks = _chunk(CPP_SAMPLE, "geometry.cpp", _C_DECL_RE)
cpp_texts = [c["content"] for c in cpp_chunks]

ok2 = True
ok2 &= check("more than 5 chunks produced", len(cpp_chunks) > 5, f"got {len(cpp_chunks)}")

preamble_cpp = cpp_texts[0]
ok2 &= check("preamble contains #include", "#include" in preamble_cpp)
ok2 &= check("#include does not start a new chunk", not any(t.lstrip().startswith("#include") for t in cpp_texts[1:]))
ok2 &= check("#define does not start a new chunk", not any(t.lstrip().startswith("#define") for t in cpp_texts[1:]))

ok2 &= check("struct Vec3 is a split point",   any("struct Vec3"    in t for t in cpp_texts))
ok2 &= check("enum class Axis is a split point", any("enum class Axis" in t for t in cpp_texts))
ok2 &= check("union FloatBits is a split point", any("union FloatBits" in t for t in cpp_texts))
ok2 &= check("free function dot() is a split point", any("float dot("      in t for t in cpp_texts))
ok2 &= check("static function is a split point",     any("static float magnitude" in t for t in cpp_texts))
ok2 &= check("class Camera is a split point",        any("class Camera"    in t for t in cpp_texts))
ok2 &= check("out-of-line ctor Camera::Camera is a split point",
             any("Camera::Camera" in t for t in cpp_texts))
ok2 &= check("out-of-line dtor Camera::~Camera is a split point",
             any("Camera::~Camera" in t for t in cpp_texts))
ok2 &= check("operator= is a split point", any("operator=" in t for t in cpp_texts))

# Lambda auto sq = [...] must stay inside magnitude(), not become its own chunk
lambda_chunk = next((t for t in cpp_texts if "auto sq =" in t), None)
ok2 &= check("lambda is NOT its own chunk",
             lambda_chunk is not None and "magnitude" in lambda_chunk,
             "lambda should stay inside magnitude() chunk")

print(f"\n  C/C++ chunker: {'all good' if ok2 else 'FAILURES ABOVE'}")
print(f"  (note: if/for/while statements inside bodies are known false-positive split points)")


# ---------------------------------------------------------------------------
# 5. C/C++ indexer + search
# ---------------------------------------------------------------------------
print("\n=== C/C++ indexer (TestC) ===")

with tempfile.TemporaryDirectory() as tmpdir:
    store = Path(tmpdir) / "c_store"
    indexer = Indexer(C_ROOT, store)
    count = indexer.index_all((".c", ".cpp", ".h", ".hpp"))
    status = indexer.status()

    check("all 6 C/C++ files indexed", count == 6, f"indexed {count} file(s)")
    check("chunk count > file count (chunking worked)", status["indexed_chunks"] > status["indexed_files"],
          f"{status['indexed_chunks']} chunks / {status['indexed_files']} files")

    results = indexer.search("how is damage applied to the player", n=3)
    check("damage search returns results", len(results) > 0, f"got {len(results)} result(s)")
    if results:
        top = results[0]
        check("top result is a C/C++ file", top["path"].endswith((".h", ".cpp")), top["path"])
        check("top result has a positive score", top["score"] > 0, f"score={top['score']}")
        print(f"\n  Top damage hit: {top['path']} lines {top['start_line']}–{top['end_line']} (score {top['score']})")
        print(f"  Snippet: {top['content'][:120].strip()!r}…")

    results2 = indexer.search("allocate and free memory blocks from a pool", n=3)
    check("allocator search returns results", len(results2) > 0, f"got {len(results2)} result(s)")
    if results2:
        top2 = results2[0]
        print(f"\n  Top allocator hit: {top2['path']} lines {top2['start_line']}–{top2['end_line']} (score {top2['score']})")

    results3 = indexer.search("collision detection between bounding boxes", n=3)
    check("collision search returns results", len(results3) > 0, f"got {len(results3)} result(s)")
    if results3:
        top3 = results3[0]
        print(f"\n  Top physics hit: {top3['path']} lines {top3['start_line']}–{top3['end_line']} (score {top3['score']})")

# ---------------------------------------------------------------------------
# 6. Version mismatch: stale store is wiped before opening
# ---------------------------------------------------------------------------
print("\n=== Version mismatch wipes stale store ===")

with tempfile.TemporaryDirectory() as _tmp:
    _store = Path(_tmp) / ".codeindex"
    _store.mkdir()

    # Simulate a store created by a different chromadb version
    (_store / "meta.json").write_text(json.dumps({"root": _tmp, "chromadb_version": "0.0.0-old"}))
    _db = _store / "db"
    _db.mkdir()
    (_db / "chroma.sqlite3").write_text("fake")
    (_store / "hashes.json").write_text("{}")

    _check_store_compat(_store)

    ok3 = True
    ok3 &= check("db/ wiped on version mismatch", not _db.exists())
    ok3 &= check("hashes.json wiped on version mismatch", not (_store / "hashes.json").exists())
    ok3 &= check("meta.json left intact by the check itself", (_store / "meta.json").exists())

    # Confirm Indexer stamps the current version into meta.json on creation
    _idx = Indexer(Path(_tmp), _store)
    _meta = json.loads((_store / "meta.json").read_text())
    ok3 &= check(
        "Indexer stamps current chromadb_version in meta.json",
        _meta.get("chromadb_version") == _CHROMADB_VERSION,
        f"got {_meta.get('chromadb_version')!r}, expected {_CHROMADB_VERSION!r}",
    )

    print(f"\n  Version mismatch: {'all good' if ok3 else 'FAILURES ABOVE'}")

print("\n=== Done ===\n")


# ---------------------------------------------------------------------------
# 6. Python chunker unit tests
# ---------------------------------------------------------------------------
print("\n=== Python chunker unit tests ===")

PY_SAMPLE = """\
\"\"\"Combat module.\"\"\"
from __future__ import annotations
from enum import Enum, auto

class DamageType(Enum):
    PHYSICAL = auto()
    FIRE = auto()

class CombatEntity:
    def __init__(self, name: str, health: float) -> None:
        self._name = name
        self._health = health

    def is_alive(self) -> bool:
        return self._health > 0.0

    def apply_damage(self, amount: float) -> None:
        self._health = max(0.0, self._health - amount)

class Player(CombatEntity):
    def __init__(self, name: str, health: float, level: int = 1) -> None:
        super().__init__(name, health)
        self.level = level

    def gain_experience(self, xp: int) -> None:
        pass

async def resolve_round(attacker: CombatEntity, defender: CombatEntity) -> dict:
    return {}

def calculate_multiplier(base: float) -> float:
    inner = lambda x: x * 2   # lambda must NOT be its own chunk
    return inner(base)
"""

py_chunks = _chunk(PY_SAMPLE, "combat.py", _PY_DECL_RE)
py_texts  = [c["content"] for c in py_chunks]

ok3 = True
ok3 &= check("Python: more than 5 chunks", len(py_chunks) > 5, f"got {len(py_chunks)}")
ok3 &= check("Python: preamble contains imports", any("from __future__" in t for t in py_texts))
ok3 &= check("Python: class DamageType is a split point",  any("class DamageType"  in t for t in py_texts))
ok3 &= check("Python: class CombatEntity is a split point", any("class CombatEntity" in t for t in py_texts))
ok3 &= check("Python: def __init__ is a split point",      any("def __init__"      in t for t in py_texts))
ok3 &= check("Python: def is_alive is a split point",      any("def is_alive"      in t for t in py_texts))
ok3 &= check("Python: class Player is a split point",      any("class Player"      in t for t in py_texts))
ok3 &= check("Python: async def resolve_round is a split point", any("async def resolve_round" in t for t in py_texts))

lambda_chunk = next((t for t in py_texts if "lambda" in t), None)
ok3 &= check("Python: lambda is NOT its own chunk",
             lambda_chunk is not None and "calculate_multiplier" in lambda_chunk,
             "lambda should stay inside calculate_multiplier()")

print(f"\n  Python chunker: {'all good' if ok3 else 'FAILURES ABOVE'}")


# ---------------------------------------------------------------------------
# 7. Python indexer + search
# ---------------------------------------------------------------------------
print("\n=== Python indexer (TestPython) ===")

with tempfile.TemporaryDirectory() as tmpdir:
    store = Path(tmpdir) / "py_store"
    indexer = Indexer(PYTHON_ROOT, store)
    count = indexer.index_all((".py",))
    status = indexer.status()

    check("Python: 1 file indexed", count == 1, f"indexed {count} file(s)")
    check("Python: chunk count > file count", status["indexed_chunks"] > status["indexed_files"],
          f"{status['indexed_chunks']} chunks / {status['indexed_files']} files")

    results = indexer.search("how is damage applied to a combat entity", n=3)
    check("Python: damage search returns results", len(results) > 0, f"got {len(results)} result(s)")
    if results:
        top = results[0]
        check("Python: top result is a .py file", top["path"].endswith(".py"), top["path"])
        check("Python: top result has positive score", top["score"] > 0, f"score={top['score']}")
        print(f"\n  Top Python hit: {top['path']} lines {top['start_line']}–{top['end_line']} (score {top['score']})")

    results2 = indexer.search("player experience and level up", n=3)
    check("Python: level-up search returns results", len(results2) > 0, f"got {len(results2)} result(s)")


# ---------------------------------------------------------------------------
# 8. Java chunker unit tests
# ---------------------------------------------------------------------------
print("\n=== Java chunker unit tests ===")

JAVA_SAMPLE = """\
package com.game;

import java.util.List;

public enum DamageType { PHYSICAL, MAGIC, FIRE }

interface Damageable {
    void applyDamage(int amount, DamageType type);
    boolean isAlive();
}

@FunctionalInterface
interface DamageCalculator {
    int calculate(int base, DamageType type);
}

public abstract class BaseEnemy implements Damageable {
    protected int health;

    public BaseEnemy(int health) {
        this.health = health;
    }

    public abstract void attack(Damageable target);

    @Override
    public boolean isAlive() {
        return health > 0;
    }

    private static int applyResistance(int amount, float r) {
        return (int)(amount * (1.0f - r));
    }
}

final class Goblin extends BaseEnemy {
    public Goblin() { super(30); }

    @Override
    public void attack(Damageable t) {
        t.applyDamage(5, DamageType.PHYSICAL);
    }

    @Override
    public void applyDamage(int amount, DamageType type) {
        this.health = Math.max(0, this.health - amount);
    }
}
"""

java_chunks = _chunk(JAVA_SAMPLE, "Combat.java", _JAVA_DECL_RE)
java_texts  = [c["content"] for c in java_chunks]

ok4 = True
ok4 &= check("Java: more than 4 chunks", len(java_chunks) > 4, f"got {len(java_chunks)}")
ok4 &= check("Java: enum DamageType is a split point",     any("enum DamageType"  in t for t in java_texts))
ok4 &= check("Java: interface Damageable is a split point", any("interface Damageable" in t for t in java_texts))
ok4 &= check("Java: abstract class BaseEnemy is a split point", any("abstract class BaseEnemy" in t for t in java_texts))
ok4 &= check("Java: public BaseEnemy constructor is a split point", any("public BaseEnemy(" in t for t in java_texts))
ok4 &= check("Java: abstract void attack is a split point", any("abstract void attack" in t for t in java_texts))
ok4 &= check("Java: final class Goblin is a split point",  any("final class Goblin"   in t for t in java_texts))
ok4 &= check("Java: @FunctionalInterface does NOT start its own chunk",
             not any(t.strip().startswith("@FunctionalInterface") for t in java_texts[1:]))

print(f"\n  Java chunker: {'all good' if ok4 else 'FAILURES ABOVE'}")


# ---------------------------------------------------------------------------
# 9. Java indexer + search
# ---------------------------------------------------------------------------
print("\n=== Java indexer (TestJava) ===")

with tempfile.TemporaryDirectory() as tmpdir:
    store = Path(tmpdir) / "java_store"
    indexer = Indexer(JAVA_ROOT, store)
    count = indexer.index_all((".java",))
    status = indexer.status()

    check("Java: 2 files indexed", count == 2, f"indexed {count} file(s)")
    check("Java: chunk count > file count", status["indexed_chunks"] > status["indexed_files"],
          f"{status['indexed_chunks']} chunks / {status['indexed_files']} files")

    results = indexer.search("apply damage to player with armor mitigation", n=3)
    check("Java: damage search returns results", len(results) > 0, f"got {len(results)} result(s)")
    if results:
        top = results[0]
        check("Java: top result is a .java file", top["path"].endswith(".java"), top["path"])
        check("Java: positive score", top["score"] > 0, f"score={top['score']}")
        print(f"\n  Top Java hit: {top['path']} lines {top['start_line']}–{top['end_line']} (score {top['score']})")


# ---------------------------------------------------------------------------
# 10. Go chunker unit tests
# ---------------------------------------------------------------------------
print("\n=== Go chunker unit tests ===")

GO_SAMPLE = """\
package server

import (
    "context"
    "net/http"
)

type Config struct {
    Host string
    Port int
}

type Handler interface {
    ServeHTTP(http.ResponseWriter, *http.Request)
}

func New(cfg Config) *Server {
    return &Server{config: cfg, mux: http.NewServeMux()}
}

func (s *Server) RegisterRoute(pattern string, h http.HandlerFunc) {
    s.mux.HandleFunc(pattern, h)
}

func (s *Server) Start(ctx context.Context) error {
    shutdown := make(chan struct{})
    go func() {
        <-ctx.Done()
        close(shutdown)
    }()
    return nil
}

func healthHandler(w http.ResponseWriter, r *http.Request) {
    w.WriteHeader(http.StatusOK)
}
"""

go_chunks = _chunk(GO_SAMPLE, "server.go", _GO_DECL_RE)
go_texts  = [c["content"] for c in go_chunks]

ok5 = True
ok5 &= check("Go: more than 4 chunks", len(go_chunks) > 4, f"got {len(go_chunks)}")
ok5 &= check("Go: preamble contains import", any("import" in t for t in go_texts))
ok5 &= check("Go: type Config struct is a split point",   any("type Config struct"   in t for t in go_texts))
ok5 &= check("Go: type Handler interface is a split point", any("type Handler interface" in t for t in go_texts))
ok5 &= check("Go: func New is a split point",             any("func New("            in t for t in go_texts))
ok5 &= check("Go: method RegisterRoute is a split point", any("RegisterRoute"        in t for t in go_texts))
ok5 &= check("Go: method Start is a split point",         any("func (s *Server) Start" in t for t in go_texts))
ok5 &= check("Go: func healthHandler is a split point",   any("func healthHandler"   in t for t in go_texts))

goroutine_chunk = next((t for t in go_texts if "go func()" in t), None)
ok5 &= check("Go: goroutine literal is NOT its own chunk",
             goroutine_chunk is not None and "Start" in goroutine_chunk,
             "goroutine should stay inside Start()")

print(f"\n  Go chunker: {'all good' if ok5 else 'FAILURES ABOVE'}")


# ---------------------------------------------------------------------------
# 11. Go indexer + search
# ---------------------------------------------------------------------------
print("\n=== Go indexer (TestGo) ===")

with tempfile.TemporaryDirectory() as tmpdir:
    store = Path(tmpdir) / "go_store"
    indexer = Indexer(GO_ROOT, store)
    count = indexer.index_all((".go",))
    status = indexer.status()

    check("Go: 2 files indexed", count == 2, f"indexed {count} file(s)")
    check("Go: chunk count > file count", status["indexed_chunks"] > status["indexed_files"],
          f"{status['indexed_chunks']} chunks / {status['indexed_files']} files")

    results = indexer.search("find user by ID from the database", n=3)
    check("Go: DB lookup search returns results", len(results) > 0, f"got {len(results)} result(s)")
    if results:
        top = results[0]
        check("Go: top result is a .go file", top["path"].endswith(".go"), top["path"])
        check("Go: positive score", top["score"] > 0, f"score={top['score']}")
        print(f"\n  Top Go hit: {top['path']} lines {top['start_line']}–{top['end_line']} (score {top['score']})")


# ---------------------------------------------------------------------------
# 12. Rust chunker unit tests
# ---------------------------------------------------------------------------
print("\n=== Rust chunker unit tests ===")

RUST_SAMPLE = """\
//! Game engine core.

pub trait Component: Send + Sync {
    fn update(&mut self, dt: f32);
    fn name(&self) -> &'static str;
}

pub struct Health {
    pub current: f32,
    pub maximum: f32,
}

impl Health {
    pub fn new(maximum: f32) -> Self {
        Health { current: maximum, maximum }
    }

    pub fn apply_damage(&mut self, amount: f32) {
        self.current = (self.current - amount).max(0.0);
    }

    pub fn is_alive(&self) -> bool {
        self.current > 0.0
    }
}

impl Component for Health {
    fn update(&mut self, _dt: f32) {}

    fn name(&self) -> &'static str { "Health" }
}

pub(crate) enum GameState {
    Menu,
    Playing,
    Paused,
}

macro_rules! assert_alive {
    ($e:expr) => { assert!($e.is_alive()); };
}

pub unsafe fn raw_mem_copy(dst: *mut u8, src: *const u8, n: usize) {
    std::ptr::copy_nonoverlapping(src, dst, n);
}
"""

rust_chunks = _chunk(RUST_SAMPLE, "engine.rs", _RUST_DECL_RE)
rust_texts  = [c["content"] for c in rust_chunks]

ok6 = True
ok6 &= check("Rust: more than 4 chunks", len(rust_chunks) > 4, f"got {len(rust_chunks)}")
ok6 &= check("Rust: pub trait Component is a split point",  any("pub trait Component"  in t for t in rust_texts))
ok6 &= check("Rust: pub struct Health is a split point",    any("pub struct Health"    in t for t in rust_texts))
ok6 &= check("Rust: impl Health is a split point",          any("impl Health"          in t for t in rust_texts))
ok6 &= check("Rust: pub fn new is a split point",           any("pub fn new("          in t for t in rust_texts))
ok6 &= check("Rust: pub fn apply_damage is a split point",  any("pub fn apply_damage"  in t for t in rust_texts))
ok6 &= check("Rust: impl Component for Health is a split point", any("impl Component for Health" in t for t in rust_texts))
ok6 &= check("Rust: pub(crate) enum GameState is a split point", any("pub(crate) enum GameState" in t for t in rust_texts))
ok6 &= check("Rust: macro_rules! assert_alive is a split point", any("macro_rules! assert_alive" in t for t in rust_texts))
ok6 &= check("Rust: pub unsafe fn raw_mem_copy is a split point", any("pub unsafe fn raw_mem_copy" in t for t in rust_texts))

print(f"\n  Rust chunker: {'all good' if ok6 else 'FAILURES ABOVE'}")


# ---------------------------------------------------------------------------
# 13. Rust indexer + search
# ---------------------------------------------------------------------------
print("\n=== Rust indexer (TestRust) ===")

with tempfile.TemporaryDirectory() as tmpdir:
    store = Path(tmpdir) / "rust_store"
    indexer = Indexer(RUST_ROOT, store)
    count = indexer.index_all((".rs",))
    status = indexer.status()

    check("Rust: 1 file indexed", count == 1, f"indexed {count} file(s)")
    check("Rust: chunk count > file count", status["indexed_chunks"] > status["indexed_files"],
          f"{status['indexed_chunks']} chunks / {status['indexed_files']} files")

    results = indexer.search("apply damage to health component", n=3)
    check("Rust: damage search returns results", len(results) > 0, f"got {len(results)} result(s)")
    if results:
        top = results[0]
        check("Rust: top result is a .rs file", top["path"].endswith(".rs"), top["path"])
        check("Rust: positive score", top["score"] > 0, f"score={top['score']}")
        print(f"\n  Top Rust hit: {top['path']} lines {top['start_line']}–{top['end_line']} (score {top['score']})")


# ---------------------------------------------------------------------------
# 14. JavaScript chunker unit tests
# ---------------------------------------------------------------------------
print("\n=== JavaScript chunker unit tests ===")

JS_SAMPLE = """\
const BASE = 'https://api.example.com';

class ApiError extends Error {
    constructor(status, msg) {
        super(msg);
        this.status = status;
    }
}

class ApiClient {
    constructor(token) {
        this.token = token;
    }

    async get(path) {
        return fetch(BASE + path);
    }

    static create(token) {
        return new ApiClient(token);
    }
}

async function fetchProfile(client, id) {
    return client.get('/users/' + id);
}

export default async function bootstrap(token) {
    return ApiClient.create(token);
}

const formatScore = (score) => score.toLocaleString();

const parseData = function(raw) {
    return JSON.parse(raw);
};
"""

js_chunks = _chunk(JS_SAMPLE, "api.js", _JS_DECL_RE)
js_texts  = [c["content"] for c in js_chunks]

ok7 = True
ok7 &= check("JS: more than 4 chunks", len(js_chunks) > 4, f"got {len(js_chunks)}")
ok7 &= check("JS: class ApiError is a split point",           any("class ApiError"   in t for t in js_texts))
ok7 &= check("JS: class ApiClient is a split point",          any("class ApiClient"  in t for t in js_texts))
ok7 &= check("JS: async function fetchProfile is a split point", any("async function fetchProfile" in t for t in js_texts))
ok7 &= check("JS: export default async function is a split point", any("export default async function" in t for t in js_texts))
ok7 &= check("JS: const formatScore arrow fn is a split point", any("const formatScore" in t for t in js_texts))
ok7 &= check("JS: const parseData function expr is a split point", any("const parseData" in t for t in js_texts))

print(f"\n  JavaScript chunker: {'all good' if ok7 else 'FAILURES ABOVE'}")


# ---------------------------------------------------------------------------
# 15. JavaScript indexer + search
# ---------------------------------------------------------------------------
print("\n=== JavaScript indexer (TestJS) ===")

with tempfile.TemporaryDirectory() as tmpdir:
    store = Path(tmpdir) / "js_store"
    indexer = Indexer(JS_ROOT, store)
    count = indexer.index_all((".js",))
    status = indexer.status()

    check("JS: 1 file indexed", count == 1, f"indexed {count} file(s)")
    check("JS: chunk count > file count", status["indexed_chunks"] > status["indexed_files"],
          f"{status['indexed_chunks']} chunks / {status['indexed_files']} files")

    results = indexer.search("authenticate user and send API request", n=3)
    check("JS: auth search returns results", len(results) > 0, f"got {len(results)} result(s)")
    if results:
        top = results[0]
        check("JS: top result is a .js file", top["path"].endswith(".js"), top["path"])
        check("JS: positive score", top["score"] > 0, f"score={top['score']}")
        print(f"\n  Top JS hit: {top['path']} lines {top['start_line']}–{top['end_line']} (score {top['score']})")


# ---------------------------------------------------------------------------
# 16. TypeScript chunker unit tests
# ---------------------------------------------------------------------------
print("\n=== TypeScript chunker unit tests ===")

TS_SAMPLE = """\
export enum Rank { Bronze = 'bronze', Gold = 'gold', Platinum = 'platinum' }

export type PlayerId = string;

export interface PlayerProfile {
    id: PlayerId;
    name: string;
    score: number;
}

export type ScoreUpdate = Pick<PlayerProfile, 'id' | 'score'>;

export abstract class BaseRepo<T, ID> {
    protected readonly items = new Map<ID, T>();

    abstract findById(id: ID): T | undefined;
    abstract save(entity: T): void;

    findAll(): T[] {
        return Array.from(this.items.values());
    }
}

export class PlayerRepo extends BaseRepo<PlayerProfile, PlayerId> {
    findById(id: PlayerId): PlayerProfile | undefined {
        return this.items.get(id);
    }

    save(p: PlayerProfile): void {
        this.items.set(p.id, p);
    }

    static rankFromScore(score: number): Rank {
        return score >= 10000 ? Rank.Platinum : Rank.Gold;
    }
}

export function buildLeaderboard(players: PlayerProfile[]) {
    return players.sort((a, b) => b.score - a.score);
}

export const computeDelta = (prev: number, curr: number): number => curr - prev;
"""

ts_chunks = _chunk(TS_SAMPLE, "models.ts", _TS_DECL_RE)
ts_texts  = [c["content"] for c in ts_chunks]

ok8 = True
ok8 &= check("TS: more than 5 chunks", len(ts_chunks) > 5, f"got {len(ts_chunks)}")
ok8 &= check("TS: export enum Rank is a split point",              any("export enum Rank"          in t for t in ts_texts))
ok8 &= check("TS: export type PlayerId is a split point",          any("export type PlayerId"      in t for t in ts_texts))
ok8 &= check("TS: export interface PlayerProfile is a split point", any("export interface PlayerProfile" in t for t in ts_texts))
ok8 &= check("TS: export type ScoreUpdate is a split point",       any("export type ScoreUpdate"  in t for t in ts_texts))
ok8 &= check("TS: export abstract class BaseRepo is a split point", any("export abstract class BaseRepo" in t for t in ts_texts))
ok8 &= check("TS: export class PlayerRepo is a split point",       any("export class PlayerRepo"  in t for t in ts_texts))
ok8 &= check("TS: export function buildLeaderboard is a split point", any("export function buildLeaderboard" in t for t in ts_texts))
ok8 &= check("TS: export const computeDelta is a split point",     any("export const computeDelta" in t for t in ts_texts))

print(f"\n  TypeScript chunker: {'all good' if ok8 else 'FAILURES ABOVE'}")


# ---------------------------------------------------------------------------
# 17. TypeScript indexer + search
# ---------------------------------------------------------------------------
print("\n=== TypeScript indexer (TestTS) ===")

with tempfile.TemporaryDirectory() as tmpdir:
    store = Path(tmpdir) / "ts_store"
    indexer = Indexer(TS_ROOT, store)
    count = indexer.index_all((".ts",))
    status = indexer.status()

    check("TS: 1 file indexed", count == 1, f"indexed {count} file(s)")
    check("TS: chunk count > file count", status["indexed_chunks"] > status["indexed_files"],
          f"{status['indexed_chunks']} chunks / {status['indexed_files']} files")

    results = indexer.search("build and sort a leaderboard by player score", n=3)
    check("TS: leaderboard search returns results", len(results) > 0, f"got {len(results)} result(s)")
    if results:
        top = results[0]
        check("TS: top result is a .ts file", top["path"].endswith(".ts"), top["path"])
        check("TS: positive score", top["score"] > 0, f"score={top['score']}")
        print(f"\n  Top TS hit: {top['path']} lines {top['start_line']}–{top['end_line']} (score {top['score']})")


# ---------------------------------------------------------------------------
# 18. Ruby chunker unit tests
# ---------------------------------------------------------------------------
print("\n=== Ruby chunker unit tests ===")

RUBY_SAMPLE = """\
require 'securerandom'

module Auth
  class AuthError < StandardError; end

  module Tokenizable
    def generate_token
      SecureRandom.urlsafe_base64(32)
    end

    def token_expired?(issued_at, ttl = 3600)
      Time.now - issued_at > ttl
    end
  end

  class User
    include Tokenizable

    attr_reader :id, :email, :role

    def initialize(id:, email:, role: :user)
      @id    = id
      @email = email
      @role  = role
    end

    def admin?
      @role == :admin
    end

    def self.create(email:, role: :user)
      new(id: SecureRandom.uuid, email: email, role: role)
    end
  end
end
"""

ruby_chunks = _chunk(RUBY_SAMPLE, "user.rb", _RUBY_DECL_RE)
ruby_texts  = [c["content"] for c in ruby_chunks]

ok9 = True
ok9 &= check("Ruby: more than 4 chunks", len(ruby_chunks) > 4, f"got {len(ruby_chunks)}")
ok9 &= check("Ruby: module Auth is a split point",       any("module Auth"      in t for t in ruby_texts))
ok9 &= check("Ruby: module Tokenizable is a split point", any("module Tokenizable" in t for t in ruby_texts))
ok9 &= check("Ruby: class User is a split point",        any("class User"       in t for t in ruby_texts))
ok9 &= check("Ruby: def initialize is a split point",    any("def initialize"   in t for t in ruby_texts))
ok9 &= check("Ruby: def self.create is a split point",   any("def self.create"  in t for t in ruby_texts))
ok9 &= check("Ruby: attr_reader is a split point",       any("attr_reader"      in t for t in ruby_texts))

print(f"\n  Ruby chunker: {'all good' if ok9 else 'FAILURES ABOVE'}")


# ---------------------------------------------------------------------------
# 19. Ruby indexer + search
# ---------------------------------------------------------------------------
print("\n=== Ruby indexer (TestRuby) ===")

with tempfile.TemporaryDirectory() as tmpdir:
    store = Path(tmpdir) / "rb_store"
    indexer = Indexer(RUBY_ROOT, store)
    count = indexer.index_all((".rb",))
    status = indexer.status()

    check("Ruby: 1 file indexed", count == 1, f"indexed {count} file(s)")
    check("Ruby: chunk count > file count", status["indexed_chunks"] > status["indexed_files"],
          f"{status['indexed_chunks']} chunks / {status['indexed_files']} files")

    results = indexer.search("authenticate user with password", n=3)
    check("Ruby: auth search returns results", len(results) > 0, f"got {len(results)} result(s)")
    if results:
        top = results[0]
        check("Ruby: top result is a .rb file", top["path"].endswith(".rb"), top["path"])
        check("Ruby: positive score", top["score"] > 0, f"score={top['score']}")
        print(f"\n  Top Ruby hit: {top['path']} lines {top['start_line']}–{top['end_line']} (score {top['score']})")


# ---------------------------------------------------------------------------
# 20. SQL chunker unit tests
# ---------------------------------------------------------------------------
print("\n=== SQL chunker unit tests ===")

SQL_SAMPLE = """\
-- Schema for leaderboard service

CREATE TABLE users (
    id    BIGINT PRIMARY KEY,
    email VARCHAR(255) NOT NULL UNIQUE,
    name  VARCHAR(100) NOT NULL
);

CREATE TABLE players (
    id      BIGINT PRIMARY KEY,
    user_id BIGINT NOT NULL,
    score   INT    NOT NULL DEFAULT 0
);

CREATE INDEX idx_score ON players (score DESC);

CREATE VIEW leaderboard AS
    SELECT p.id, p.score, u.name
    FROM players p JOIN users u ON u.id = p.user_id
    ORDER BY p.score DESC;

ALTER TABLE players ADD COLUMN wins INT NOT NULL DEFAULT 0;

DROP TABLE IF EXISTS legacy_scores;

CREATE OR REPLACE VIEW player_stats AS
    SELECT id, score, wins FROM players;
"""

sql_chunks = _chunk(SQL_SAMPLE, "schema.sql", _SQL_DECL_RE)
sql_texts  = [c["content"] for c in sql_chunks]

ok10 = True
ok10 &= check("SQL: more than 4 chunks", len(sql_chunks) > 4, f"got {len(sql_chunks)}")
ok10 &= check("SQL: CREATE TABLE users is a split point",    any("CREATE TABLE users"    in t for t in sql_texts))
ok10 &= check("SQL: CREATE TABLE players is a split point",  any("CREATE TABLE players"  in t for t in sql_texts))
ok10 &= check("SQL: CREATE INDEX is a split point",          any("CREATE INDEX"          in t for t in sql_texts))
ok10 &= check("SQL: CREATE VIEW is a split point",           any("CREATE VIEW leaderboard" in t for t in sql_texts))
ok10 &= check("SQL: ALTER TABLE is a split point",           any("ALTER TABLE"           in t for t in sql_texts))
ok10 &= check("SQL: DROP TABLE is a split point",            any("DROP TABLE"            in t for t in sql_texts))
ok10 &= check("SQL: CREATE OR REPLACE VIEW is a split point", any("CREATE OR REPLACE VIEW" in t for t in sql_texts))

print(f"\n  SQL chunker: {'all good' if ok10 else 'FAILURES ABOVE'}")


# ---------------------------------------------------------------------------
# 21. SQL indexer + search
# ---------------------------------------------------------------------------
print("\n=== SQL indexer (TestSQL) ===")

with tempfile.TemporaryDirectory() as tmpdir:
    store = Path(tmpdir) / "sql_store"
    indexer = Indexer(SQL_ROOT, store)
    count = indexer.index_all((".sql",))
    status = indexer.status()

    check("SQL: 1 file indexed", count == 1, f"indexed {count} file(s)")
    check("SQL: chunk count > file count", status["indexed_chunks"] > status["indexed_files"],
          f"{status['indexed_chunks']} chunks / {status['indexed_files']} files")

    results = indexer.search("leaderboard ranking of players by score", n=3)
    check("SQL: leaderboard search returns results", len(results) > 0, f"got {len(results)} result(s)")
    if results:
        top = results[0]
        check("SQL: top result is a .sql file", top["path"].endswith(".sql"), top["path"])
        check("SQL: positive score", top["score"] > 0, f"score={top['score']}")
        print(f"\n  Top SQL hit: {top['path']} lines {top['start_line']}–{top['end_line']} (score {top['score']})")


# ---------------------------------------------------------------------------
# 22. Assembly chunker unit tests
# ---------------------------------------------------------------------------
print("\n=== Assembly chunker unit tests ===")

ASM_SAMPLE = """\
; x86-64 NASM — basic math routines

section .data
    zero dq 0.0

section .bss
    result resq 1

section .text
    global add_int64
    global clamp_int32

; Add rdi + rsi -> rax
add_int64:
    mov rax, rdi
    add rax, rsi
    ret

; Clamp edi to [esi, edx] -> eax
clamp_int32:
    mov eax, edi
    cmp eax, esi
    cmovl eax, esi
    cmp eax, edx
    cmovg eax, edx
    ret
"""

asm_chunks = _chunk(ASM_SAMPLE, "math.asm", _ASM_DECL_RE)
asm_texts  = [c["content"] for c in asm_chunks]

ok11 = True
ok11 &= check("ASM: more than 3 chunks", len(asm_chunks) > 3, f"got {len(asm_chunks)}")
ok11 &= check("ASM: section .data is a split point",   any("section .data"  in t for t in asm_texts))
ok11 &= check("ASM: section .text is a split point",   any("section .text"  in t for t in asm_texts))
ok11 &= check("ASM: add_int64 label is a split point",  any("add_int64:"     in t for t in asm_texts))
ok11 &= check("ASM: clamp_int32 label is a split point", any("clamp_int32:"  in t for t in asm_texts))

print(f"\n  Assembly chunker: {'all good' if ok11 else 'FAILURES ABOVE'}")


# ---------------------------------------------------------------------------
# 23. Assembly indexer + search
# ---------------------------------------------------------------------------
print("\n=== Assembly indexer (TestASM) ===")

with tempfile.TemporaryDirectory() as tmpdir:
    store = Path(tmpdir) / "asm_store"
    indexer = Indexer(ASM_ROOT, store)
    count = indexer.index_all((".asm",))
    status = indexer.status()

    check("ASM: 1 file indexed", count == 1, f"indexed {count} file(s)")
    check("ASM: chunk count > file count", status["indexed_chunks"] > status["indexed_files"],
          f"{status['indexed_chunks']} chunks / {status['indexed_files']} files")

    results = indexer.search("add two integers together in assembly", n=3)
    check("ASM: add search returns results", len(results) > 0, f"got {len(results)} result(s)")
    if results:
        top = results[0]
        check("ASM: top result is an .asm file", top["path"].endswith(".asm"), top["path"])
        check("ASM: positive score", top["score"] > 0, f"score={top['score']}")
        print(f"\n  Top ASM hit: {top['path']} lines {top['start_line']}–{top['end_line']} (score {top['score']})")


print("\n=== Done ===\n")
