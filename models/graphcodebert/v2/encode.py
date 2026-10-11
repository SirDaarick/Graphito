"""Upstream GraphCodeBERT input features and graph-guided attention mask (`INPUT_VERSION = "v2"`).

A statement-for-statement port of `convert_examples_to_features` and `TextDataset.__getitem__` of
upstream `GraphCodeBERT/clonedetection/run.py` (vendored in `tests/reference/graphcodebert/`), for
one code input. The golden test compares every array against the vendored code.

Sequence layout (length `code_length + data_flow_length`)::

    [CLS] code subtokens [SEP] | DFG nodes (id unk, position 0) | padding (id pad, position 1)

Code positions start at `pad_token_id + 1` (2 for RoBERTa). Upstream behaviour kept on purpose,
recorded as deviations from the spec wording:

- GE1.3: the node budget is `code_length + data_flow_length - len(CLS + code + SEP)`, so a short
  file may carry more than `data_flow_length` nodes (upstream lends unused code slots to nodes).
- GE1.3: nodes whose token was cut from the code are *kept* (as upstream); they get no code
  attention. With sliding windows (design D7) a window never cuts code, so this only matters for
  direct callers that pass more code than the budget.
- GE3.3: a node with no aligned code inside the sequence and no parent gets an all-False mask
  row (upstream does not add self-attention). With an additive mask that row attends uniformly.
"""

from dataclasses import dataclass, field
from typing import Any, Protocol, Sequence

import numpy as np

from models.graphcodebert.v2.config import GCBV2Config

# `run.py` truncates code to `code_length + data_flow_length - K - min(n_dfg, data_flow_length)`,
# then to `[:512 - K]` (K = CLS + SEP + one position; recorded in the vendored SOURCE.md).
TRUNCATION_K = 3
UPSTREAM_MAX_CODE = 512


class Tokenizer(Protocol):
    """The subset of a Hugging Face (RoBERTa) tokenizer the builder uses."""

    cls_token: str
    sep_token: str
    cls_token_id: int
    sep_token_id: int
    pad_token_id: int
    unk_token_id: int

    def tokenize(self, text: str) -> list[str]: ...

    def convert_tokens_to_ids(self, tokens: list[str]) -> list[int]: ...


@dataclass(frozen=True)
class EncodedInput:
    """One upstream-format model input.

    `attn_mask` is the `[L, L]` boolean graph-guided mask (row attends column). `dfg_to_code`
    holds `(start, end)` sequence spans (CLS offset applied); `dfg_to_dfg` holds parent node
    indices relative to the first node. `truncated` is True when code subtokens or DFG nodes
    were cut.
    """

    source_tokens: list[str]
    input_ids: list[int]
    position_idx: list[int]
    dfg_to_code: list[tuple[int, int]]
    dfg_to_dfg: list[list[int]]
    attn_mask: np.ndarray = field(repr=False)
    n_code_subtokens: int
    n_code_kept: int
    n_dfg: int
    n_dfg_kept: int
    truncated: bool

    @property
    def node_index(self) -> int:
        """Sequence index of the first DFG node (= CLS + code + SEP)."""
        return self.n_code_kept + 2


def subtokenize(code_tokens: Sequence[str], tokenizer: Tokenizer) -> tuple[list[str], dict[int, tuple[int, int]]]:
    """Upstream subtokenization: `tokenize(x)` for the first token, `tokenize('@ ' + x)[1:]`
    otherwise. Returns the flat subtokens and `ori2cur_pos` (token index -> `(start, end)`
    subtoken range, with `ori2cur_pos[-1] == (0, 0)`)."""
    pieces = [tokenizer.tokenize("@ " + x)[1:] if idx != 0 else tokenizer.tokenize(x) for idx, x in enumerate(code_tokens)]
    ori2cur_pos: dict[int, tuple[int, int]] = {-1: (0, 0)}
    for i in range(len(pieces)):
        ori2cur_pos[i] = (ori2cur_pos[i - 1][1], ori2cur_pos[i - 1][1] + len(pieces[i]))
    return [y for x in pieces for y in x], ori2cur_pos


def code_budget(n_dfg: int, code_length: int, data_flow_length: int) -> int:
    """Upstream code subtoken budget for a DFG of `n_dfg` nodes."""
    return min(code_length + data_flow_length - TRUNCATION_K - min(n_dfg, data_flow_length), UPSTREAM_MAX_CODE - TRUNCATION_K)


