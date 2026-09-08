"""
Tests unitarios para el DFG Extractor de Graphito.

Cubre: declaraciones, asignaciones, structs, function calls, arrays,
templates C++, scopes, edge cases y fallback.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from models.graphcodebert.parser import DFGExtractor, DFGResult, DFGEdge


@pytest.fixture
def extractor():
    return DFGExtractor()


def _find_edge(edges: list[DFGEdge], relation: str, target_token: str,
               tokens: list[str]) -> DFGEdge | None:
    for e in edges:
        tgt = tokens[e.target_index].strip() if e.target_index < len(tokens) else ""
        if e.relation == relation and tgt == target_token:
            return e
    return None


def _edge_has_source(edge: DFGEdge, source_token: str, tokens: list[str]) -> bool:
    for si in edge.source_indices:
        if si < len(tokens) and tokens[si].strip() == source_token:
            return True
    return False


class TestBasicDeclarations:

    def test_simple_assignment(self, extractor):
        code = "int main() { int x = 5; return 0; }"
        r = extractor.parse_code(code, "c")
        assert r.success
        assert len(r.code_tokens) > 0

    def test_variable_computed_from(self, extractor):
        code = "int main() { int x = 5; int y = x + 2; return 0; }"
        r = extractor.parse_code(code, "c")
        edge = _find_edge(r.dfg_edges, "computedFrom", "y", r.code_tokens)
        assert edge is not None, f"Expected computedFrom->y, got {r.dfg_edges}"
        assert _edge_has_source(edge, "x", r.code_tokens)

    def test_compound_assignment(self, extractor):
        code = "int main() { int x = 10; x += 5; return 0; }"
        r = extractor.parse_code(code, "c")
        edge = _find_edge(r.dfg_edges, "computedFrom", "x", r.code_tokens)
        assert edge is not None, f"Expected self-loop edge for x+=, got {r.dfg_edges}"

    def test_plain_declaration_no_init(self, extractor):
        code = "int main() { int x; x = 10; return 0; }"
        r = extractor.parse_code(code, "c")
        # x = 10 has no variable RHS, so no computedFrom edge,
        # but x should be tracked in state
        assert r.success

    def test_return_comes_from(self, extractor):
        code = "int main() { int x = 5; return x; }"
        r = extractor.parse_code(code, "c")
        edge = _find_edge(r.dfg_edges, "comesFrom", "x", r.code_tokens)
        assert edge is not None, f"Expected comesFrom->x from return, got {r.dfg_edges}"


class TestControlFlow:

    def test_if_else_merge(self, extractor):
        code = """
        int main() {
            int a = 1; int b;
            if (a > 0) { b = a; } else { b = 0; }
            return b;
        }
        """
        r = extractor.parse_code(code, "c")
        assert r.success
        edge = _find_edge(r.dfg_edges, "computedFrom", "b", r.code_tokens)
        assert edge is not None

    def test_for_loop_self_edge(self, extractor):
        code = """
        int main() {
            int sum = 0;
            for (int i = 0; i < 10; i++) { sum = sum + i; }
            return sum;
        }
        """
        r = extractor.parse_code(code, "c")
        assert r.success
        self_edges = [e for e in r.dfg_edges
                      if e.relation == "computedFrom" and len(e.source_indices) == 1
                      and e.source_indices[0] == e.target_index]
        assert len(self_edges) >= 1, f"Expected self-loop, got {r.dfg_edges}"

    def test_while_loop(self, extractor):
        code = """
        int main() {
            int x = 10;
            while (x > 0) { x = x - 1; }
            return x;
        }
        """
        r = extractor.parse_code(code, "c")
        assert r.success
        assert len(r.dfg_edges) >= 2


class TestStructs:

    def test_struct_field_read(self, extractor):
        code = """
        typedef struct { int x; int y; } Point;
        int get_x(Point *p) { return p->x; }
        """
        r = extractor.parse_code(code, "c")
        assert r.success

    def test_struct_field_write(self, extractor):
        code = """
        typedef struct { int val; } Node;
        void update(Node *n) { n->val = n->val + 1; }
        """
        r = extractor.parse_code(code, "c")
        assert r.success
        assert len(r.dfg_edges) >= 1

    def test_nested_field_access(self, extractor):
        code = """
        typedef struct { int x; } Inner;
        typedef struct { Inner a; } Outer;
        void set_x(Outer *o, int v) { o->a.x = v; }
        """
        r = extractor.parse_code(code, "c")
        assert r.success

    def test_struct_dot_access(self, extractor):
        code = """
        typedef struct { int val; } Item;
        int main() { Item it; it.val = 42; return it.val; }
        """
        r = extractor.parse_code(code, "c")
        assert r.success
        assert len(r.dfg_edges) >= 1


class TestFunctionCalls:

    def test_call_args_flow(self, extractor):
        code = """
        int sumar(int a, int b) { return a + b; }
        int main() { int x = 5, y = 3; int z = sumar(x, y); return z; }
        """
        r = extractor.parse_code(code, "c")
        edge = _find_edge(r.dfg_edges, "computedFrom", "z", r.code_tokens)
        assert edge is not None, f"Expected x,y->z from call, got {r.dfg_edges}"
        assert _edge_has_source(edge, "x", r.code_tokens)
        assert _edge_has_source(edge, "y", r.code_tokens)

    def test_call_no_args(self, extractor):
        code = """
        int leer() { return 42; }
        int main() { int x = leer(); return x; }
        """
        r = extractor.parse_code(code, "c")
        assert r.success

    def test_recursive_call(self, extractor):
        code = """
        int fib(int n) {
            if (n <= 1) { return n; }
            return fib(n - 1) + fib(n - 2);
        }
        """
        r = extractor.parse_code(code, "c")
        assert r.success


class TestArrays:

    def test_array_subscript_read(self, extractor):
        code = """
        int main() {
            int arr[5] = {1, 2, 3, 4, 5};
            int x = arr[2];
            return x;
        }
        """
        r = extractor.parse_code(code, "c")
        assert r.success

    def test_array_subscript_write(self, extractor):
        code = """
        int main() {
            int arr[3];
            arr[0] = 10;
            arr[1] = arr[0] + 5;
            return arr[1];
        }
        """
        r = extractor.parse_code(code, "c")
        assert r.success
        assert len(r.dfg_edges) >= 1

    def test_2d_array(self, extractor):
        code = """
        int main() {
            int mat[3][3];
            mat[0][0] = 1;
            int x = mat[0][0];
            return x;
        }
        """
        r = extractor.parse_code(code, "c")
        assert r.success


class TestCppFeatures:

    def test_cpp_reference(self, extractor):
        code = """
        void increment(int &x) { x = x + 1; }
        int main() { int a = 5; increment(a); return a; }
        """
        r = extractor.parse_code(code, "cpp")
        assert r.success

    def test_cpp_range_for(self, extractor):
        code = """
        #include <vector>
        int sum(std::vector<int> &v) {
            int s = 0;
            for (int x : v) { s += x; }
            return s;
        }
        """
        r = extractor.parse_code(code, "cpp")
        assert r.success

    def test_cpp_template_function(self, extractor):
        code = """
        template<typename T>
        T max(T a, T b) { return a > b ? a : b; }
        int main() { int x = max(3, 5); return x; }
        """
        r = extractor.parse_code(code, "cpp")
        assert r.success

    def test_cpp_class_method(self, extractor):
        code = """
        class Counter {
            int val;
        public:
            Counter() : val(0) {}
            void inc() { val = val + 1; }
            int get() { return val; }
        };
        int main() { Counter c; c.inc(); return c.get(); }
        """
        r = extractor.parse_code(code, "cpp")
        assert r.success


class TestScopeIsolation:

    def test_same_var_different_funcs(self, extractor):
        code = """
        int func1() { int i = 0; i = i + 1; return i; }
        int func2() { int i = 10; i = i - 1; return i; }
        """
        r = extractor.parse_code(code, "c")
        edges_i = [e for e in r.dfg_edges
                    if r.code_tokens[e.target_index].strip() == "i"]
        assert len(edges_i) >= 4, f"Expected >=4 edges for i, got {len(edges_i)}"

    def test_global_variable(self, extractor):
        code = """
        int counter = 0;
        void inc() { counter = counter + 1; }
        int main() { inc(); return counter; }
        """
        r = extractor.parse_code(code, "c")
        assert r.success


class TestEdgeCases:

    def test_empty_code(self, extractor):
        r = extractor.parse_code("", "c")
        assert len(r.dfg_edges) == 0
        empty_code = not r.success or len(r.code_tokens) <= 1
        assert empty_code, f"Expected empty/single token, got {len(r.code_tokens)}"

    def test_malformed_code_fallback(self, extractor):
        code = "int main( {{{{{{{ broken }}"
        r = extractor.parse_code(code, "c")
        assert len(r.dfg_edges) == 0
        assert len(r.code_tokens) > 0

    def test_only_comments(self, extractor):
        code = "// just a comment\n/* block comment */"
        r = extractor.parse_code(code, "c")
        assert r.success
        assert len(r.dfg_edges) == 0

    def test_very_long_code(self, extractor):
        code = "int main() { int x = 0; " + "x = x + 1; " * 500 + "return x; }"
        r = extractor.parse_code(code, "c")
        assert r.success

    def test_unicode_identifiers(self, extractor):
        code = 'int main() { int año = 2024; int año_siguiente = año + 1; return 0; }'
        r = extractor.parse_code(code, "c")
        assert r.success

    def test_preprocessor_directives(self, extractor):
        code = """
        #define MAX 100
        #include <stdio.h>
        int main() { int x = MAX; return x; }
        """
        r = extractor.parse_code(code, "c")
        assert r.success

    def test_multiple_declarations_same_line(self, extractor):
        code = "int main() { int a, b, c = 0; a = b; return c; }"
        r = extractor.parse_code(code, "c")
        assert r.success

    def test_pointer_deref(self, extractor):
        code = """
        void swap(int *a, int *b) {
            int tmp = *a;
            *a = *b;
            *b = tmp;
        }
        """
        r = extractor.parse_code(code, "c")
        assert r.success

    def test_ternary_operator(self, extractor):
        code = "int main() { int a = 5, b = 10; int x = a > b ? a : b; return x; }"
        r = extractor.parse_code(code, "c")
        assert r.success


class TestDFGEdgeStructure:

    def test_edge_has_valid_indices(self, extractor):
        code = "int main() { int x = 5; int y = x + 2; return y; }"
        r = extractor.parse_code(code, "c")
        for e in r.dfg_edges:
            assert e.target_index >= 0
            assert e.target_index < len(r.code_tokens)
            for si in e.source_indices:
                assert si >= 0
                assert si < len(r.code_tokens)
            assert e.relation in ("computedFrom", "comesFrom")

    def test_no_duplicate_edges(self, extractor):
        code = "int main() { int a = 1; int b = a; return b; }"
        r = extractor.parse_code(code, "c")
        unique = set()
        for e in r.dfg_edges:
            key = (e.relation, e.target_index, tuple(sorted(e.source_indices)))
            assert key not in unique, f"Duplicate edge: {e}"
            unique.add(key)


class TestDFGResult:

    def test_result_dataclass_defaults(self):
        r = DFGResult()
        assert r.code_tokens == []
        assert r.dfg_edges == []
        assert not r.success

    def test_result_with_data(self, extractor):
        code = "int main() { int x = 5; return x; }"
        r = extractor.parse_code(code, "c")
        assert r.success
        assert len(r.code_tokens) > 0
        assert all(isinstance(t, str) for t in r.code_tokens)

    def test_index_to_code_consistency(self, extractor):
        code = "int main() { int x = 5; return 0; }"
        r = extractor.parse_code(code, "c")
        for idx, tok in r.index_to_code.items():
            assert 0 <= idx < len(r.code_tokens)
            assert r.code_tokens[idx] == tok
