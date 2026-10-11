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


class TestPointersAndAliasing:

    def test_pointer_declaration_with_address_of(self, extractor):
        code = "int main() { int x = 5; int *p = &x; return 0; }"
        r = extractor.parse_code(code, "c")
        assert r.success
        edge = _find_edge(r.dfg_edges, "computedFrom", "p", r.code_tokens)
        assert edge is not None
        assert _edge_has_source(edge, "x", r.code_tokens)

    def test_pointer_dereference_assignment(self, extractor):
        code = "int main() { int x = 5; int *p = &x; *p = 10; return x; }"
        r = extractor.parse_code(code, "c")
        assert r.success
        ret_edge = _find_edge(r.dfg_edges, "comesFrom", "x", r.code_tokens)
        assert ret_edge is not None
        assert _edge_has_source(ret_edge, "p", r.code_tokens)

    def test_pointer_parameters(self, extractor):
        code = "void f(char *dest, const char *src) { *dest = *src; }"
        r = extractor.parse_code(code, "c")
        assert r.success
        edge = _find_edge(r.dfg_edges, "computedFrom", "dest", r.code_tokens)
        assert edge is not None
        assert _edge_has_source(edge, "src", r.code_tokens)


# =============================================================================================
# v2 walker (models.graphcodebert.v2.dfg): GD2-GD6, design D4. The legacy classes above test the
# frozen `parser.py` and stay unchanged.
# =============================================================================================

import hashlib

from models.graphcodebert.v2.dfg import extract_dfg_v2

LEGACY_PARSER = Path(__file__).parent.parent / "models" / "graphcodebert" / "parser.py"
LEGACY_PARSER_SHA256 = "f3cddf7749d8e2e7ed2da77c954ac6e533a9d0536cb0556a816259d069946858"


def test_legacy_parser_is_frozen():
    content = LEGACY_PARSER.read_bytes().replace(b"\r\n", b"\n")
    assert hashlib.sha256(content).hexdigest() == LEGACY_PARSER_SHA256


def _occ(r, token: str, k: int = 0) -> int:
    """Index in `code_tokens` of the k-th occurrence (negative k counts from the end)."""
    positions = [i for i, t in enumerate(r.code_tokens) if t == token]
    assert positions, f"{token!r} not in {r.code_tokens}"
    return positions[k]


def _parents(r, idx: int) -> set[int]:
    """Union of parent indices over every node at `idx`."""
    out = set()
    for code, i, rel, codes, idxs in r.dfg:
        if i == idx:
            out.update(idxs)
    return out


def _has_node(r, idx: int) -> bool:
    return any(n[1] == idx for n in r.dfg)


class TestV2NodeFormat:
    CODE = "int f(){ int a; a = 1; int b = a; return b; }"

    def test_equal_length_parents_and_indices_point_to_tokens(self):
        r = extract_dfg_v2(self.CODE, "c")
        assert r.dfg
        for code, idx, rel, codes, idxs in r.dfg:
            assert rel in ("comesFrom", "computedFrom")
            assert r.code_tokens[idx] == code
            assert len(codes) == len(idxs)
            for pc, pi in zip(codes, idxs):
                assert r.code_tokens[pi] == pc

    def test_deterministic_and_sorted_by_idx(self):
        loop = "int f(int n){ int s = 0; for (int i = 0; i < n; i++) { s = s + i; n = s; } return s; }"
        a, b = extract_dfg_v2(loop, "c"), extract_dfg_v2(loop, "c")
        assert a == b
        idxs = [n[1] for n in a.dfg]
        assert idxs == sorted(idxs)

    def test_edges_are_directional(self):
        r = extract_dfg_v2("int f(int a){ int b = a; return b; }", "c")
        b, a = _occ(r, "b"), _occ(r, "a", 1)
        assert a in _parents(r, b)
        assert b not in _parents(r, a)


