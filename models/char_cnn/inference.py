#!/usr/bin/env python3
"""
inference.py — Inferencia con CharCNN para detección de código sintético.

Modos de uso:
  1. Clasificación binaria: ¿es código sintético?
  2. Extracción de embedding: vector denso de autoría para fusión bimodal.

The facade dispatches on the checkpoint's version fields (`v2/checkpoint.py`): a checkpoint
without them runs the frozen legacy path (arch v1, preprocess v1) unchanged; one with
`arch_version == preproc_version == 2` runs the v2 model with windowed scoring. Both return the
legacy keys plus `score`, `abstained`, `n_windows`, `preproc_version` and `arch_version`.
"""

import argparse
import warnings
from pathlib import Path
from typing import Optional

import torch

from models.char_cnn.config import CharCNNConfig
from models.char_cnn.model import CharCNN
from models.char_cnn.preprocess import CharPreprocessor, MIN_NON_WS_CHARS
from models.char_cnn.v2.checkpoint import LEGACY_VERSION, checkpoint_versions, load_checkpoint, load_v2_model
from models.char_cnn.v2.config import CharCNNV2Config
from models.char_cnn.v2.scoring import predict_one

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# Placeholder values of the legacy numeric keys when the input is too short to score (D15).
_ABSTAIN_PLACEHOLDERS = {
    "prediction": "humano",
    "class_id": 0,
    "confidence": 0.95,
    "prob_humano": 0.95,
    "prob_sintetico": 0.05,
    "ai_probability": 0.05,
}


