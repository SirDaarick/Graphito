from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import tree_sitter as ts
import tree_sitter_c as tsc
import tree_sitter_cpp as tscpp


@dataclass
class DFGEdge:

    source_indices: list[int] = field(default_factory=list)
    target_index: int = 0
    relation: str = "computedFrom"


@dataclass
class DFGResult:

    code_tokens: list[str] = field(default_factory=list)
    dfg_edges: list[DFGEdge] = field(default_factory=list)
    index_to_code: dict[int, str] = field(default_factory=dict)
    success: bool = False


_LEAF_TYPES = frozenset(
    {
        "identifier",
        "number_literal",
        "string_literal",
        "char_literal",
        "primitive_type",
        "type_identifier",
        "sized_type_specifier",
        "struct_specifier",
        "enum_specifier",
        "true",
        "false",
        "null",
        "this",
        "preproc_include",
        "preproc_def",
        "preproc_function_def",
        "comment",
    }
)

_ASSIGNMENT_OPS = frozenset(
    {
        "=", "+=", "-=", "*=", "/=", "%=", "&=", "|=", "^=",
        "<<=", ">>=",
    }
)


def _is_leaf(node: ts.Node) -> bool:
    return node.type in _LEAF_TYPES or node.child_count == 0


def _collect_terminal_tokens(root: ts.Node, code_bytes: bytes) -> tuple[list[str], dict[int, str]]:
    tokens: list[str] = []
    index_to_code: dict[int, str] = {}

    def walk(node: ts.Node):
        if _is_leaf(node):
            token_text = node.text.decode("utf-8", errors="replace") if node.text else ""
            idx = len(tokens)
            tokens.append(token_text)
            start = node.start_byte
            end = node.end_byte
            index_to_code[(start, end)] = (idx, token_text)
        else:
            for child in node.children:
                walk(child)

    walk(root)
    return tokens, index_to_code


def _find_identifiers(node: ts.Node) -> list[ts.Node]:
    result: list[ts.Node] = []
    if node.type == "identifier":
        result.append(node)
    for child in node.children:
        result.extend(_find_identifiers(child))
    return result


def _extract_var_name(identifier_node: ts.Node) -> str:
    if identifier_node.text:
        return identifier_node.text.decode("utf-8", errors="replace")
    return ""


def _node_occurs_at(node: ts.Node, tokens: list[str], code_bytes: bytes) -> list[int]:
    name = _extract_var_name(node)
    indices: list[int] = []
    start = node.start_point
    for i, tok in enumerate(tokens):
        if tok.strip() == name:
            indices.append(i)
    return indices if indices else [0]