class TestV2DefUse:
    def test_declaration_with_initializer_defines(self):
        r = extract_dfg_v2("int f(int a){ int b = a; return b; }", "c")
        assert _parents(r, _occ(r, "b")) == {_occ(r, "a", 1)}
        assert _parents(r, _occ(r, "b", 1)) == {_occ(r, "b")}

    def test_last_definition_wins(self):
        r = extract_dfg_v2("int f(){ int a; a = 1; a = 2; int c = a; return c; }", "c")
        read = _occ(r, "a", 3)
        assert _parents(r, read) == {_occ(r, "a", 2)}
        assert _parents(r, _occ(r, "c")) == {read}

    def test_call_arguments_flow_into_definition(self):
        r = extract_dfg_v2("int f(int a, int b){ int x = g(a, b); return x; }", "c")
        x = _occ(r, "x")
        assert {_occ(r, "a", 1), _occ(r, "b", 1)} <= _parents(r, x)

    def test_compound_assignment_reads_and_writes_lhs(self):
        r = extract_dfg_v2("int f(int x, int y){ x += y; return x; }", "c")
        lhs = _occ(r, "x", 1)
        assert _parents(r, lhs) == {_occ(r, "x"), _occ(r, "y", 1)}
        assert _parents(r, _occ(r, "x", 2)) == {lhs}

    def test_subscript_update_reads_and_writes_base(self):
        r = extract_dfg_v2("void f(int *a, int i){ a[i]++; }", "c")
        a = _occ(r, "a", 1)
        assert a in _parents(r, a)

    def test_field_update_reads_and_writes_base(self):
        r = extract_dfg_v2("struct S { int n; }; void f(struct S s){ s.n++; }", "c")
        s = _occ(r, "s", 1)
        assert s in _parents(r, s)

    def test_binary_unary_cast_subscript_reads(self):
        r = extract_dfg_v2("int f(int a, int *p, int i){ int x = -a + (int)p[i]; return x; }", "c")
        x = _occ(r, "x")
        assert {_occ(r, "a", 1), _occ(r, "p", 1), _occ(r, "i", 1)} <= _parents(r, x)
        assert not any(r.code_tokens[i] == "int" for i in _parents(r, x))


class TestV2ControlFlow:
    @pytest.mark.parametrize("lang", ["c", "cpp"])
    def test_braceless_if_else_unions_both_branches(self, lang):
        code = "int f(int c){ int a = 0; if (c) a = 1; else a = 2; int b = a; return b; }"
        r = extract_dfg_v2(code, lang)
        # Both branches define `a`, so the pre-if definition no longer reaches (design D4).
        assert _parents(r, _occ(r, "a", 3)) == {_occ(r, "a", 1), _occ(r, "a", 2)}

    @pytest.mark.parametrize("lang", ["c", "cpp"])
    def test_if_without_else_keeps_incoming_definition(self, lang):
        r = extract_dfg_v2("int f(int c){ int a = 0; if (c) a = 1; int b = a; return b; }", lang)
        assert _parents(r, _occ(r, "a", 2)) == {_occ(r, "a"), _occ(r, "a", 1)}

    def test_for_loop_carries_definitions_without_duplicates(self):
        r = extract_dfg_v2("int f(int n){ int s = 0; for (int i = 0; i < n; i++) s = s + i; return s; }", "c")
        read = _occ(r, "s", 2)  # `s` on the right of `s = s + i`
        assert _parents(r, read) == {_occ(r, "s"), _occ(r, "s", 1)}
        keys = [(c, i, rel, tuple(idxs)) for c, i, rel, _, idxs in r.dfg]
        assert len(keys) == len(set(keys))

    def test_for_second_pass_after_expression_initializer(self):
        r = extract_dfg_v2("int f(int n){ int i; for (i = 0; i < n; i = i + 1) n = n - 1; return n; }", "c")
        # The condition read of `i` sees the update `i = i + 1` on the second pass (design D4c);
        # upstream only runs that pass after a declaration initializer.
        assert _parents(r, _occ(r, "i", 2)) == {_occ(r, "i", 1), _occ(r, "i", 3)}

    def test_while_and_dedup(self):
        r = extract_dfg_v2("int f(int x){ while (x > 0) x = x - 1; return x; }", "c")
        assert _parents(r, _occ(r, "x", 1)) == {_occ(r, "x"), _occ(r, "x", 2)}

    def test_range_for(self):
        r = extract_dfg_v2("int f(std::vector<int> v){ int s = 0; for (auto x : v) s = s + x; return s; }", "cpp")
        assert _parents(r, _occ(r, "x")) == {_occ(r, "v", 1)}
        assert _parents(r, _occ(r, "s", 2)) == {_occ(r, "s"), _occ(r, "s", 1)}

    def test_do_while(self):
        r = extract_dfg_v2("int f(int x){ int y = 0; do { y = y + x; x = x - 1; } while (x > 0); return y; }", "c")
        assert _parents(r, _occ(r, "x", 1)) == {_occ(r, "x"), _occ(r, "x", 2)}
        assert _occ(r, "x", 2) in _parents(r, _occ(r, "x", 4))

    def test_switch_unions_all_cases(self):
        code = "int f(int c){ int a = 0; switch (c) { case 1: a = 1; break; case 2: a = 2; break; } return a; }"
        r = extract_dfg_v2(code, "c")
        assert _parents(r, _occ(r, "a", -1)) == {_occ(r, "a"), _occ(r, "a", 1), _occ(r, "a", 2)}

    def test_switch_default_case_is_walked(self):
        r = extract_dfg_v2("int f(int c){ int a; switch (c) { default: a = c; } return a; }", "c")
        assert _occ(r, "a", 1) in _parents(r, _occ(r, "a", -1))


