"""Semantic-preserving code transformations (T0-T7) implemented on Tree-sitter ASTs."""

from dataclasses import dataclass
import hashlib
import random
import re
from typing import Callable, Dict, List, Optional, Sequence, Set, Tuple
import tree_sitter as ts

from models.evaluation.normalize import KEYWORDS
from models.graphcodebert.v2.dfg import parse_source, prepare_source
from models.robustness.validity import count_error_nodes


@dataclass(frozen=True)
class TransformResult:
    code: str
    n_eligible: int
    n_applied: int


def derive_seed(base_seed: int, file_sha256: str, transform: str, intensity: float | str) -> int:
    """Derive a deterministic 64-bit integer seed for a file, transform and intensity."""
    key = f"{base_seed}:{file_sha256}:{transform}:{intensity}".encode("utf-8")
    return int(hashlib.sha256(key).hexdigest()[:16], 16)


# --- Tree-sitter traversal & edit helpers --------------------------------------------------------


def _is_error(node: ts.Node) -> bool:
    return node.type in ("ERROR", "MISSING") or getattr(node, "is_missing", False)


def _in_error_subtree(node: ts.Node) -> bool:
    curr = node
    while curr is not None:
        if _is_error(curr):
            return True
        curr = curr.parent
    return False


def _has_error(node: ts.Node) -> bool:
    return getattr(node, "has_error", False) or count_error_nodes(node) > 0


def _apply_byte_edits(source: bytes, edits: Sequence[Tuple[int, int, bytes]]) -> bytes:
    """Apply non-overlapping byte range edits from right to left."""
    if not edits:
        return source
    sorted_edits = sorted(edits, key=lambda x: x[0], reverse=True)
    buf = bytearray(source)
    for start, end, repl in sorted_edits:
        buf[start:end] = repl
    return bytes(buf)


def _filter_disjoint_nodes(nodes: Sequence[ts.Node]) -> List[ts.Node]:
    """Filter nodes so no node is a descendant or overlapping with another."""
    disjoint: List[ts.Node] = []
    # Sort outer/longer spans first
    sorted_nodes = sorted(nodes, key=lambda n: (n.start_byte, -n.end_byte))
    for n in sorted_nodes:
        if not any(not (n.end_byte <= chosen.start_byte or chosen.end_byte <= n.start_byte) for chosen in disjoint):
            disjoint.append(n)
    return disjoint


# --- T0: Identity (Baseline) --------------------------------------------------------------------


def t0_identity(code: str, lang: str, p: float = 1.0, seed: int = 0) -> TransformResult:
    """Identity transform: returns original code untouched byte-for-byte."""
    return TransformResult(code=code, n_eligible=0, n_applied=0)


# --- T1: Identifier Renaming (Control) ----------------------------------------------------------


def _is_inside_class_or_struct(node: ts.Node) -> bool:
    """True if node sits inside class or struct definition (member/method)."""
    curr = node.parent
    while curr is not None:
        if curr.type in ("class_specifier", "struct_specifier", "field_declaration_list"):
            return True
        curr = curr.parent
    return False


def _find_identifiers_in_subtree(node: ts.Node, name: str, source: bytes) -> List[Tuple[int, int]]:
    """Collect byte ranges of identifier nodes with the given name, skipping field accesses."""
    spans: List[Tuple[int, int]] = []
    stack = [node]
    while stack:
        curr = stack.pop()
        if curr.type == "identifier":
            if source[curr.start_byte:curr.end_byte].decode("utf-8", errors="replace") == name:
                parent = curr.parent
                # Avoid struct/class field identifiers (e.g. p.x or p->x)
                if parent is not None and parent.type == "field_expression":
                    field_child = parent.child_by_field_name("field")
                    if field_child is not None and field_child.id == curr.id:
                        continue
                if parent is not None and parent.type in ("field_declaration", "using_declaration", "namespace_definition"):
                    continue
                spans.append((curr.start_byte, curr.end_byte))
        stack.extend(reversed(curr.children))
    return spans