class CharCNNInference:

    def __init__(
        self,
        checkpoint_path: Optional[Path | str] = None,
        config: Optional[CharCNNConfig] = None,
        device: Optional[torch.device] = None,
        model_path: Optional[Path | str] = None,
    ):
        self.device = device or DEVICE
        chosen_path = checkpoint_path or model_path or Path("models/char_cnn/best_model.pth")
        chosen_path = Path(chosen_path)

        self.checkpoint = load_checkpoint(chosen_path, map_location=self.device)
        self.arch_version, self.preproc_version = checkpoint_versions(self.checkpoint.get("config") or {})
        self.class_names = {0: "humano", 1: "sintético"}
        if self.arch_version == LEGACY_VERSION:
            self._init_legacy(config)
        else:
            self._init_v2(config)

    def _init_legacy(self, config: Optional[CharCNNConfig]) -> None:
        # Frozen legacy constructor body (arch v1, preprocess v1); do not change numerics here.
        ckpt_config = self.checkpoint.get("config", {})
        self.config = config or CharCNNConfig()

        if ckpt_config.get("alphabet"):
            self.config.alphabet = ckpt_config["alphabet"]
        if ckpt_config.get("seq_length"):
            self.config.seq_length = ckpt_config["seq_length"]
        # Checkpoints saved before this field existed were trained on legacy "trim" input.
        self.config.whitespace_mode = ckpt_config.get("whitespace_mode", "trim")

        self.preprocessor = CharPreprocessor(self.config)
        self.config.vocab_size = self.preprocessor.vocab_size

        state_dict = self.checkpoint["model_state_dict"]
        if "convs.0.0.weight" in state_dict:
            from models.char_cnn.model import ParallelCharCNN
            self.model = ParallelCharCNN(self.config).to(self.device)
        else:
            self.model = CharCNN(self.config).to(self.device)

        self.model.load_state_dict(state_dict)
        self.model.eval()

        dummy = torch.randint(0, self.config.vocab_size, (1, self.config.seq_length))
        dummy = dummy.to(self.device)
        self.model(dummy)

    def _init_v2(self, config: object) -> None:
        # The checkpoint's own config defines the model; a caller-supplied one cannot apply.
        if config is not None:
            warnings.warn(
                "CharCNNInference: the `config` argument is ignored for v2 checkpoints "
                "(the checkpoint config defines the model)",
                UserWarning,
                stacklevel=3,
            )
        self.model = load_v2_model(self.checkpoint, self.device)
        self.config: CharCNNV2Config = self.model.config
        self.preprocessor = None

    def predict(self, file_path: Path | str) -> dict:
        # Si se pasa un string que no es ruta existente, procesar como texto directamente
        if isinstance(file_path, str) and not Path(file_path).exists():
            return self.predict_text(file_path)

        p = Path(file_path)
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except (OSError, UnicodeDecodeError):
            text = ""

        res = self.predict_text(text)
        res["file"] = str(p)
        return res

    def predict_text(self, text: str, pad: bool = False) -> dict:
        # `pad` only applies to the legacy path; v2 is padding-invariant.
        if self.arch_version != LEGACY_VERSION:
            return self._predict_text_v2(text)
        res = self._predict_text_legacy(text, pad=pad)
        abstained = res["insufficient_length"]
        res.update(
            score=None if abstained else res["prob_sintetico"],
            abstained=abstained,
            n_windows=1,
            preproc_version=self.preproc_version,
            arch_version=self.arch_version,
        )
        return res

    def _predict_text_legacy(self, text: str, pad: bool = False) -> dict:
        # Frozen legacy predict_text body (keys and numerics unchanged).
        # Salvaguarda pericial de inferencia: fragmentos triviales (< MIN_NON_WS_CHARS caracteres
        # no-espacio, sin contar comentarios) carecen de densidad estadística de n-gramas de
        # autoría y degeneran a falso positivo. El modelo recibe el texto original (sin recortar).
        non_ws_len = self.preprocessor.effective_length(text)
        if non_ws_len < MIN_NON_WS_CHARS:
            encoded = self.preprocessor.encode(text, pad=pad)
            input_tensor = torch.tensor(encoded, dtype=torch.long).unsqueeze(0).to(self.device)
            with torch.no_grad():
                _, embedding = self.model(input_tensor, return_embedding=True)
            return {
                "prediction": "humano",
                "class_id": 0,
                "confidence": 0.95,
                "prob_humano": 0.95,
                "prob_sintetico": 0.05,
                "ai_probability": 0.05,
                "embedding": embedding.squeeze(0).cpu().tolist(),
                "insufficient_length": True,
            }

        encoded = self.preprocessor.encode(text, pad=pad)
        input_tensor = torch.tensor(encoded, dtype=torch.long).unsqueeze(0).to(self.device)

        with torch.no_grad():
            logits, embedding = self.model(input_tensor, return_embedding=True)
            probs = torch.softmax(logits, dim=1)
            pred_class = logits.argmax(dim=1).item()
            confidence = probs[0, pred_class].item()
            p_synth = round(probs[0, 1].item(), 6)

        return {
            "prediction": self.class_names[pred_class],
            "class_id": pred_class,
            "confidence": round(confidence, 6),
            "prob_humano": round(probs[0, 0].item(), 6),
            "prob_sintetico": p_synth,
            "ai_probability": p_synth,
            "embedding": embedding.squeeze(0).cpu().tolist(),
            "insufficient_length": False,
        }

    def _predict_text_v2(self, text: str) -> dict:
        out = predict_one(self.model, text, self.device, self.config)
        versions = {"preproc_version": self.preproc_version, "arch_version": self.arch_version}
        if out["abstained"]:
            # Placeholders keep `float(res["prob_sintetico"])` working for existing consumers;
            # `score=None` / `abstained=True` carry the real outcome. An empty normalized text
            # was scored as `[UNK]` only to keep shapes valid, so its embedding is zeroed.
            embedding = [0.0] * len(out["embedding"]) if out["empty"] else out["embedding"].tolist()
            return {
                **_ABSTAIN_PLACEHOLDERS,
                "embedding": embedding,
                "insufficient_length": True,
                "score": None,
                "abstained": True,
                "n_windows": 0 if out["empty"] else out["n_windows"],
                **versions,
            }

        probs = out["probs"]
        pred_class = int(probs.argmax())
        p_synth = round(float(probs[1]), 6)
        return {
            "prediction": self.class_names[pred_class],
            "class_id": pred_class,
            "confidence": round(float(probs[pred_class]), 6),
            "prob_humano": round(float(probs[0]), 6),
            "prob_sintetico": p_synth,
            "ai_probability": p_synth,
            "embedding": out["embedding"].tolist(),
            "insufficient_length": False,
            "score": p_synth,
            "abstained": False,
            "n_windows": out["n_windows"],
            **versions,
        }


def main() -> None:
    parser = argparse.ArgumentParser(description="Inferencia CharCNN — Graphito")
    parser.add_argument("checkpoint", type=Path, help="Ruta al .pth del modelo entrenado")
    parser.add_argument("file", type=Path, nargs="?", help="Archivo .c/.cpp a analizar")
    parser.add_argument("--text", type=str, default=None, help="Texto de código a analizar (stdin si no se especifica archivo)")
    parser.add_argument("--device", type=str, default=None)
    args = parser.parse_args()

    if args.device:
        global DEVICE
        DEVICE = torch.device(args.device)

    engine = CharCNNInference(args.checkpoint)

    if args.file:
        result = engine.predict(args.file)
    elif args.text:
        result = engine.predict_text(args.text)
    else:
        import sys
        text = sys.stdin.read()
        if not text.strip():
            print("Error: proporciona un archivo, --text, o redirige código por stdin", file=sys.stderr)
            sys.exit(1)
        result = engine.predict_text(text)

    import json
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