def DFG_c_cpp(root: ts.Node, code_bytes: bytes) -> tuple[list[str], list[DFGEdge]]:

    tokens = []
    indices_map: dict[tuple[int, int], int] = {}
    next_idx = 0

    def walk_leaves(node: ts.Node):
        nonlocal next_idx
        if _is_leaf(node):
            token_text = node.text.decode("utf-8", errors="replace") if node.text else ""
            tokens.append(token_text)
            start = node.start_byte
            end = node.end_byte
            indices_map[(start, end)] = next_idx
            next_idx += 1
        else:
            for child in node.children:
                walk_leaves(child)

    walk_leaves(root)

    function_registry: dict[str, dict] = {}

    def _collect_functions(node: ts.Node):
        if node.type == "function_definition":
            func_name = ""
            params: list[tuple[str, int]] = []
            for child in node.children:
                if child.type == "function_declarator":
                    for gc in child.children:
                        if gc.type == "identifier":
                            func_name = gc.text.decode("utf-8", errors="replace") if gc.text else ""
                        elif gc.type == "parameter_list":
                            for pc in gc.children:
                                if pc.type == "parameter_declaration":
                                    for ppc in pc.children:
                                        if ppc.type == "identifier":
                                            pname = ppc.text.decode("utf-8", errors="replace") if ppc.text else ""
                                            pidx = indices_map.get((ppc.start_byte, ppc.end_byte), -1)
                                            if pname and pidx >= 0:
                                                params.append((pname, pidx))
            if func_name:
                function_registry[func_name] = {"params": params, "returns": []}
        for child in node.children:
            _collect_functions(child)

    _collect_functions(root)

    edges: list[DFGEdge] = []

    def get_text(node: ts.Node) -> str:
        return node.text.decode("utf-8", errors="replace") if node.text else ""

    def get_idx(node: ts.Node) -> int:
        key = (node.start_byte, node.end_byte)
        return indices_map.get(key, -1)

    _EXPR_TYPES = frozenset({
        "binary_expression", "parenthesized_expression",
        "call_expression", "subscript_expression",
        "field_expression", "unary_expression",
        "conditional_expression", "cast_expression",
        "pointer_expression", "reference_expression",
        "sizeof_expression", "assignment_expression",
        "update_expression", "comma_expression",
        "new_expression", "delete_expression",
        "argument_list", "parameter_list",
    })

    def all_var_indices(node: ts.Node) -> list[int]:
        idxs: list[int] = []
        if node.type == "identifier":
            i = get_idx(node)
            if i >= 0:
                idxs.append(i)
        elif node.type == "field_expression":
            for child in node.children:
                if child.type in ("identifier", "field_expression"):
                    idxs.extend(all_var_indices(child))
        elif node.type == "subscript_expression":
            for child in node.children:
                if child.type == "identifier":
                    i = get_idx(child)
                    if i >= 0:
                        idxs.append(i)
                    break
        elif node.type == "call_expression":
            saw_name = False
            for child in node.children:
                if child.type == "identifier" and not saw_name:
                    saw_name = True
                    continue
                if child.type == "identifier":
                    i = get_idx(child)
                    if i >= 0:
                        idxs.append(i)
                elif child.type in _EXPR_TYPES:
                    idxs.extend(all_var_indices(child))
            return sorted(set(idxs))
        for child in node.children:
            if child.type == "identifier":
                i = get_idx(child)
                if i >= 0:
                    idxs.append(i)
            elif child.type in _EXPR_TYPES:
                idxs.extend(all_var_indices(child))
        return sorted(set(idxs))

    def _resolve_lhs_var_indices(node: ts.Node) -> tuple[Optional[str], list[int]]:

        if node.type == "identifier":
            i = get_idx(node)
            name = get_text(node)
            return name, [i] if i >= 0 else []
        elif node.type == "field_expression":
            base_name = None
            base_indices: list[int] = []
            for child in node.children:
                if child.type in ("identifier", "field_expression"):
                    n, idxs = _resolve_lhs_var_indices(child)
                    if n:
                        base_name = n
                    base_indices.extend(idxs)
            return base_name, base_indices
        elif node.type == "subscript_expression":
            for child in node.children:
                if child.type == "identifier":
                    i = get_idx(child)
                    name = get_text(child)
                    return name, [i] if i >= 0 else []
            return None, []
        return None, []

    def walk(node: ts.Node, states: dict[str, list[int]], current_func: str = "") -> dict[str, list[int]]:
        local = dict(states)

        if node.type == "function_definition":
            local = {}
            func_name = ""
            for child in node.children:
                if child.type == "function_declarator":
                    for gc in child.children:
                        if gc.type == "identifier":
                            func_name = get_text(gc)
                        elif gc.type == "parameter_list":
                            for pc in gc.children:
                                if pc.type == "parameter_declaration":
                                    for ppc in pc.children:
                                        if ppc.type == "identifier":
                                            vn = get_text(ppc)
                                            idx = get_idx(ppc)
                                            if idx >= 0:
                                                local[vn] = [idx]
            local = _walk_children(node, local, func_name)

        elif node.type == "declaration":
            has_init = False
            for child in node.children:
                if child.type == "init_declarator":
                    has_init = True
                    ident = None
                    rhs_idxs: list[int] = []
                    non_leaf_rhs: list[ts.Node] = []
                    for gc in child.children:
                        if gc.type == "identifier":
                            ident = gc
                    for gc in child.children:
                        if gc.type not in ("identifier", "=", ",") and gc.type not in _LEAF_TYPES:
                            rhs_idxs.extend(all_var_indices(gc))
                            non_leaf_rhs.append(gc)

                    if ident:
                        target_idx = get_idx(ident)
                        var_name = get_text(ident)
                        if rhs_idxs and target_idx >= 0:
                            edges.append(DFGEdge(
                                source_indices=sorted(set(rhs_idxs)),
                                target_index=target_idx,
                                relation="computedFrom",
                            ))
                        local[var_name] = [target_idx]

                    for rhs_node in non_leaf_rhs:
                        local = walk(rhs_node, local, current_func)

                    if ident and non_leaf_rhs:
                        for rhs_node in non_leaf_rhs:
                            if rhs_node.type == "call_expression":
                                called_func = ""
                                for gc in rhs_node.children:
                                    if gc.type == "identifier":
                                        called_func = get_text(gc)
                                        break
                                if called_func and called_func in function_registry:
                                    ret_vars = function_registry[called_func].get("returns", [])
                                    for rv in ret_vars:
                                        edges.append(DFGEdge(
                                            source_indices=[rv],
                                            target_index=get_idx(ident),
                                            relation="returnToCaller",
                                        ))
                elif child.type == "identifier":
                    var_name = get_text(child)
                    idx = get_idx(child)
                    if idx >= 0:
                        local[var_name] = [idx]
            for child in node.children:
                if child.type not in ("init_declarator", "identifier") and child.type not in _LEAF_TYPES:
                    local = walk(child, local, current_func)

        elif node.type == "assignment_expression":
            lhs_ident: Optional[ts.Node] = None
            lhs_is_field = False
            rhs_indices: list[int] = []
            op_type = None
            op_seen = False
            for child in node.children:
                if child.type in ("identifier", "field_expression", "subscript_expression") and not op_seen:
                    lhs_ident = child
                    lhs_is_field = (child.type in ("field_expression", "subscript_expression"))
                elif child.type in ("=", "+=", "-=", "*=", "/=", "%=",
                                    "&=", "|=", "^=", "<<=", ">>="):
                    op_seen = True
                    op_type = child.type
                elif op_seen:
                    rhs_indices.extend(all_var_indices(child))

            if lhs_ident and op_type:
                if lhs_is_field:
                    base_name, base_indices = _resolve_lhs_var_indices(lhs_ident)
                    if op_type != "=" and base_indices:
                        rhs_indices.extend(base_indices)
                    all_src = sorted(set(rhs_indices + base_indices))
                    if all_src:
                        target_idx = base_indices[0] if base_indices else -1
                        if target_idx >= 0:
                            edges.append(DFGEdge(
                                source_indices=all_src,
                                target_index=target_idx,
                                relation="computedFrom",
                            ))
                    if base_name and base_indices:
                        local[base_name] = base_indices
                else:
                    target_idx = get_idx(lhs_ident)
                    var_name = get_text(lhs_ident)
                    if op_type != "=":
                        lhs_idx = get_idx(lhs_ident)
                        if lhs_idx >= 0:
                            rhs_indices.append(lhs_idx)
                    if target_idx >= 0:
                        if rhs_indices:
                            edges.append(DFGEdge(
                                source_indices=sorted(set(rhs_indices)),
                                target_index=target_idx,
                                relation="computedFrom",
                            ))
                        local[var_name] = [target_idx]

            if lhs_ident and op_type:
                for child in node.children:
                    if child.type == "call_expression" and op_seen:
                        called_func = ""
                        for gc in child.children:
                            if gc.type == "identifier":
                                called_func = get_text(gc)
                                break
                        if called_func and called_func in function_registry:
                            ret_vars = function_registry[called_func].get("returns", [])
                            tgt = get_idx(lhs_ident) if not lhs_is_field else (
                                _resolve_lhs_var_indices(lhs_ident)[1][0] if _resolve_lhs_var_indices(lhs_ident)[1] else -1
                            )
                            for rv in ret_vars:
                                if tgt >= 0:
                                    edges.append(DFGEdge(
                                        source_indices=[rv],
                                        target_index=tgt,
                                        relation="returnToCaller",
                                    ))

        elif node.type == "call_expression":
            func_name = ""
            arg_indices: list[int] = []
            for child in node.children:
                if child.type == "identifier":
                    func_name = get_text(child)
                    break
            for child in node.children:
                if child.type == "argument_list":
                    arg_indices = all_var_indices(child)

            if func_name and func_name in function_registry:
                callee = function_registry[func_name]
                callee_params = callee.get("params", [])
                for i, (_, param_idx) in enumerate(callee_params):
                    if i < len(arg_indices) and param_idx >= 0:
                        edges.append(DFGEdge(
                            source_indices=[arg_indices[i]],
                            target_index=param_idx,
                            relation="argToParam",
                        ))

            local = _walk_children(node, local)

        elif node.type == "update_expression":
            for child in node.children:
                if child.type == "identifier":
                    idx = get_idx(child)
                    if idx >= 0:
                        edges.append(DFGEdge(
                            source_indices=[idx],
                            target_index=idx,
                            relation="computedFrom",
                        ))
                        local[get_text(child)] = [idx]

        elif node.type == "if_statement":
            branches: list[ts.Node] = []
            for child in node.children:
                if child.type in ("condition_clause", "compound_statement",
                                  "else_clause", "if_statement"):
                    branches.append(child)

            merged: dict[str, list[int]] = dict(local)
            for branch in branches:
                branch_states = dict(local)
                if branch.type == "condition_clause":
                    _ = walk(branch, branch_states, current_func)
                else:
                    branch_states = walk(branch, branch_states, current_func)
                for k, v in branch_states.items():
                    if k in merged:
                        merged[k] = sorted(set(merged[k] + v))
                    else:
                        merged[k] = v
            local = merged

        elif node.type == "for_statement":
            for _ in range(2):
                local = _walk_children(node, dict(local), current_func)

        elif node.type == "while_statement":
            for _ in range(2):
                local = _walk_children(node, dict(local), current_func)

        elif node.type == "parameter_declaration":
            for child in node.children:
                if child.type == "identifier":
                    var_name = get_text(child)
                    idx = get_idx(child)
                    if idx >= 0:
                        local[var_name] = [idx]

        elif node.type == "return_statement":
            ret_indices = all_var_indices(node)
            if ret_indices:
                var_name = tokens[ret_indices[0]].strip() if ret_indices[0] < len(tokens) else ""
                if var_name and var_name in local:
                    edges.append(DFGEdge(
                        source_indices=local[var_name],
                        target_index=ret_indices[0],
                        relation="comesFrom",
                    ))
                if current_func and current_func in function_registry:
                    if ret_indices[0] not in function_registry[current_func].get("returns", []):
                        function_registry[current_func].setdefault("returns", []).append(ret_indices[0])

        else:
            local = _walk_children(node, local, current_func)

        return local

    def _walk_children(node: ts.Node, states: dict[str, list[int]], func_name: str = "") -> dict[str, list[int]]:
        current = dict(states)
        for child in node.children:
            if child.type not in _LEAF_TYPES:
                current = walk(child, current, func_name)
        return current

    walk(root, {})

    return tokens, edges


