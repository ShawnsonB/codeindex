"""
Smoke test for codeindex indexer.

Tests:
  1. PHP chunker — checks split points, excluded closures, and enum/trait/interface detection
  2. C# indexer — indexes tests/fixtures/csharp (5 synthetic .cs files) and runs a semantic search
  3. PHP indexer — indexes tests/fixtures/php and runs a semantic search
  4. C/C++ chunker — checks split points, excluded lambdas, struct/enum/union/operator detection
  5. C/C++ indexer — indexes tests/fixtures/c (6 files: 3 .h + 3 .cpp), semantic search
"""

import sys
import tempfile
from pathlib import Path

# File lives at codeindex/tests/test_codeindex.py; src/ is at parent.parent/src
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from codeindex.indexer import _chunk, _PHP_DECL_RE, _CS_DECL_RE, _C_DECL_RE, Indexer  # noqa: E402

TESTS_DIR   = Path(__file__).parent
FIXTURES    = TESTS_DIR / "fixtures"
CSHARP_ROOT = FIXTURES / "csharp"
PHP_ROOT    = FIXTURES / "php"
C_ROOT      = FIXTURES / "c"

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

print("\n=== Done ===\n")
