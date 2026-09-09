import os
import sys
import logging
from typing import Dict, List, Any
from app.domain.ports.inference_port import InferencePort
from app.infrastructure.inference.stub_engine import StubInferenceEngine

logger = logging.getLogger(__name__)

# Asegurar que la ruta a models/ esté accesible
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)


class RealBimodalInferenceEngine(InferencePort):
    """
    Adaptador real que conecta los modelos de PyTorch:
    - Canal A: GraphCodeBERT con DFG
    - Canal B: CharCNN
    """

    def __init__(self):
        self.stub_fallback = StubInferenceEngine()
        self.gcb_engine = None
        self.charcnn_engine = None
        self._init_models()

    def _init_models(self):
        try:
            from models.graphcodebert.inference import GraphCodeBERTInference
            self.gcb_engine = GraphCodeBERTInference()
            logger.info("GraphCodeBERT engine inicializado exitosamente.")
        except Exception as e:
            logger.warning(f"No se pudo cargar GraphCodeBERT: {e}. Se usará fallback simulado.")

        try:
            from pathlib import Path
            from models.char_cnn.inference import CharCNNInference
            candidate_paths = [
                Path("/models/char_cnn/best_model.pth"),
                Path(project_root) / "models" / "char_cnn" / "best_model.pth",
            ]
            weights_path = next((p for p in candidate_paths if p.exists()), None)
            if weights_path:
                self.charcnn_engine = CharCNNInference(checkpoint_path=weights_path)
                logger.info(f"CharCNN engine inicializado con pesos en: {weights_path}")
            else:
                logger.warning("No se encontró best_model.pth para CharCNN. Se usará fallback simulado.")
        except Exception as e:
            logger.warning(f"No se pudo cargar CharCNN: {e}. Se usará fallback simulado.")

    async def extract_semantic_embedding(self, code: str, lang: str = "c") -> List[float]:
        if self.gcb_engine:
            try:
                res = self.gcb_engine.predict_code(code, language=lang)
                if res.get("success") and "embedding" in res:
                    return res["embedding"]
            except Exception as e:
                logger.error(f"Error en inferencia GraphCodeBERT: {e}")
        return await self.stub_fallback.extract_semantic_embedding(code, lang)

    async def predict_synthetic_prob(self, code: str) -> float:
        if self.charcnn_engine:
            try:
                res = self.charcnn_engine.predict_text(code)
                if isinstance(res, dict):
                    if "prob_sintetico" in res:
                        return float(res["prob_sintetico"])
                    elif "ai_probability" in res:
                        return float(res["ai_probability"])
                elif isinstance(res, (float, int)):
                    return float(res)
            except Exception as e:
                logger.error(f"Error en inferencia CharCNN: {e}")
        return await self.stub_fallback.predict_synthetic_prob(code)

    async def generate_hybrid_embedding(self, code: str, lang: str = "c") -> List[float]:
        semantic = await self.extract_semantic_embedding(code, lang)
        ai_prob = await self.predict_synthetic_prob(code)
        return semantic + [ai_prob]

    def compute_decision(
        self,
        semantic_similarity: float,
        synthetic_prob: float,
        threshold_sem: float = 0.85,
        threshold_ai: float = 0.70,
    ) -> Dict[str, Any]:
        return self.stub_fallback.compute_decision(
            semantic_similarity, synthetic_prob, threshold_sem, threshold_ai
        )
