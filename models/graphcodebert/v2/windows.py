"""Sliding windows over the full-file subtoken sequence (GE5, design D7/D8).

The DFG is extracted once on the whole file; windows only slice the subtokens:

- a file whose subtokens fit the upstream dynamic budget (`code_budget`) gets exactly the single
  upstream input (`encode`), bit-identical to `run.py`;
- otherwise windows of `config.window_code_tokens` subtokens (382 by default, 384 with CLS/SEP)
  start at `0, stride, 2*stride, ...` (stride 191) and the last window ends at the last subtoken;
- more than `config.max_windows` windows are replaced by `max_windows` evenly spaced starts
  (first at 0, last ending at the file end) and the input is marked `truncated`.

Per window the nodes are those whose code span lies fully inside the window, in `idx` order, cut
to the upstream node budget (`code_length + data_flow_length - len(CLS + code + SEP)`, 128 for a
full window). Parents outside the window are dropped and the rest reindexed; spans are shifted by
`-start + 1` (CLS). Windowing never splits by lines.

The no-DFG ablation (`use_dfg=False`) plans the windows with the full DFG and then drops every
node, so both variants see the same code context (D8).
"""

from dataclasses import dataclass, field
from typing import Sequence

from models.graphcodebert.v2.config import GCBV2Config
from models.graphcodebert.v2.encode import (
    EncodedInput,
    Tokenizer,
    build_attention_mask,
    code_budget,
    encode,
    subtokenize,
)


@dataclass(frozen=True)
class WindowPlan:
    """Subtoken spans `[start, end)` of the model inputs of one file.

    `single` is True when the file fits the upstream budget and is encoded as one upstream input
    (its span is then `[0, n)` before upstream truncation). `capped` is True when the regular grid
    needed more than `max_windows` windows."""

    spans: list[tuple[int, int]]
    single: bool
    capped: bool

    @property
    def starts(self) -> list[int]:
        return [s for s, _ in self.spans]

    @property
    def n_windows(self) -> int:
        return len(self.spans)


def window_starts(n: int, window: int, stride: int, max_windows: int) -> tuple[list[int], bool]:
    """Window starts for `n` subtokens and whether the `max_windows` cap applied.

    Regular grid `0, stride, ...` while a window still leaves a tail, then a final start
    `n - window` so the last window ends at `n`. Above the cap: `max_windows` evenly spaced starts
    from 0 to `n - window`."""
    if n <= window:
        return [0], False
    last = n - window
    starts = list(range(0, last, stride))
    if starts[-1] != last:
        starts.append(last)
    if len(starts) <= max_windows:
        return starts, False
    if max_windows == 1:
        return [0], True
    return [round(i * last / (max_windows - 1)) for i in range(max_windows)], True


def plan_windows(n_subtokens: int, n_dfg: int, config: GCBV2Config) -> WindowPlan:
    """Plan the model inputs of a file with `n_subtokens` code subtokens and `n_dfg` DFG nodes."""
    if n_subtokens <= code_budget(n_dfg, config.code_length, config.data_flow_length):
        return WindowPlan(spans=[(0, n_subtokens)], single=True, capped=False)
    window = config.window_code_tokens
    starts, capped = window_starts(n_subtokens, window, config.window_stride, config.max_windows)
    return WindowPlan(spans=[(s, min(s + window, n_subtokens)) for s in starts], single=False, capped=capped)


@dataclass(frozen=True)
class WindowedInput:
    """The model inputs of one file plus the bookkeeping the result reports.

    `node_ids[w]` lists, for window `w`, the indices into the full-file DFG of the nodes placed
    in that window (in placement order)."""

    inputs: list[EncodedInput] = field(repr=False)
    plan: WindowPlan
    node_ids: list[list[int]]
    n_code_subtokens: int
    dfg_node_count: int
    truncated: bool

    @property
    def n_windows(self) -> int:
        return len(self.inputs)

    @property
    def dfg_nodes_used(self) -> int:
        """Distinct DFG nodes placed in at least one window."""
        return len(set().union(*map(set, self.node_ids))) if self.node_ids else 0