def t1_rename_identifiers(code: str, lang: str, p: float = 1.0, seed: int = 0) -> TransformResult:
    """T1: Rename declared local variables, parameters, and local free functions (excluding main).
    
    Guarantees that replacement names never collide with existing identifiers or normalize.KEYWORDS.
    Preserves Jaccard token shingle sets exactly (proof of H2).
    """
    source = code.encode("utf-8")
    tree = parse_source(source, lang)
    root = tree.root_node

    existing_tokens = set(re.findall(r"[A-Za-z_]\w*", code))

    # Collect declared type names (struct/class/enum names) so we don't rename constructors or types
    type_names: Set[str] = set()
    stack = [root]
    while stack:
        n = stack.pop()
        if n.type in ("type_identifier", "struct_specifier", "class_specifier"):
            t_id = n.child_by_field_name("name") or (n if n.type == "type_identifier" else None)
            if t_id and t_id.type in ("type_identifier", "identifier"):
                type_names.add(source[t_id.start_byte:t_id.end_byte].decode("utf-8", errors="replace"))
        stack.extend(reversed(n.children))

    # 1. Identify declared free functions (excluding main and class methods/constructors)
    declared_functions: Dict[str, ts.Node] = {}
    stack = [root]
    while stack:
        n = stack.pop()
        if n.type == "function_definition" and not _in_error_subtree(n):
            if not _is_inside_class_or_struct(n):
                decl = n.child_by_field_name("declarator")
                while decl and decl.type in ("pointer_declarator", "reference_declarator", "parenthesized_declarator"):
                    decl = decl.child_by_field_name("declarator") or (decl.children[1] if len(decl.children) > 1 else None)
                if decl and decl.type == "function_declarator":
                    name_node = decl.child_by_field_name("declarator") or decl.children[0]
                    while name_node and name_node.type in ("pointer_declarator", "parenthesized_declarator"):
                        name_node = name_node.child_by_field_name("declarator") or name_node.children[0]
                    if name_node and name_node.type == "identifier":
                        fname = source[name_node.start_byte:name_node.end_byte].decode("utf-8", errors="replace")
                        if fname != "main" and fname not in type_names and fname not in declared_functions:
                            declared_functions[fname] = n
        stack.extend(reversed(n.children))

    # 2. Identify local variables and parameters inside function definitions
    local_symbols: Dict[Tuple[int, str], List[Tuple[int, int]]] = {}
    stack = [root]
    while stack:
        n = stack.pop()
        if n.type == "function_definition" and not _in_error_subtree(n):
            func_id = n.id
            names_in_func: Set[str] = set()
            shadowed: Set[str] = set()

            # Find parameters
            params_node = None
            decl = n.child_by_field_name("declarator")
            while decl and decl.type in ("pointer_declarator", "reference_declarator"):
                decl = decl.child_by_field_name("declarator")
            if decl and decl.type == "function_declarator":
                params_node = decl.child_by_field_name("parameters")

            if params_node:
                for param in params_node.children:
                    if param.type == "parameter_declaration":
                        pdecl = param.child_by_field_name("declarator")
                        while pdecl and pdecl.type in ("pointer_declarator", "reference_declarator"):
                            pdecl = pdecl.child_by_field_name("declarator")
                        if pdecl and pdecl.type == "identifier":
                            pname = source[pdecl.start_byte:pdecl.end_byte].decode("utf-8", errors="replace")
                            names_in_func.add(pname)

            # Find local declarations inside body
            body = n.child_by_field_name("body")
            if body and body.type == "compound_statement":
                decl_stack = [body]
                while decl_stack:
                    curr = decl_stack.pop()
                    if curr.type == "declaration":
                        for c in curr.children:
                            target = None
                            if c.type == "init_declarator":
                                target = c.child_by_field_name("declarator")
                            elif c.type == "identifier":
                                target = c
                            while target and target.type in ("pointer_declarator", "reference_declarator", "array_declarator"):
                                target = target.child_by_field_name("declarator")
                            if target and target.type == "identifier":
                                vname = source[target.start_byte:target.end_byte].decode("utf-8", errors="replace")
                                if vname in names_in_func:
                                    shadowed.add(vname)
                                else:
                                    names_in_func.add(vname)
                    if curr.type != "function_definition" or curr.id == body.id:
                        decl_stack.extend(reversed(curr.children))

            for sname in sorted(names_in_func - shadowed):
                if sname not in declared_functions and sname != "main" and sname not in type_names:
                    spans = _find_identifiers_in_subtree(n, sname, source)
                    if spans:
                        local_symbols[(func_id, sname)] = spans

        stack.extend(reversed(n.children))

    # Also collect call sites for declared functions
    func_symbols: Dict[str, List[Tuple[int, int]]] = {}
    for fname in declared_functions:
        spans = []
        stack = [root]
        while stack:
            curr = stack.pop()
            if curr.type == "identifier":
                t = source[curr.start_byte:curr.end_byte].decode("utf-8", errors="replace")
                if t == fname:
                    parent = curr.parent
                    if parent is not None:
                        is_func_decl = parent.type == "function_declarator" and parent.child_by_field_name("declarator") == curr
                        is_call = parent.type == "call_expression" and parent.child_by_field_name("function") == curr
                        if is_func_decl or is_call:
                            spans.append((curr.start_byte, curr.end_byte))
            stack.extend(reversed(curr.children))
        if spans:
            func_symbols[fname] = spans

    all_symbols = [("func", k, v) for k, v in func_symbols.items()] + [("var", k, v) for k, v in local_symbols.items()]
    n_eligible = len(all_symbols)
    if n_eligible == 0:
        return TransformResult(code=code, n_eligible=0, n_applied=0)

    rng = random.Random(seed)
    k = max(1, int(round(p * n_eligible))) if p > 0 else 0
    selected = rng.sample(all_symbols, k)

    edits: List[Tuple[int, int, bytes]] = []
    used_names = set(existing_tokens) | set(KEYWORDS) | type_names
    v_count = 1
    f_count = 1

    for kind, sym_key, spans in selected:
        if kind == "func":
            while f"f_{f_count}" in used_names:
                f_count += 1
            new_name = f"f_{f_count}"
            f_count += 1
        else:
            while f"v_{v_count}" in used_names:
                v_count += 1
            new_name = f"v_{v_count}"
            v_count += 1
        used_names.add(new_name)
        new_bytes = new_name.encode("utf-8")
        for start, end in spans:
            edits.append((start, end, new_bytes))

    new_source = _apply_byte_edits(source, edits)
    return TransformResult(code=new_source.decode("utf-8", errors="replace"), n_eligible=n_eligible, n_applied=len(selected))


