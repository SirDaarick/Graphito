import hashlib
import math
from typing import Dict, List, Any
from app.domain.ports.inference_port import InferencePort


class StubInferenceEngine(InferencePort):
    """
    Motor de inferencia simulado (Stub).
    Produce embeddings deterministas y probabilidades reproducibles para desarrollo y pruebas,
    sin requerir pesos de PyTorch ni GPUs.
    """

    async def extract_semantic_embedding(self, code: str, lang: str = "c") -> List[float]:
        # Generar un vector unitario de 768 dimensiones derivado del hash del código normalizado
        code_norm = "".join(code.split())
        h = hashlib.sha256(code_norm.encode("utf-8")).digest()
        
        # Expandir bytes a 768 floats pseudo-aleatorios deterministas
        raw_vals = []
        for i in range(768):
            byte_val = h[i % len(h)]
            # Oscilación determinista
            raw_vals.append(math.sin((i + 1) * byte_val))
            
        # Normalizar vector a norma L2 = 1.0 (para similitud del coseno)
        norm = math.sqrt(sum(x * x for x in raw_vals)) or 1.0
        return [round(x / norm, 6) for x in raw_vals]

    async def predict_synthetic_prob(self, code: str) -> float:
        # Heurística simple para pruebas: comentarios típicos de LLMs o longitud de indentación
        code_lower = code.lower()
        score = 0.25
        if "here is" in code_lower or "solution" in code_lower or "include <stdio.h>" in code_lower:
            score += 0.35
        if "// autor:" in code_lower or "// estudiante" in code_lower:
            score -= 0.15
        return max(0.01, min(0.99, round(score, 4)))

    async def generate_hybrid_embedding(self, code: str, lang: str = "c") -> List[float]:
        semantic = await self.extract_semantic_embedding(code, lang)
        ai_prob = await self.predict_synthetic_prob(code)
        # Vector híbrido de 769 dimensiones (768 semántico + 1 estilometría)
        return semantic + [ai_prob]

    def compute_decision(
        self,
        semantic_similarity: float,
        synthetic_prob: float,
        threshold_sem: float = 0.85,
        threshold_ai: float = 0.70,
    ) -> Dict[str, Any]:
        """
        Cálculo del dictamen de integridad docente e indicadores de discrepancia.
        """
        # Métrica de discrepancia: penaliza si la similitud lógica es alta y la probabilidad IA es alta
        discrepancia = round(semantic_similarity * synthetic_prob, 4)
        indicadores = []

        if semantic_similarity >= threshold_sem and synthetic_prob >= threshold_ai:
            dictamen = "SOSPECHA_IA"
            indicadores.append({
                "tipo_alerta": "DISCREPANCIA_ESTILOMETRICA",
                "descripcion": f"Alta similitud funcional ({semantic_similarity*100:.1f}%) con alta probabilidad de generación por IA ({synthetic_prob*100:.1f}%).",
                "severidad": "ALTA",
            })
        elif semantic_similarity >= threshold_sem:
            dictamen = "PLAGIO_PROBABLE"
            indicadores.append({
                "tipo_alerta": "SIMILITUD_LOGICA_ALTA",
                "descripcion": f"Estructura algorítmica casi idéntica a la referencia ({semantic_similarity*100:.1f}%).",
                "severidad": "MEDIA",
            })
        elif synthetic_prob >= threshold_ai:
            dictamen = "SOSPECHA_IA"
            indicadores.append({
                "tipo_alerta": "PATRON_SINTETICO",
                "descripcion": f"Estilometría con alta probabilidad de redacción por LLM ({synthetic_prob*100:.1f}%).",
                "severidad": "MEDIA",
            })
        else:
            dictamen = "INTEGRO"
            indicadores.append({
                "tipo_alerta": "CONFORMIDAD_BASE",
                "descripcion": "No se detectaron discrepancias críticas de integridad académica.",
                "severidad": "BAJA",
            })

        return {
            "discrepancia_score": discrepancia,
            "dictamen": dictamen,
            "indicadores": indicadores,
        }