def encode_window(
    subtokens: Sequence[str],
    ori2cur_pos: dict[int, tuple[int, int]],
    dfg: Sequence[tuple],
    tokenizer: Tokenizer,
    config: GCBV2Config,
    start: int,
    end: int,
) -> tuple[EncodedInput, list[int]]:
    """Upstream-format input for the subtoken window `[start, end)` and the full-DFG indices of
    the nodes placed in it. Mirrors `build_features` with the window as the code."""
    total = config.code_length + config.data_flow_length
    code = list(subtokens[start:end])
    source_tokens = [tokenizer.cls_token] + code + [tokenizer.sep_token]
    source_ids = list(tokenizer.convert_tokens_to_ids(source_tokens))
    position_idx = [i + tokenizer.pad_token_id + 1 for i in range(len(source_tokens))]

    inside = [k for k, node in enumerate(dfg) if start <= ori2cur_pos[node[1]][0] and ori2cur_pos[node[1]][1] <= end]
    kept = inside[: max(0, total - len(source_tokens))]
    nodes = [dfg[k] for k in kept]
    source_tokens += [x[0] for x in nodes]
    position_idx += [0 for _ in nodes]
    source_ids += [tokenizer.unk_token_id for _ in nodes]
    padding_length = total - len(source_ids)
    position_idx += [tokenizer.pad_token_id] * padding_length
    source_ids += [tokenizer.pad_token_id] * padding_length

    reverse_index = {x[1]: idx for idx, x in enumerate(nodes)}
    dfg_to_dfg = [[reverse_index[i] for i in x[-1] if i in reverse_index] for x in nodes]
    shift = 1 - start  # CLS offset minus the window start
    dfg_to_code = [(ori2cur_pos[x[1]][0] + shift, ori2cur_pos[x[1]][1] + shift) for x in nodes]
    mask = build_attention_mask(
        source_ids, position_idx, dfg_to_code, dfg_to_dfg, (tokenizer.cls_token_id, tokenizer.sep_token_id)
    )
    enc = EncodedInput(
        source_tokens=source_tokens,
        input_ids=source_ids,
        position_idx=position_idx,
        dfg_to_code=dfg_to_code,
        dfg_to_dfg=dfg_to_dfg,
        attn_mask=mask,
        n_code_subtokens=len(code),
        n_code_kept=len(code),
        n_dfg=len(inside),
        n_dfg_kept=len(kept),
        truncated=len(kept) < len(inside),
    )
    return enc, kept


def build_windows(
    code_tokens: Sequence[str],
    dfg: Sequence[tuple],
    tokenizer: Tokenizer,
    config: GCBV2Config | None = None,
    use_dfg: bool | None = None,
) -> WindowedInput:
    """All model inputs of one file. `use_dfg` defaults to `config.use_dfg`; when False the
    windows are planned with the full DFG and every node is dropped (D8)."""
    config = config or GCBV2Config()
    use_dfg = config.use_dfg if use_dfg is None else use_dfg
    dfg = list(dfg)
    subtokens, ori2cur_pos = subtokenize(code_tokens, tokenizer)
    plan = plan_windows(len(subtokens), len(dfg), config)
    placed = dfg if use_dfg else []

    if plan.single:
        enc = encode(code_tokens, placed, tokenizer, config)
        return WindowedInput(
            inputs=[enc],
            plan=plan,
            node_ids=[list(range(enc.n_dfg_kept))],
            n_code_subtokens=len(subtokens),
            dfg_node_count=len(dfg),
            truncated=enc.truncated,
        )

    inputs, node_ids = [], []
    for start, end in plan.spans:
        enc, kept = encode_window(subtokens, ori2cur_pos, placed, tokenizer, config, start, end)
        inputs.append(enc)
        node_ids.append(kept)
    covered = set()
    for start, end in plan.spans:
        covered.update(range(start, end))
    truncated = plan.capped or len(covered) < len(subtokens) or any(e.truncated for e in inputs)
    return WindowedInput(
        inputs=inputs,
        plan=plan,
        node_ids=node_ids,
        n_code_subtokens=len(subtokens),
        dfg_node_count=len(dfg),
        truncated=truncated,
    )
