#!/usr/bin/env python3
"""
test_char_cnn_robustness.py - Suite de pruebas de robustez y generalización para CharCNN.

Pruebas:
  1. Evaluación del Test Set (13 subproblemas 100% no vistos en train/val).
  2. Invarianza ante formateo/indentación (el clasificador no debe depender de espacios).
  3. Invarianza ante comentarios (eliminar o agregar comentarios no debe alterar la clasificación).
  4. Fusión Bimodal no penalizante (verificación matemática de que el estilo no diluye el coseno semántico).
"""

import json
from pathlib import Path
import torch
import numpy as np

from models.char_cnn.config import CharCNNConfig
from models.char_cnn.dataset import CharCNNDataset
from models.char_cnn.inference import CharCNNInference
from models.char_cnn.preprocess import CharPreprocessor
from models.char_cnn.train import evaluate, compute_metrics


def test_unseen_subproblems_generalization():
    print("\n" + "=" * 60)
    print("TEST 1: Generalización sobre Subproblemas No Vistos (Test Set)")
    print("=" * 60)

    checkpoint_path = Path("models/char_cnn/best_model.pth")
    assert checkpoint_path.exists(), f"No existe {checkpoint_path}"

    infer = CharCNNInference(checkpoint_path)
    config = infer.config
    preprocessor = infer.preprocessor

    manifest_path = Path("models/char_cnn/dataset_manifest.json")
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    test_samples = manifest["splits"]["test"]
    print(f"Total muestras de test: {len(test_samples)}")
    print(f"Subproblemas de test: {manifest['subproblems']['test']}")

    y_true = []
    y_pred = []
    probs = []

    for s in test_samples:
        fp = Path(s["file_path"])
        label = s["label"]
        res = infer.predict(fp)
        y_true.append(label)
        y_pred.append(res["class_id"])
        probs.append(res["prob_sintetico"])

    metrics = compute_metrics(y_true, y_pred)
    print(f"Accuracy:  {metrics['accuracy']:.4f}")
    print(f"Precision: {metrics['precision']:.4f}")
    print(f"Recall:    {metrics['recall']:.4f}")
    print(f"F1-Score:  {metrics['f1']:.4f}")

    assert metrics["accuracy"] >= 0.80, f"Accuracy {metrics['accuracy']} no cumple RNF-04 (>= 0.80)"
    print("✅ TEST 1 PASÓ: Cumple con creces el RNF-04 sobre problemas completamente no vistos.")
    return metrics


def test_formatting_invariance():
    print("\n" + "=" * 60)
    print("TEST 2: Invarianza ante Formateo / Indentación")
    print("=" * 60)

    infer = CharCNNInference(Path("models/char_cnn/best_model.pth"))

    sample_human = """
#include <stdio.h>
int main(){
int a,b;
scanf("%d%d",&a,&b);
if(a>b){printf("Mayor: %d",a);}
else{printf("Mayor: %d",b);}
return 0;
}
"""

    sample_formatted = """
#include <stdio.h>

int main() {
    int a, b;
    scanf("%d %d", &a, &b);

    if (a > b) {
        printf("Mayor: %d\n", a);
    } else {
        printf("Mayor: %d\n", b);
    }

    return 0;
}
"""

    res_raw = infer.predict_text(sample_human)
    res_fmt = infer.predict_text(sample_formatted)

    print(f"Código crudo:     Pred={res_raw['prediction']} (P(IA)={res_raw['prob_sintetico']:.4f})")
    print(f"Código formateado: Pred={res_fmt['prediction']} (P(IA)={res_fmt['prob_sintetico']:.4f})")

    diff = abs(res_raw["prob_sintetico"] - res_fmt["prob_sintetico"])
    print(f"Diferencia en probabilidad tras formateo: {diff:.4f}")
    assert res_raw["prediction"] == res_fmt["prediction"], "El formateo alteró la clase predicha!"
    print("✅ TEST 2 PASÓ: La predicción es invariante ante formateo.")


def test_comment_stripping_invariance():
    print("\n" + "=" * 60)
    print("TEST 3: Invarianza ante Inserción de Comentarios")
    print("=" * 60)

    infer = CharCNNInference(Path("models/char_cnn/best_model.pth"))

    code_clean = """
#include <stdio.h>
int factorial(int n) {
    if (n <= 1) return 1;
    return n * factorial(n - 1);
}
int main() {
    int x = 5;
    printf("%d", factorial(x));
    return 0;
}
"""

    code_heavy_comments = """
/*
 * Program: Factorial Calculator
 * Author: Student
 * Description: Computes factorial using recursion
 */
#include <stdio.h>

// Recursive function to compute factorial of n
int factorial(int n) {
    // Base case: if n is 0 or 1
    if (n <= 1) return 1;
    // Recursive step
    return n * factorial(n - 1);
}

// Main execution routine
int main() {
    int x = 5; // Target value
    printf("%d", factorial(x));
    return 0; // Exit successfully
}
"""

    res_clean = infer.predict_text(code_clean)
    res_comments = infer.predict_text(code_heavy_comments)

    print(f"Sin comentarios:    Pred={res_clean['prediction']} (P(IA)={res_clean['prob_sintetico']:.4f})")
    print(f"Con docstrings LLM: Pred={res_comments['prediction']} (P(IA)={res_comments['prob_sintetico']:.4f})")

    diff = abs(res_clean["prob_sintetico"] - res_comments["prob_sintetico"])
    print(f"Diferencia por comentarios: {diff:.4f}")
    assert diff < 0.15, f"La presencia de comentarios altera demasiado la probabilidad: {diff}"
    print("✅ TEST 3 PASÓ: Sanitización efectiva, los comentarios no engañan a la red.")


def test_bimodal_fusion_non_diluting():
    print("\n" + "=" * 60)
    print("TEST 4: Verificación de Fusión Bimodal No Diluyente")
    print("=" * 60)

    from models.fusion import BimodalFusion, ComparisonResult, _cosine
    from models.graphcodebert.inference import GraphCodeBERTInference

    gcb = GraphCodeBERTInference()
    infer_char = CharCNNInference(Path("models/char_cnn/best_model.pth"))
    fusion = BimodalFusion(gcb, infer_char)

    test_file = Path("data/raw/src/A2016/Z1/Z1/student1013.c")
    res = fusion.compare(test_file, [test_file])
    top = res[0]

    print(f"Autocomparación estudiante con sí mismo:")
    print(f"  Similitud Reportada:   {top.similarity:.6f}")
    print(f"  Similitud Semántica:   {top.semantic_similarity:.6f}")
    print(f"  P(Sintético):          {top.prob_sintetico:.6f}")
    print(f"  Riesgo Combinado:      {top.combined_risk:.6f}")

    assert abs(top.similarity - 1.0) < 1e-4, f"Falla matemática: similitud idéntica fue {top.similarity} en vez de 1.0!"
    print("✅ TEST 4 PASÓ: La similitud de un código idéntico es exactamente 1.0 (ya no sufre penalización por norma de estilo).")


if __name__ == "__main__":
    test_unseen_subproblems_generalization()
    test_formatting_invariance()
    test_comment_stripping_invariance()
    test_bimodal_fusion_non_diluting()
    print("\n" + "=" * 60)
    print("🎉 TODAS LAS PRUEBAS DE ROBUSTEZ PASARON EXITOSAMENTE")
    print("=" * 60)