class DFGExtractor:

    def __init__(self):
        self._c_lang = ts.Language(tsc.language())
        self._cpp_lang = ts.Language(tscpp.language())
        self._c_parser = ts.Parser(self._c_lang)
        self._cpp_parser = ts.Parser(self._cpp_lang)

    def _detect_language(self, file_path: Path) -> str:
        suffix = file_path.suffix.lower()
        if suffix in (".cpp", ".cc", ".cxx", ".hpp", ".hxx"):
            return "cpp"
        return "c"

    def parse_file(self, file_path: Path) -> DFGResult:
        language = self._detect_language(file_path)
        try:
            code_bytes = file_path.read_bytes()
            code_str = code_bytes.decode("utf-8", errors="replace")
            code_bytes = code_str.encode("utf-8")
        except (OSError, UnicodeDecodeError):
            return DFGResult(success=False)

        return self.parse_code(code_str, language)

    def parse_code(self, code: str, language: str = "c") -> DFGResult:
        code_bytes = code.encode("utf-8")

        parser = self._c_parser if language == "c" else self._cpp_parser

        try:
            tree = parser.parse(code_bytes)
        except Exception:
            return DFGResult(success=False)

        if tree.root_node is None or tree.root_node.has_error:
            tokens, index_to_code = _collect_terminal_tokens(
                parser.parse(code_bytes).root_node, code_bytes
            )
            return DFGResult(
                code_tokens=tokens,
                index_to_code=index_to_code,
                success=bool(tokens),
            )

        try:
            tokens, edges = DFG_c_cpp(tree.root_node, code_bytes)
        except Exception:
            return DFGResult(success=False)

        index_to_code: dict[int, str] = {}
        for i, tok in enumerate(tokens):
            index_to_code[i] = tok

        return DFGResult(
            code_tokens=tokens,
            dfg_edges=edges,
            index_to_code=index_to_code,
            success=True,
        )
