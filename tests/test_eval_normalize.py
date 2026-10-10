"""C/C++ normalization: comment stripping, effective length, norm hash and shingle tokens."""

from models.evaluation.normalize import (
    effective_length,
    norm_hash,
    shingle_tokens,
    strip_comments,
    tokenize,
)


def test_strip_removes_line_and_block_comments():
    out = strip_comments("int a; // tail\n/* block\n spans */ int b;\n")
    assert "tail" not in out and "block" not in out and "spans" not in out
    assert "int a;" in out and "int b;" in out


def test_strip_keeps_comment_markers_inside_literals():
    code = 'char *s = "// not a comment";\nchar c = \'/\';\nchar *t = "/* nor this */";\n'
    assert strip_comments(code) == code


def test_strip_handles_escaped_quote_in_string():
    out = strip_comments('char *s = "a\\" // still string"; // real comment\n')
    assert '"a\\" // still string"' in out
    assert "real comment" not in out


def test_strip_preserves_line_count_for_block_comments():
    code = "a\n/* x\ny\nz */\nb\n"
    assert strip_comments(code).count("\n") == code.count("\n")


def test_strip_unterminated_block_comment_runs_to_end():
    assert strip_comments("int a; /* never closed\nint b;").strip() == "int a;"


def test_effective_length_counts_only_code_without_whitespace():
    assert effective_length("int a;") == 5
    assert effective_length("  int \n a ;  ") == 5
    assert effective_length("// only a comment\n/* and another */\n") == 0
    assert effective_length("") == 0


def test_effective_length_threshold_boundary():
    below = "x" * 49
    at = "x" * 50
    assert effective_length(below) < 50 <= effective_length(at)
    assert effective_length(f"/* long comment */ {below}\n// more\n") == 49


def test_norm_hash_ignores_comments_and_whitespace():
    a = "int main() { return 0; }"
    b = "int  main ( )\n{\n  // say hi\n  return 0 ; /* done */\n}\n"
    assert norm_hash(a) == norm_hash(b)
    assert len(norm_hash(a)) == 16


def test_norm_hash_changes_with_logic_and_identifiers():
    base = "int f(int x) { return x + 1; }"
    assert norm_hash(base) != norm_hash("int f(int x) { return x + 2; }")
    assert norm_hash(base) != norm_hash("int g(int x) { return x + 1; }")


def test_tokenize_splits_literals_numbers_and_operators():
    tokens = tokenize('x <<= 0x1F; y = 1.5f; s = "a b"; c = \'q\'; p->q++;')
    assert tokens == [
        "x", "<<=", "0x1F", ";",
        "y", "=", "1.5f", ";",
        "s", "=", '"a b"', ";",
        "c", "=", "'q'", ";",
        "p", "->", "q", "++", ";",
    ]


def test_tokenize_ignores_comments():
    assert tokenize("a /* b */ + c // d") == ["a", "+", "c"]


def test_shingle_tokens_maps_identifiers_and_literals_keeps_keywords():
    code = 'int total = count + 42; printf("hi"); char c = \'x\';'
    assert shingle_tokens(code) == [
        "int", "ID", "=", "ID", "+", "NUM", ";",
        "ID", "(", "STR", ")", ";",
        "char", "ID", "=", "CHR", ";",
    ]


def test_shingle_tokens_are_invariant_to_identifier_renaming():
    a = "for (int i = 0; i < n; i++) { sum += v[i]; }"
    b = "for (int idx = 0; idx < count; idx++) { acc += arr[idx]; }"
    assert shingle_tokens(a) == shingle_tokens(b)


def test_shingle_tokens_keep_cpp_keywords():
    tokens = shingle_tokens("template <typename T> class Box : public Base { virtual void run() override; };")
    for kw in ("template", "typename", "class", "public", "virtual", "void", "override"):
        assert kw in tokens
    assert "Box" not in tokens and "Base" not in tokens
