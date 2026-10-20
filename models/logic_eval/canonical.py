"""Deterministic canonical identifier normalization for C/C++ ASTs.

Renames user-defined variables (v1, v2...), functions (f1, f2...), and custom types (t1, t2...)
in order of first appearance, preserving scopes, keywords, stdlib symbols, and main.
"""

from typing import Dict, List, Optional, Set, Tuple
import tree_sitter as ts

from models.evaluation.normalize import KEYWORDS
from models.graphcodebert.v2.dfg import parse_source
from models.robustness.transforms import _apply_byte_edits, _in_error_subtree, _is_error

STDLIB_SYMBOLS: Set[str] = {
    # stdio
    "printf", "scanf", "fprintf", "fscanf", "sprintf", "sscanf", "snprintf", "vprintf",
    "vfprintf", "vsprintf", "vsnprintf", "fgetc", "fgets", "fputc", "fputs", "getc",
    "getchar", "gets", "putc", "putchar", "puts", "ungetc", "fopen", "freopen", "fflush",
    "fclose", "remove", "rename", "tmpfile", "tmpnam", "setvbuf", "setbuf", "fread",
    "fwrite", "fseek", "ftell", "rewind", "fgetpos", "fsetpos", "clearerr", "feof",
    "ferror", "perror", "FILE", "fpos_t", "stdin", "stdout", "stderr", "EOF", "NULL",
    "size_t", "ssize_t", "off_t",
    # stdlib
    "malloc", "calloc", "realloc", "free", "abort", "exit", "atexit", "getenv",
    "system", "bsearch", "qsort", "abs", "labs", "llabs", "div", "ldiv", "lldiv",
    "rand", "srand", "atof", "atoi", "atol", "atoll", "strtod", "strtof", "strtold",
    "strtol", "strtoll", "strtoul", "strtoull", "EXIT_SUCCESS", "EXIT_FAILURE", "RAND_MAX",
    # string
    "strcpy", "strncpy", "strcat", "strncat", "strcmp", "strncmp", "strcoll", "strxfrm",
    "strchr", "strrchr", "strspn", "strcspn", "strpbrk", "strstr", "strtok", "memset",
    "strerror", "strlen", "memcpy", "memmove", "memcmp", "memchr",
    # math
    "sin", "cos", "tan", "asin", "acos", "atan", "atan2", "sinh", "cosh", "tanh",
    "exp", "log", "log10", "pow", "sqrt", "ceil", "floor", "fabs", "ldexp", "frexp",
    "modf", "fmod", "round", "trunc", "hypot", "cbrt", "log2",
    # ctype
    "isalnum", "isalpha", "islower", "isupper", "isdigit", "isxdigit", "iscntrl",
    "isgraph", "isspace", "isblank", "isprint", "ispunct", "tolower", "toupper",
    # time
    "time", "clock", "difftime", "mktime", "strftime", "time_t", "clock_t", "tm",
    # stdint & stdbool & stddef
    "int8_t", "int16_t", "int32_t", "int64_t", "uint8_t", "uint16_t", "uint32_t", "uint64_t",
    "intptr_t", "uintptr_t", "ptrdiff_t", "bool", "true", "false",
    # C++ std / iostream / stl types and streams
    "std", "cin", "cout", "cerr", "clog", "endl", "vector", "string", "map", "set",
    "multimap", "multiset", "unordered_map", "unordered_set", "list", "deque", "queue",
    "priority_queue", "stack", "pair", "tuple",
    "iostream", "istream", "ostream", "stringstream", "istringstream", "ostringstream",
    "ifstream", "ofstream", "fstream", "iterator", "const_iterator",
    # special identifiers
    "main",
}


def _is_reserved(name: str) -> bool:
    return name in KEYWORDS or name in STDLIB_SYMBOLS


def _unwrap_declarator(decl: Optional[ts.Node]) -> Optional[ts.Node]:
    """Unwrap pointer/reference/array/parenthesized declarators to the base declarator."""
    curr = decl
    while curr is not None and curr.type in (
        "pointer_declarator",
        "reference_declarator",
        "array_declarator",
        "parenthesized_declarator",
    ):
        curr = curr.child_by_field_name("declarator") or (
            curr.children[1] if len(curr.children) > 1 and curr.children[1].type != ";" else None
        )
    return curr


