#!/usr/bin/env python3
"""
inference.py — Inferencia con CharCNN para detección de código sintético.

Modos de uso:
  1. Clasificación binaria: ¿es código sintético?
  2. Extracción de embedding: vector denso de autoría para fusión bimodal.
"""

import argparse
from pathlib import Path
from typing import Optional

import torch

from models.char_cnn.config import CharCNNConfig
from models.char_cnn.model import CharCNN
from models.char_cnn.preprocess import CharPreprocessor, MIN_NON_WS_CHARS

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")


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

        self.checkpoint = torch.load(
            chosen_path, map_location=self.device, weights_only=False,
        )

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

        self.class_names = {0: "humano", 1: "sintético"}

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