# --- T2: For <-> While Conversion ---------------------------------------------------------------


def _has_belonging_continue(for_node: ts.Node) -> bool:
    """True if for_node contains a `continue` that belongs to this loop (not an inner loop)."""
    stack = list(for_node.children)
    while stack:
        curr = stack.pop()
        if curr.type == "continue_statement":
            return True
        if curr.type not in ("for_statement", "while_statement", "do_statement"):
            stack.extend(reversed(curr.children))
    return False


def _parse_for_header(for_node: ts.Node, source: bytes) -> Optional[Tuple[str, str, str, ts.Node]]:
    """Parse for loop components: (init_str, cond_str, update_str, body_node)."""
    children = for_node.children
    try:
        l_idx = next(i for i, c in enumerate(children) if c.type == "(")
        r_idx = next(i for i, c in enumerate(children) if c.type == ")")
    except StopIteration:
        return None

    header = children[l_idx + 1:r_idx]
    body = children[r_idx + 1] if r_idx + 1 < len(children) else None
    if not body:
        return None

    if header and header[0].type == "declaration":
        init_str = source[header[0].start_byte:header[0].end_byte].decode("utf-8", errors="replace").strip()
        rest = header[1:]
        semi_idx = next((i for i, c in enumerate(rest) if c.type == ";"), -1)
        if semi_idx == -1:
            return None
        cond_nodes = rest[:semi_idx]
        update_nodes = rest[semi_idx + 1:]
    else:
        semi_indices = [i for i, c in enumerate(header) if c.type == ";"]
        if len(semi_indices) < 2:
            return None
        s1, s2 = semi_indices[0], semi_indices[1]
        init_nodes = header[:s1]
        cond_nodes = header[s1 + 1:s2]
        update_nodes = header[s2 + 1:]
        if init_nodes:
            init_str = source[init_nodes[0].start_byte:init_nodes[-1].end_byte].decode("utf-8", errors="replace").strip()
            if not init_str.endswith(";"):
                init_str += ";"
        else:
            init_str = ""

    cond_str = source[cond_nodes[0].start_byte:cond_nodes[-1].end_byte].decode("utf-8", errors="replace").strip() if cond_nodes else "1"
    update_str = source[update_nodes[0].start_byte:update_nodes[-1].end_byte].decode("utf-8", errors="replace").strip() if update_nodes else ""
    return (init_str, cond_str, update_str, body)


