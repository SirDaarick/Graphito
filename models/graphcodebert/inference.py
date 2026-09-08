from pathlib import Path
from typing import Optional

import torch
import torch.nn.functional as F
from transformers import RobertaTokenizer, RobertaModel

from models.graphcodebert.config import GraphCodeBERTConfig
from models.graphcodebert.parser import DFGExtractor, DFGResult


class GraphCodeBERTInference:

    def __init__(
        self,
        config: Optional[GraphCodeBERTConfig] = None,
        device: Optional[torch.device] = None,
    ):
        self.config = config or GraphCodeBERTConfig()
        self.device = device or torch.device(
            "cuda" if torch.cuda.is_available() else "cpu"
        )
        self._dfg_extractor = DFGExtractor()

        self.tokenizer = RobertaTokenizer.from_pretrained(
            self.config.model_name, cache_dir=str(self.config.cache_dir)
        )
        self.encoder = RobertaModel.from_pretrained(
            self.config.model_name, cache_dir=str(self.config.cache_dir)
        )
        self.encoder.to(self.device)
        self.encoder.eval()

    def predict(self, file_path: Path) -> dict:
        code_bytes = file_path.read_bytes()
        code = code_bytes.decode("utf-8", errors="replace")
        return self.predict_code(code, self._dfg_extractor._detect_language(file_path))

    def predict_code(self, code: str, language: str = "c") -> dict:
        token_count = len(self.tokenizer.encode(code, add_special_tokens=True))
        if token_count < self.config.max_code_tokens:
            result = self._dfg_extractor.parse_code(code, language)
            return self._embed(result, language)

        return self._embed_chunked(code, language)

    def _embed_chunked(self, code: str, language: str) -> dict:
        lines = code.split("\n")
        chunks: list[str] = []
        current_chunk: list[str] = []
        current_tokens = 0

        for line in lines:
            line_tokens = len(self.tokenizer.encode(line, add_special_tokens=False))
            if current_tokens + line_tokens >= self.config.max_code_tokens and current_chunk:
                chunks.append("\n".join(current_chunk))
                overlap = max(0, len(current_chunk) // 4)
                current_chunk = current_chunk[-overlap:] if overlap else []
                current_tokens = sum(len(self.tokenizer.encode(l, add_special_tokens=False))
                                     for l in current_chunk)
            current_chunk.append(line)
            current_tokens += line_tokens

        if current_chunk:
            chunks.append("\n".join(current_chunk))

        if not chunks:
            chunks = [code]

        chunk_embeddings: list[list[float]] = []
        total_code_tokens = 0
        total_dfg_nodes = 0
        for chunk in chunks:
            result = self._dfg_extractor.parse_code(chunk, language)
            if not result.success or len(result.code_tokens) == 0:
                continue
            emb = self._embed(result, language)
            chunk_embeddings.append(emb["embedding"])
            total_code_tokens += emb["code_tokens_count"]
            total_dfg_nodes += emb["dfg_node_count"]

        if not chunk_embeddings:
            result = self._dfg_extractor.parse_code(code[:2000], language)
            emb = self._embed(result, language)
            return emb

        import numpy as np
        avg = np.mean(chunk_embeddings, axis=0).tolist()

        return {
            "embedding": avg,
            "language": language,
            "code_tokens_count": total_code_tokens,
            "dfg_node_count": total_dfg_nodes,
            "success": True,
            "used_graph": True,
            "chunks": len(chunk_embeddings),
        }

    def _embed(self, dfg_result: DFGResult, language: str) -> dict:
        code_tokens = dfg_result.code_tokens
        edges = dfg_result.dfg_edges

        use_graph = dfg_result.success and len(code_tokens) > 0 and len(edges) > 0

        input_ids, position_idx, graph_mask_4d = self._build_graph_aware_input(
            code_tokens, edges if use_graph else []
        )

        code_len = (input_ids[0] != self.tokenizer.pad_token_id).sum().item()
        num_dfg = (input_ids[0] == self.tokenizer.unk_token_id).sum().item()
        real_code_len = code_len - num_dfg

        token_embeds = self.encoder.embeddings.word_embeddings(
            input_ids.to(self.device)
        )
        pos_embeds = self.encoder.embeddings.position_embeddings(
            position_idx.to(self.device)
        )

        if use_graph:
            token_embeds = self._inject_dfg_embeddings(
                token_embeds, code_tokens, edges,
                code_len=real_code_len, num_dfg=num_dfg,
            )

        embeds = token_embeds + pos_embeds
        embeds = self.encoder.embeddings.LayerNorm(embeds)
        embeds = self.encoder.embeddings.dropout(embeds)

        with torch.no_grad():
            encoder_out = self.encoder.encoder(
                hidden_states=embeds,
                attention_mask=graph_mask_4d.to(self.device),
            )
            cls_embedding = encoder_out.last_hidden_state[:, 0, :].squeeze(0)

        return {
            "embedding": cls_embedding.cpu().tolist(),
            "language": language,
            "code_tokens_count": len(code_tokens),
            "dfg_node_count": len(edges) if use_graph else 0,
            "success": dfg_result.success,
            "used_graph": use_graph,
        }

    def _build_graph_aware_input(
        self, code_tokens: list[str], dfg_edges: list
    ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:

        code_str = " ".join(code_tokens)
        tokenized = self.tokenizer(
            code_str,
            return_tensors="pt",
            truncation=True,
            max_length=self.config.max_code_tokens,
            return_attention_mask=False,
            return_token_type_ids=False,
        )
        code_ids = tokenized["input_ids"][0]  # includes [CLS] and [SEP]
        code_len = code_ids.size(0)

        max_len = self.config.max_position_embeddings
        if code_len >= max_len:
            code_ids = code_ids[:max_len]
            code_len = code_ids.size(0)
            num_dfg = 0
        else:
            dfg_node_limit = max_len - code_len
            used_edges = dfg_edges[:dfg_node_limit]
            num_dfg = len(used_edges)

        total_len = code_len + num_dfg
        input_ids = torch.full((max_len,), self.tokenizer.pad_token_id, dtype=torch.long)
        position_idx = torch.full((max_len,), 1, dtype=torch.long)

        input_ids[:code_len] = code_ids
        pos_start = 2
        position_idx[0] = pos_start
        position_idx[1 : code_len - 1] = torch.arange(pos_start + 1, pos_start + code_len - 1)
        position_idx[code_len - 1] = pos_start + code_len - 1

        for d in range(num_dfg):
            dfg_pos = code_len + d
            input_ids[dfg_pos] = self.tokenizer.unk_token_id
            dfg_pos_id = pos_start + code_len + d
            if dfg_pos_id < max_len:
                position_idx[dfg_pos] = dfg_pos_id

        attn_mask_2d = torch.zeros((total_len, total_len), dtype=torch.bool)

        for i in range(code_len):
            attn_mask_2d[i, :code_len] = True

        for d in range(num_dfg):
            dfg_pos = code_len + d
            attn_mask_2d[dfg_pos, :code_len] = True
            attn_mask_2d[:code_len, dfg_pos] = True

        if num_dfg > 0:
            code_to_subtoken: dict[int, list[int]] = {}
            subtoken_idx = 1
            for ci in range(len(code_tokens)):
                tok_text = code_tokens[ci]
                sub_ids = self.tokenizer.encode(tok_text, add_special_tokens=False)
                code_to_subtoken[ci] = list(range(subtoken_idx, subtoken_idx + len(sub_ids)))
                subtoken_idx += len(sub_ids)
                if subtoken_idx >= code_len - 1:
                    break

            for d in range(num_dfg):
                edge = dfg_edges[d]
                dfg_pos = code_len + d

                relevant_subtokens: set[int] = set()
                for src_idx in edge.source_indices:
                    relevant_subtokens.update(code_to_subtoken.get(src_idx, []))
                relevant_subtokens.update(code_to_subtoken.get(edge.target_index, []))

                if not relevant_subtokens:
                    relevant_subtokens = {1}

                for st in relevant_subtokens:
                    if st < code_len:
                        attn_mask_2d[dfg_pos, st] = True
                        attn_mask_2d[st, dfg_pos] = True

            for d1 in range(num_dfg):
                for d2 in range(num_dfg):
                    if d1 != d2:
                        attn_mask_2d[code_len + d1, code_len + d2] = True

        graph_mask_4d = torch.zeros((1, 1, max_len, max_len), dtype=torch.bool)
        graph_mask_4d[0, 0, :total_len, :total_len] = attn_mask_2d

        input_ids = input_ids.unsqueeze(0)
        position_idx = position_idx.unsqueeze(0)

        return input_ids, position_idx, graph_mask_4d

    def _inject_dfg_embeddings(
        self,
        token_embeds: torch.Tensor,
        code_tokens: list[str],
        dfg_edges: list,
        code_len: int,
        num_dfg: int,
    ) -> torch.Tensor:

        if num_dfg == 0:
            return token_embeds

        max_subtoken = (token_embeds.shape[1] if code_len == 0 else code_len)

        code_to_subtoken: dict[int, list[int]] = {}
        subtoken_idx = 1  # after [CLS]
        code_len_input = len(code_tokens)
        for ci in range(code_len_input):
            tok_text = code_tokens[ci]
            sub_ids = self.tokenizer.encode(tok_text, add_special_tokens=False)
            code_to_subtoken[ci] = list(range(subtoken_idx, subtoken_idx + len(sub_ids)))
            subtoken_idx += len(sub_ids)
            if subtoken_idx >= max_subtoken - 1:
                break

        for d in range(min(num_dfg, len(dfg_edges))):
            edge = dfg_edges[d]
            dfg_pos = code_len + d

            relevant_subtokens: set[int] = set()
            for src_idx in edge.source_indices:
                relevant_subtokens.update(code_to_subtoken.get(src_idx, []))
            target_subtokens = code_to_subtoken.get(edge.target_index, [])
            relevant_subtokens.update(target_subtokens)

            if not relevant_subtokens:
                relevant_subtokens = {1}

            valid_st = [s for s in relevant_subtokens if s < dfg_pos]
            if valid_st:
                avg_token = token_embeds[0, valid_st, :].mean(dim=0)
                token_embeds[0, dfg_pos, :] = avg_token

        return token_embeds
