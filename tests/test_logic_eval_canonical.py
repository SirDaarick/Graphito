"""Tests for canonical identifier normalization in models.logic_eval.canonical."""

import pytest
from models.graphcodebert.v2.dfg import parse_source
from models.robustness.validity import count_error_nodes


def test_canonical_determinism():
    from models.logic_eval.canonical import canonicalize_code

    code = """
    #include <stdio.h>
    int calculate(int val, int factor) {
        int temp = val * factor;
        return temp;
    }
    int main() {
        int input = 5;
        int result = calculate(input, 2);
        printf("%d\\n", result);
        return 0;
    }
    """
    res1 = canonicalize_code(code, "c")
    res2 = canonicalize_code(code, "c")
    assert res1 == res2
    assert len(res1) > 0


def test_canonical_invariance():
    from models.logic_eval.canonical import canonicalize_code

    code1 = """
    int sum_values(int a, int b) {
        int res = a + b;
        return res;
    }
    """
    code2 = """
    int add_numbers(int x, int y) {
        int total = x + y;
        return total;
    }
    """
    canon1 = canonicalize_code(code1, "c")
    canon2 = canonicalize_code(code2, "c")
    assert canon1 == canon2
    assert "f1" in canon1
    assert "v1" in canon1
    assert "v2" in canon1
    assert "v3" in canon1


def test_canonical_preserves_keywords_stdlib_main():
    from models.logic_eval.canonical import canonicalize_code

    code = """
    #include <stdio.h>
    #include <stdlib.h>

    int main() {
        size_t n = 10;
        int *arr = (int *)malloc(n * sizeof(int));
        for (int i = 0; i < n; i++) {
            scanf("%d", &arr[i]);
            printf("%d\\n", arr[i]);
        }
        free(arr);
        return 0;
    }
    """
    canon = canonicalize_code(code, "c")
    assert "main" in canon
    assert "printf" in canon
    assert "scanf" in canon
    assert "malloc" in canon
    assert "free" in canon
    assert "sizeof" in canon
    assert "for" in canon
    assert "return 0;" in canon


def test_canonical_scope_handling():
    from models.logic_eval.canonical import canonicalize_code

    code1 = """
    int func_a(int i) {
        int count = i + 1;
        return count;
    }
    int func_b(int i) {
        int count = i * 2;
        return count;
    }
    """
    code2 = """
    int worker_one(int x) {
        int alpha = x + 1;
        return alpha;
    }
    int worker_two(int y) {
        int beta = y * 2;
        return beta;
    }
    """
    canon1 = canonicalize_code(code1, "c")
    canon2 = canonicalize_code(code2, "c")
    assert canon1 == canon2


def test_canonical_struct_types_and_fields():
    from models.logic_eval.canonical import canonicalize_code

    code1 = """
    struct Point {
        int x;
        int y;
    };
    int get_x(struct Point p) {
        return p.x;
    }
    """
    code2 = """
    struct Coordinate {
        int x;
        int y;
    };
    int fetch_x(struct Coordinate pt) {
        return pt.x;
    }
    """
    canon1 = canonicalize_code(code1, "c")
    canon2 = canonicalize_code(code2, "c")
    assert canon1 == canon2
    # Field 'x' must be preserved, struct type replaced by t1
    assert "t1" in canon1
    assert ".x" in canon1


def test_canonical_syntax_validity():
    from models.logic_eval.canonical import canonicalize_code

    code = """
    #include <stdio.h>
    int solve(int num) {
        int count = 0;
        while (num > 0) {
            if (num % 2 == 0) {
                count++;
            }
            num /= 2;
        }
        return count;
    }
    int main() {
        int val;
        if (scanf("%d", &val) == 1) {
            printf("%d\\n", solve(val));
        }
        return 0;
    }
    """
    tree_orig = parse_source(code.encode("utf-8"), "c")
    orig_errors = count_error_nodes(tree_orig.root_node)
    assert orig_errors == 0

    canon = canonicalize_code(code, "c")
    tree_canon = parse_source(canon.encode("utf-8"), "c")
    canon_errors = count_error_nodes(tree_canon.root_node)
    assert canon_errors == 0