def t2_for_while(code: str, lang: str, p: float = 1.0, seed: int = 0) -> TransformResult:
    """T2: Convert for loops to while loops and while loops to for loops."""
    source = code.encode("utf-8")
    tree = parse_source(source, lang)
    root = tree.root_node

    eligible_nodes: List[Tuple[str, ts.Node]] = []
    stack = [root]
    while stack:
        n = stack.pop()
        if not _in_error_subtree(n):
            if n.type == "for_statement":
                if not _has_belonging_continue(n) and _parse_for_header(n, source) is not None:
                    eligible_nodes.append(("for", n))
            elif n.type == "while_statement":
                parent = n.parent
                if parent is None or parent.type != "do_statement":
                    eligible_nodes.append(("while", n))
        stack.extend(reversed(n.children))

    n_eligible = len(eligible_nodes)
    if n_eligible == 0:
        return TransformResult(code=code, n_eligible=0, n_applied=0)

    rng = random.Random(seed)
    k = max(1, int(round(p * n_eligible))) if p > 0 else 0
    selected_raw = rng.sample(eligible_nodes, k)

    # Filter disjoint nodes
    node_map = {n.id: (kind, n) for kind, n in selected_raw}
    disjoint_nodes = _filter_disjoint_nodes([n for _, n in selected_raw])
    selected = [node_map[n.id] for n in disjoint_nodes]

    edits: List[Tuple[int, int, bytes]] = []
    for kind, node in selected:
        if kind == "for":
            parsed = _parse_for_header(node, source)
            if not parsed:
                continue
            init_str, cond_str, update_str, body_node = parsed

            if body_node.type == "compound_statement":
                body_bytes = source[body_node.start_byte:body_node.end_byte]
                inner_text = body_bytes.decode("utf-8", errors="replace").strip()
                if inner_text.startswith("{") and inner_text.endswith("}"):
                    inner_content = inner_text[1:-1].strip()
                else:
                    inner_content = inner_text
                if update_str:
                    new_body = f"{{ {inner_content} {update_str}; }}" if inner_content else f"{{ {update_str}; }}"
                else:
                    new_body = f"{{ {inner_content} }}"
            else:
                body_str = source[body_node.start_byte:body_node.end_byte].decode("utf-8", errors="replace").strip()
                if update_str:
                    new_body = f"{{ {body_str} {update_str}; }}"
                else:
                    new_body = f"{{ {body_str} }}"

            if init_str:
                repl = f"{{ {init_str} while ({cond_str}) {new_body} }}"
            else:
                repl = f"while ({cond_str}) {new_body}"

            edits.append((node.start_byte, node.end_byte, repl.encode("utf-8")))

        elif kind == "while":
            lparen = None
            for c in node.children:
                if c.type == "parenthesized_expression":
                    cond_inner = source[c.start_byte + 1:c.end_byte - 1].decode("utf-8", errors="replace").strip()
                    break
            else:
                continue

            body_node = node.children[-1]
            body_str = source[body_node.start_byte:body_node.end_byte].decode("utf-8", errors="replace").strip()
            repl = f"for (; {cond_inner}; ) {body_str}"
            edits.append((node.start_byte, node.end_byte, repl.encode("utf-8")))

    new_source = _apply_byte_edits(source, edits)
    return TransformResult(code=new_source.decode("utf-8", errors="replace"), n_eligible=n_eligible, n_applied=len(edits))