class TestV2Declarators:
    def test_pointer_and_reference_declarators(self):
        r = extract_dfg_v2("int f(int a){ int *p = &a; int &r = a; int **q = &p; return *p + r; }", "cpp")
        assert _parents(r, _occ(r, "p")) == {_occ(r, "a", 1)}
        assert _parents(r, _occ(r, "r")) == {_occ(r, "a", 2)}
        assert _parents(r, _occ(r, "q")) == {_occ(r, "p", 1)}

    def test_pointer_return_function_parameters(self):
        r = extract_dfg_v2("char *f(int n){ return n; }", "c")
        assert _parents(r, _occ(r, "n", 1)) == {_occ(r, "n")}

    def test_array_and_reference_parameters(self):
        r = extract_dfg_v2("int f(int a[], int &k){ int x = a[0] + k; return x; }", "cpp")
        assert _parents(r, _occ(r, "a", 1)) == {_occ(r, "a")}
        assert _parents(r, _occ(r, "k", 1)) == {_occ(r, "k")}

    def test_array_declarator_does_not_define_its_size(self):
        r = extract_dfg_v2("int f(){ int a[10] = {0}; int b = a[0]; return b; }", "c")
        ten = _occ(r, "10")
        assert not any(n[1] == ten and n[4] for n in r.dfg)
        assert _parents(r, _occ(r, "a")) == {_occ(r, "0")}


class TestV2Aggregates:
    def test_struct_and_enum_bodies_are_tokens(self):
        code = "struct P { int x; }; enum E { A, B = A }; int f(){ P s; s.x = 1; int y = s.x; return y; }"
        r = extract_dfg_v2(code, "cpp")
        assert _occ(r, "x") < _occ(r, "s")  # field from the struct body
        assert {"A", "B", "E", "P"} <= set(r.code_tokens)
        assert _parents(r, _occ(r, "B")) == {_occ(r, "A", 1)}
        assert _occ(r, "s", 2) in _parents(r, _occ(r, "y"))

    def test_field_write_defines_base_variable(self):
        r = extract_dfg_v2("struct S { int n; }; int f(struct S s){ s.n = 1; int y = s.n; return y; }", "c")
        assert _parents(r, _occ(r, "s", 2)) == {_occ(r, "s", 1)}

    def test_function_scope_reset_and_globals(self):
        r = extract_dfg_v2("int k = 1; int g(){ int a = 1; return a; } int f(){ return a + k; }", "c")
        assert not _parents(r, _occ(r, "a", -1))  # `a` of g does not leak into f
        assert _parents(r, _occ(r, "k", 1)) == {_occ(r, "k")}


class TestV2TokensAndErrors:
    def test_comments_absent(self):
        r = extract_dfg_v2("int f(){ int a = 1; // int z = a;\n /* int w; */ return a; }", "c")
        assert "z" not in r.code_tokens and "w" not in r.code_tokens
        assert not any(t.startswith("//") or t.startswith("/*") for t in r.code_tokens)
        assert _parents(r, _occ(r, "a", 1)) == {_occ(r, "a")}

    def test_comment_markers_inside_strings_survive(self):
        r = extract_dfg_v2('int f(){ char *s = "// not a comment"; return 0; }', "c")
        assert '"// not a comment"' in r.code_tokens

    def test_missing_nodes_skipped(self):
        r = extract_dfg_v2("int f(){ int a = 1; int c = ; return a; }", "c")
        assert r.parse_errors is True
        assert "" not in r.code_tokens

    def test_non_ascii_uses_byte_offsets(self):
        r = extract_dfg_v2('int f(){ char *s = "ñandú"; int a = 1; int b = a; return b; }', "c")
        assert '"ñandú"' in r.code_tokens
        assert _parents(r, _occ(r, "b")) == {_occ(r, "a", 1)}

    def test_parse_error_keeps_dfg(self):
        r = extract_dfg_v2("int f(){ int a = 1; int b = a; int c = ; return b; }", "c")
        assert r.parse_errors is True
        assert _parents(r, _occ(r, "b")) == {_occ(r, "a", 1)}

    def test_clean_parse_has_no_errors(self):
        assert extract_dfg_v2("int f(int a){ return a; }", "c").parse_errors is False

    def test_post_filter_drops_isolated_nodes(self):
        r = extract_dfg_v2("int f(){ int unused; return 0; }", "c")
        assert not _has_node(r, _occ(r, "unused"))
        assert r.n_nodes_raw > len(r.dfg)