def _find_identifiers_in_subtree(node: ts.Node, name: str, source: bytes) -> List[Tuple[int, int]]:
    """Collect byte ranges of identifier nodes with given name, skipping field accesses."""
    spans: List[Tuple[int, int]] = []
    stack = [node]
    while stack:
        curr = stack.pop()
        if _is_error(curr):
            continue  # every descendant is inside an error subtree too: prune (same result, O(n))
        if curr.type == "identifier":
            if source[curr.start_byte:curr.end_byte].decode("utf-8", errors="replace") == name:
                parent = curr.parent
                if parent is not None and parent.type == "field_expression":
                    field_child = parent.child_by_field_name("field")
                    if field_child is not None and field_child.id == curr.id:
                        continue
                if parent is not None and parent.type in (
                    "field_declaration",
                    "using_declaration",
                    "namespace_definition",
                ):
                    continue
                spans.append((curr.start_byte, curr.end_byte))
        stack.extend(reversed(curr.children))
    return spans


def canonicalize_code(code: str, lang: str = "c") -> str:
    """Deterministically rename user variables, functions, and types in order of appearance."""
    source = code.encode("utf-8")
    tree = parse_source(source, lang)
    root = tree.root_node

    edits: Dict[Tuple[int, int], bytes] = {}

    # 1. Custom Types: struct, class, enum, union, typedef
    declared_types: Dict[str, str] = {}
    type_spans: Dict[str, List[Tuple[int, int]]] = {}

    stack = [root]
    while stack:
        n = stack.pop()
        if not _in_error_subtree(n):
            if n.type in ("struct_specifier", "class_specifier", "enum_specifier", "union_specifier"):
                name_node = n.child_by_field_name("name")
                if name_node and name_node.type in ("type_identifier", "identifier"):
                    t_name = source[name_node.start_byte:name_node.end_byte].decode("utf-8", errors="replace")
                    if not _is_reserved(t_name) and t_name not in declared_types:
                        canon_t = f"t{len(declared_types) + 1}"
                        declared_types[t_name] = canon_t
                        type_spans[t_name] = [(name_node.start_byte, name_node.end_byte)]
            elif n.type == "type_definition":
                for child in n.children:
                    if child.type == "type_identifier":
                        t_name = source[child.start_byte:child.end_byte].decode("utf-8", errors="replace")
                        if not _is_reserved(t_name) and t_name not in declared_types:
                            canon_t = f"t{len(declared_types) + 1}"
                            declared_types[t_name] = canon_t
                            type_spans[t_name] = [(child.start_byte, child.end_byte)]
        stack.extend(reversed(n.children))

    # Collect type usages across the entire AST
    if declared_types:
        stack = [root]
        while stack:
            n = stack.pop()
            if not _in_error_subtree(n) and n.type in ("type_identifier", "identifier"):
                t_name = source[n.start_byte:n.end_byte].decode("utf-8", errors="replace")
                if t_name in declared_types:
                    span = (n.start_byte, n.end_byte)
                    type_spans.setdefault(t_name, []).append(span)
            stack.extend(reversed(n.children))

        for t_name, spans in type_spans.items():
            repl = declared_types[t_name].encode("utf-8")
            for span in spans:
                edits[span] = repl

    # 2. Declared Functions (excluding main, stdlib, methods)
    declared_functions: Dict[str, str] = {}
    func_spans: Dict[str, List[Tuple[int, int]]] = {}

    stack = [root]
    while stack:
        n = stack.pop()
        if not _in_error_subtree(n):
            if n.type in ("function_definition", "declaration"):
                decl = n.child_by_field_name("declarator")
                decl = _unwrap_declarator(decl)
                if decl and decl.type == "function_declarator":
                    fname_node = decl.child_by_field_name("declarator") or (
                        decl.children[0] if decl.children else None
                    )
                    fname_node = _unwrap_declarator(fname_node)
                    if fname_node and fname_node.type == "identifier":
                        fname = source[fname_node.start_byte:fname_node.end_byte].decode("utf-8", errors="replace")
                        if (
                            not _is_reserved(fname)
                            and fname not in declared_types
                            and fname not in declared_functions
                        ):
                            canon_f = f"f{len(declared_functions) + 1}"
                            declared_functions[fname] = canon_f
                            func_spans[fname] = [(fname_node.start_byte, fname_node.end_byte)]
        stack.extend(reversed(n.children))

    # Collect function call sites
    if declared_functions:
        stack = [root]
        while stack:
            n = stack.pop()
            if not _in_error_subtree(n) and n.type == "call_expression":
                fn_node = n.child_by_field_name("function")
                if fn_node and fn_node.type == "identifier":
                    fname = source[fn_node.start_byte:fn_node.end_byte].decode("utf-8", errors="replace")
                    if fname in declared_functions:
                        span = (fn_node.start_byte, fn_node.end_byte)
                        func_spans.setdefault(fname, []).append(span)
            stack.extend(reversed(n.children))

        for fname, spans in func_spans.items():
            repl = declared_functions[fname].encode("utf-8")
            for span in spans:
                edits[span] = repl

    # 3. Global Variables
    global_vars: Dict[str, str] = {}
    for child in root.children:
        if not _in_error_subtree(child) and child.type == "declaration":
            for c in child.children:
                target = None
                if c.type == "init_declarator":
                    target = c.child_by_field_name("declarator")
                elif c.type == "identifier":
                    target = c
                target = _unwrap_declarator(target)
                if target and target.type == "identifier":
                    vname = source[target.start_byte:target.end_byte].decode("utf-8", errors="replace")
                    if (
                        not _is_reserved(vname)
                        and vname not in declared_types
                        and vname not in declared_functions
                        and vname not in global_vars
                    ):
                        canon_v = f"v{len(global_vars) + 1}"
                        global_vars[vname] = canon_v
                        for span in _find_identifiers_in_subtree(root, vname, source):
                            edits[span] = canon_v.encode("utf-8")

    n_globals = len(global_vars)

    # 4. Local Variables & Parameters per function definition
    stack = [root]
    while stack:
        n = stack.pop()
        if not _in_error_subtree(n) and n.type == "function_definition":
            local_vars: List[str] = []
            seen_locals: Set[str] = set()

            # Parameters
            decl = n.child_by_field_name("declarator")
            decl = _unwrap_declarator(decl)
            if decl and decl.type == "function_declarator":
                params_node = decl.child_by_field_name("parameters")
                if params_node:
                    for param in params_node.children:
                        if not _in_error_subtree(param) and param.type == "parameter_declaration":
                            pdecl = param.child_by_field_name("declarator")
                            pdecl = _unwrap_declarator(pdecl)
                            if pdecl and pdecl.type == "identifier":
                                pname = source[pdecl.start_byte:pdecl.end_byte].decode("utf-8", errors="replace")
                                if (
                                    not _is_reserved(pname)
                                    and pname not in declared_types
                                    and pname not in declared_functions
                                    and pname not in global_vars
                                    and pname not in seen_locals
                                ):
                                    local_vars.append(pname)
                                    seen_locals.add(pname)

            # Local declarations in body
            body = n.child_by_field_name("body")
            if body and body.type == "compound_statement":
                decl_stack = [body]
                while decl_stack:
                    curr = decl_stack.pop()
                    if not _in_error_subtree(curr) and curr.type == "declaration":
                        for c in curr.children:
                            target = None
                            if c.type == "init_declarator":
                                target = c.child_by_field_name("declarator")
                            elif c.type == "identifier":
                                target = c
                            target = _unwrap_declarator(target)
                            if target and target.type == "identifier":
                                vname = source[target.start_byte:target.end_byte].decode("utf-8", errors="replace")
                                if (
                                    not _is_reserved(vname)
                                    and vname not in declared_types
                                    and vname not in declared_functions
                                    and vname not in global_vars
                                    and vname not in seen_locals
                                ):
                                    local_vars.append(vname)
                                    seen_locals.add(vname)
                    # Traverse into nested blocks and loops, but don't enter nested functions
                    if curr.type != "function_definition" or curr.id == body.id:
                        decl_stack.extend(reversed(curr.children))

            # Assign local canonical names
            for idx, vname in enumerate(local_vars):
                canon_v = f"v{n_globals + idx + 1}"
                repl = canon_v.encode("utf-8")
                for span in _find_identifiers_in_subtree(n, vname, source):
                    edits[span] = repl

        stack.extend(reversed(n.children))

    # Apply byte edits from right to left
    edit_list = [(span[0], span[1], repl) for span, repl in edits.items()]
    new_source = _apply_byte_edits(source, edit_list)
    return new_source.decode("utf-8", errors="replace")