# --- T3: Statement and Declaration Reordering ----------------------------------------------------


def _read_write_sets(stmt: ts.Node, source: bytes) -> Optional[Tuple[Set[str], Set[str]]]:
    """Calculate (writes, reads) for a statement node. Returns None if ineligible (calls, pointers)."""
    stack = [stmt]
    while stack:
        curr = stack.pop()
        if curr.type == "call_expression":
            return None
        if curr.type == "assignment_expression":
            lhs = curr.child_by_field_name("left") or curr.children[0]
            if lhs.type in ("subscript_expression", "pointer_expression", "field_expression"):
                return None
        stack.extend(curr.children)

    writes: Set[str] = set()
    reads: Set[str] = set()

    if stmt.type == "declaration":
        for c in stmt.children:
            if c.type == "init_declarator":
                decl = c.child_by_field_name("declarator") or c.children[0]
                while decl and decl.type in ("pointer_declarator", "reference_declarator", "array_declarator"):
                    decl = decl.child_by_field_name("declarator")
                if decl and decl.type == "identifier":
                    writes.add(source[decl.start_byte:decl.end_byte].decode("utf-8", errors="replace"))
                init = c.child_by_field_name("value")
                if init:
                    for id_node in re.findall(r"[A-Za-z_]\w*", source[init.start_byte:init.end_byte].decode("utf-8", errors="replace")):
                        if id_node not in KEYWORDS:
                            reads.add(id_node)
            elif c.type == "identifier":
                writes.add(source[c.start_byte:c.end_byte].decode("utf-8", errors="replace"))

    elif stmt.type == "expression_statement":
        expr = stmt.children[0] if stmt.children else None
        if not expr:
            return None
        if expr.type == "assignment_expression":
            lhs = expr.child_by_field_name("left") or expr.children[0]
            if lhs.type == "identifier":
                writes.add(source[lhs.start_byte:lhs.end_byte].decode("utf-8", errors="replace"))
            else:
                return None
            rhs = expr.child_by_field_name("right") or expr.children[2]
            for id_node in re.findall(r"[A-Za-z_]\w*", source[rhs.start_byte:rhs.end_byte].decode("utf-8", errors="replace")):
                if id_node not in KEYWORDS:
                    reads.add(id_node)
        elif expr.type == "update_expression":
            arg = expr.child_by_field_name("argument")
            if arg and arg.type == "identifier":
                name = source[arg.start_byte:arg.end_byte].decode("utf-8", errors="replace")
                writes.add(name)
                reads.add(name)
            else:
                return None
        else:
            for id_node in re.findall(r"[A-Za-z_]\w*", source[expr.start_byte:expr.end_byte].decode("utf-8", errors="replace")):
                if id_node not in KEYWORDS:
                    reads.add(id_node)

    return (writes, reads)