def build_features(
    code_tokens: Sequence[str],
    dfg: Sequence[tuple],
    tokenizer: Tokenizer,
    code_length: int = 384,
    data_flow_length: int = 128,
) -> dict[str, Any]:
    """`convert_examples_to_features` for one input (no mask). Returns `source_tokens`,
    `input_ids`, `position_idx`, `dfg_to_code`, `dfg_to_dfg` plus truncation counts."""
    subtokens, ori2cur_pos = subtokenize(code_tokens, tokenizer)
    dfg = list(dfg)
    n_dfg = len(dfg)

    # truncating
    code = subtokens[: code_budget(n_dfg, code_length, data_flow_length)]
    source_tokens = [tokenizer.cls_token] + code + [tokenizer.sep_token]
    source_ids = list(tokenizer.convert_tokens_to_ids(source_tokens))
    position_idx = [i + tokenizer.pad_token_id + 1 for i in range(len(source_tokens))]
    dfg = dfg[: code_length + data_flow_length - len(source_tokens)]
    source_tokens += [x[0] for x in dfg]
    position_idx += [0 for _ in dfg]
    source_ids += [tokenizer.unk_token_id for _ in dfg]
    padding_length = code_length + data_flow_length - len(source_ids)
    position_idx += [tokenizer.pad_token_id] * padding_length
    source_ids += [tokenizer.pad_token_id] * padding_length

    # reindex
    reverse_index = {x[1]: idx for idx, x in enumerate(dfg)}
    dfg = [x[:-1] + ([reverse_index[i] for i in x[-1] if i in reverse_index],) for x in dfg]
    dfg_to_dfg = [x[-1] for x in dfg]
    length = 1  # len([tokenizer.cls_token])
    dfg_to_code = [(ori2cur_pos[x[1]][0] + length, ori2cur_pos[x[1]][1] + length) for x in dfg]
    return {
        "source_tokens": source_tokens,
        "input_ids": source_ids,
        "position_idx": position_idx,
        "dfg_to_code": dfg_to_code,
        "dfg_to_dfg": dfg_to_dfg,
        "n_code_subtokens": len(subtokens),
        "n_code_kept": len(code),
        "n_dfg": n_dfg,
        "n_dfg_kept": len(dfg),
    }


def build_attention_mask(
    input_ids: Sequence[int],
    position_idx: Sequence[int],
    dfg_to_code: Sequence[tuple[int, int]],
    dfg_to_dfg: Sequence[Sequence[int]],
    special_ids: Sequence[int],
) -> np.ndarray:
    """`TextDataset.__getitem__` mask for one input: `[L, L]` bool, row attends column.

    `special_ids` are the CLS and SEP ids (upstream hard-codes RoBERTa's `[0, 2]`)."""
    size = len(position_idx)
    attn_mask = np.zeros((size, size), dtype=bool)
    # begin index of nodes and max length of input
    node_index = sum([i > 1 for i in position_idx])
    max_length = sum([i != 1 for i in position_idx])
    # sequence attends to sequence
    attn_mask[:node_index, :node_index] = True
    # special tokens attend to all tokens
    for idx, i in enumerate(input_ids):
        if i in special_ids:
            attn_mask[idx, :max_length] = True
    # nodes attend to the code tokens they are identified from
    for idx, (a, b) in enumerate(dfg_to_code):
        if a < node_index and b < node_index:
            attn_mask[idx + node_index, a:b] = True
            attn_mask[a:b, idx + node_index] = True
    # nodes attend to adjacent (parent) nodes
    for idx, nodes in enumerate(dfg_to_dfg):
        for a in nodes:
            if a + node_index < len(position_idx):
                attn_mask[idx + node_index, a + node_index] = True
    return attn_mask


def encode(
    code_tokens: Sequence[str],
    dfg: Sequence[tuple],
    tokenizer: Tokenizer,
    config: GCBV2Config | None = None,
) -> EncodedInput:
    """Upstream features and mask for `(code_tokens, dfg)` (DFG nodes as produced by
    `extract_dfg_v2`; pass `[]` for the no-DFG ablation)."""
    config = config or GCBV2Config()
    f = build_features(code_tokens, dfg, tokenizer, config.code_length, config.data_flow_length)
    mask = build_attention_mask(
        f["input_ids"], f["position_idx"], f["dfg_to_code"], f["dfg_to_dfg"], (tokenizer.cls_token_id, tokenizer.sep_token_id)
    )
    truncated = f["n_code_kept"] < f["n_code_subtokens"] or f["n_dfg_kept"] < f["n_dfg"]
    return EncodedInput(
        source_tokens=f["source_tokens"],
        input_ids=f["input_ids"],
        position_idx=f["position_idx"],
        dfg_to_code=f["dfg_to_code"],
        dfg_to_dfg=f["dfg_to_dfg"],
        attn_mask=mask,
        n_code_subtokens=f["n_code_subtokens"],
        n_code_kept=f["n_code_kept"],
        n_dfg=f["n_dfg"],
        n_dfg_kept=f["n_dfg_kept"],
        truncated=truncated,
    )