def t3_reorder_stmts(code: str, lang: str, p: float = 1.0, seed: int = 0) -> TransformResult:
    """T3: Swap independent adjacent statements/declarations respecting read/write sets."""
    source = code.encode("utf-8")
    tree = parse_source(source, lang)
    root = tree.root_node

    candidate_pairs: List[Tuple[ts.Node, ts.Node]] = []
    stack = [root]
    while stack:
        n = stack.pop()
        if n.type == "compound_statement" and not _in_error_subtree(n):
            stmts = [c for c in n.children if c.type in ("declaration", "expression_statement")]
            i = 0
            while i < len(stmts) - 1:
                s1, s2 = stmts[i], stmts[i + 1]
                if s1.type == s2.type:
                    rw1 = _read_write_sets(s1, source)
                    rw2 = _read_write_sets(s2, source)
                    if rw1 is not None and rw2 is not None:
                        w1, r1 = rw1
                        w2, r2 = rw2
                        if w1.isdisjoint(r2 | w2) and w2.isdisjoint(r1):
                            candidate_pairs.append((s1, s2))
                            i += 1
                i += 1
        stack.extend(reversed(n.children))

    n_eligible = len(candidate_pairs)
    if n_eligible == 0:
        return TransformResult(code=code, n_eligible=0, n_applied=0)

    rng = random.Random(seed)
    k = max(1, int(round(p * n_eligible))) if p > 0 else 0
    selected = rng.sample(candidate_pairs, k)

    edits: List[Tuple[int, int, bytes]] = []
    for s1, s2 in selected:
        s1_bytes = source[s1.start_byte:s1.end_byte]
        s2_bytes = source[s2.start_byte:s2.end_byte]
        mid_bytes = source[s1.end_byte:s2.start_byte]
        repl = s2_bytes + mid_bytes + s1_bytes
        edits.append((s1.start_byte, s2.end_byte, repl))

    new_source = _apply_byte_edits(source, edits)
    return TransformResult(code=new_source.decode("utf-8", errors="replace"), n_eligible=n_eligible, n_applied=len(edits))


# --- T4: Equivalent Operators -------------------------------------------------------------------


def t4_operators(code: str, lang: str, p: float = 1.0, seed: int = 0) -> TransformResult:
    """T4: Rewrite operators between equivalent forms (x = x + 1 <-> x += 1 <-> x++, etc.)."""
    source = code.encode("utf-8")
    tree = parse_source(source, lang)
    root = tree.root_node

    eligible_ops: List[Tuple[int, int, str]] = []
    stack = [root]
    while stack:
        n = stack.pop()
        if not _in_error_subtree(n):
            if n.type == "assignment_expression":
                lhs = n.child_by_field_name("left") or n.children[0]
                if lhs and lhs.type == "identifier":
                    x = source[lhs.start_byte:lhs.end_byte].decode("utf-8", errors="replace")
                    op = n.children[1].type
                    rhs = n.child_by_field_name("right") or n.children[2]

                    if op == "=" and rhs.type == "binary_expression":
                        b_left = rhs.child_by_field_name("left")
                        b_op = rhs.children[1].type
                        b_right = rhs.child_by_field_name("right")
                        if b_left and b_left.type == "identifier":
                            b_x = source[b_left.start_byte:b_left.end_byte].decode("utf-8", errors="replace")
                            if b_x == x and b_op in ("+", "-", "*", "/", "%", "&", "|", "^", "<<", ">>"):
                                r_text = source[b_right.start_byte:b_right.end_byte].decode("utf-8", errors="replace")
                                if b_op == "+" and r_text == "1":
                                    eligible_ops.append((n.start_byte, n.end_byte, f"{x} += 1"))
                                elif b_op == "-" and r_text == "1":
                                    eligible_ops.append((n.start_byte, n.end_byte, f"{x} -= 1"))
                                else:
                                    eligible_ops.append((n.start_byte, n.end_byte, f"{x} {b_op}= ({r_text})"))

                    elif op in ("+=", "-=", "*=", "/=", "%=", "&=", "|=", "^=", "<<=", ">>="):
                        base_op = op[:-1]
                        r_text = source[rhs.start_byte:rhs.end_byte].decode("utf-8", errors="replace")
                        eligible_ops.append((n.start_byte, n.end_byte, f"{x} = {x} {base_op} ({r_text})"))

            elif n.type == "update_expression":
                parent = n.parent
                if parent is not None and parent.type in ("expression_statement", "for_statement"):
                    arg = n.child_by_field_name("argument")
                    if arg and arg.type == "identifier":
                        x = source[arg.start_byte:arg.end_byte].decode("utf-8", errors="replace")
                        if n.children[0].type in ("++", "--"):
                            u_op = n.children[0].type
                            eligible_ops.append((n.start_byte, n.end_byte, f"{x}{u_op}"))
                        elif len(n.children) > 1 and n.children[1].type in ("++", "--"):
                            u_op = n.children[1].type
                            eligible_ops.append((n.start_byte, n.end_byte, f"{u_op}{x}"))

        stack.extend(reversed(n.children))

    n_eligible = len(eligible_ops)
    if n_eligible == 0:
        return TransformResult(code=code, n_eligible=0, n_applied=0)

    rng = random.Random(seed)
    k = max(1, int(round(p * n_eligible))) if p > 0 else 0
    selected = rng.sample(eligible_ops, k)

    edits = [(start, end, repl.encode("utf-8")) for start, end, repl in selected]
    new_source = _apply_byte_edits(source, edits)
    return TransformResult(code=new_source.decode("utf-8", errors="replace"), n_eligible=n_eligible, n_applied=len(edits))


# --- T5: Benign Dead Code Insertion -------------------------------------------------------------


def t5_dead_code(code: str, lang: str, p: float = 1.0, seed: int = 0) -> TransformResult:
    """T5: Insert benign dead code blocks (if (0) { ; } or (void)0;) after statements."""
    source = code.encode("utf-8")
    tree = parse_source(source, lang)
    root = tree.root_node

    insertion_points: List[int] = []
    stack = [root]
    while stack:
        n = stack.pop()
        if n.type == "compound_statement" and not _in_error_subtree(n):
            children = [c for c in n.children if c.type not in ("{", "}", "comment")]
            last_decl_idx = -1
            for idx, c in enumerate(children):
                if c.type == "declaration":
                    last_decl_idx = idx

            for idx, c in enumerate(children):
                if idx >= last_decl_idx and c.type != "declaration":
                    insertion_points.append(c.end_byte)

        stack.extend(reversed(n.children))

    n_eligible = len(insertion_points)
    if n_eligible == 0:
        return TransformResult(code=code, n_eligible=0, n_applied=0)

    rng = random.Random(seed)
    k = max(1, int(round(p * n_eligible))) if p > 0 else 0
    selected = rng.sample(insertion_points, k)

    templates = [b"\n    if (0) { ; }", b"\n    (void)0;"]
    edits = [(pos, pos, rng.choice(templates)) for pos in selected]

    new_source = _apply_byte_edits(source, edits)
    return TransformResult(code=new_source.decode("utf-8", errors="replace"), n_eligible=n_eligible, n_applied=len(edits))


# --- T6: Branch Inversion (If / Else) -----------------------------------------------------------


def t6_invert_if(code: str, lang: str, p: float = 1.0, seed: int = 0) -> TransformResult:
    """T6: Invert if/else branches using !(cond) with braced bodies."""
    source = code.encode("utf-8")
    tree = parse_source(source, lang)
    root = tree.root_node

    eligible_ifs: List[ts.Node] = []
    stack = [root]
    while stack:
        n = stack.pop()
        if n.type == "if_statement" and not _in_error_subtree(n):
            has_else = any(c.type == "else_clause" for c in n.children)
            if has_else:
                span_text = source[n.start_byte:n.end_byte]
                if b"\n#" not in span_text and not span_text.startswith(b"#"):
                    eligible_ifs.append(n)
        stack.extend(reversed(n.children))

    n_eligible = len(eligible_ifs)
    if n_eligible == 0:
        return TransformResult(code=code, n_eligible=0, n_applied=0)

    rng = random.Random(seed)
    k = max(1, int(round(p * n_eligible))) if p > 0 else 0
    selected_raw = rng.sample(eligible_ifs, k)
    selected = _filter_disjoint_nodes(selected_raw)

    edits: List[Tuple[int, int, bytes]] = []
    for node in selected:
        cond_node = node.child_by_field_name("condition")
        csq_node = node.child_by_field_name("consequence")
        else_clause = next((c for c in node.children if c.type == "else_clause"), None)
        if not cond_node or not csq_node or not else_clause:
            continue

        alt_node = next((c for c in else_clause.children if c.type != "else"), None)
        if not alt_node:
            continue

        cond_text = source[cond_node.start_byte:cond_node.end_byte].decode("utf-8", errors="replace").strip()
        if cond_text.startswith("(") and cond_text.endswith(")"):
            neg_cond = f"!{cond_text}"
        else:
            neg_cond = f"!({cond_text})"

        csq_text = source[csq_node.start_byte:csq_node.end_byte].decode("utf-8", errors="replace").strip()
        if csq_node.type != "compound_statement":
            new_alt = f"{{ {csq_text} }}"
        else:
            new_alt = csq_text

        alt_text = source[alt_node.start_byte:alt_node.end_byte].decode("utf-8", errors="replace").strip()
        if alt_node.type != "compound_statement":
            new_csq = f"{{ {alt_text} }}"
        else:
            new_csq = alt_text

        repl = f"if ({neg_cond}) {new_csq} else {new_alt}"
        edits.append((node.start_byte, node.end_byte, repl.encode("utf-8")))

    new_source = _apply_byte_edits(source, edits)
    return TransformResult(code=new_source.decode("utf-8", errors="replace"), n_eligible=n_eligible, n_applied=len(edits))


# --- T7: Combined Pipeline ----------------------------------------------------------------------


def t7_combined(code: str, lang: str, p: float = 1.0, seed: int = 0) -> TransformResult:
    """T7: Sequential pipeline T2 -> T3 -> T4 -> T5 with reparsing between stages."""
    file_sha = hashlib.sha256(code.encode("utf-8")).hexdigest()
    pipeline = [
        ("T2", t2_for_while),
        ("T3", t3_reorder_stmts),
        ("T4", t4_operators),
        ("T5", t5_dead_code),
    ]

    curr_code = code
    total_eligible = 0
    total_applied = 0

    for name, fn in pipeline:
        stage_seed = derive_seed(seed, file_sha, name, p)
        res = fn(curr_code, lang, p=p, seed=stage_seed)
        curr_code = res.code
        total_eligible += res.n_eligible
        total_applied += res.n_applied

    return TransformResult(code=curr_code, n_eligible=total_eligible, n_applied=total_applied)


# --- Registry and Dispatcher --------------------------------------------------------------------


TRANSFORMS: Dict[str, Callable[..., TransformResult]] = {
    "T0": t0_identity,
    "T1": t1_rename_identifiers,
    "T2": t2_for_while,
    "T3": t3_reorder_stmts,
    "T4": t4_operators,
    "T5": t5_dead_code,
    "T6": t6_invert_if,
    "T7": t7_combined,
}


def apply_condition(code: str, lang: str, condition: str, seed: int = 42) -> TransformResult:
    """Apply a named condition (e.g. 'T0', 'T1', 'T7@0.5', 'T7@1.0') to code."""
    if "@" in condition:
        name, intensity_str = condition.split("@", 1)
        intensity = float(intensity_str)
    else:
        name = condition
        intensity = 1.0

    if name not in TRANSFORMS:
        raise ValueError(f"unknown transformation condition {name!r} (available: {list(TRANSFORMS.keys())})")

    fn = TRANSFORMS[name]
    return fn(code, lang, p=intensity, seed=seed)
