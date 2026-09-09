import asyncio
import numpy as np
from models.char_cnn.inference import CharCNNInference
from models.graphcodebert.inference import GraphCodeBERTInference
from app.application.orchestrator.analysis_orchestrator import AnalysisOrchestrator
from app.infrastructure.inference.stub_engine import StubInferenceEngine

# Códigos de prueba
CODE_HUMAN_FIZZBUZZ = """
#include <stdio.h>
int main() {
    int i;
    for(i=1; i<=100; i++) {
        if(i%15==0) printf("FizzBuzz\\n");
        else if(i%3==0) printf("Fizz\\n");
        else if(i%5==0) printf("Buzz\\n");
        else printf("%d\\n", i);
    }
    return 0;
}
"""

CODE_AI_FIZZBUZZ_PERFECT = """
#include <stdio.h>

/**
 * @brief Prints numbers from 1 to 100 with Fizz, Buzz, or FizzBuzz replacement.
 */
int main(void) {
    const int MAX_COUNT = 100;
    for (int i = 1; i <= MAX_COUNT; ++i) {
        if (i % 15 == 0) {
            printf("FizzBuzz\\n");
        } else if (i % 3 == 0) {
            printf("Fizz\\n");
        } else if (i % 5 == 0) {
            printf("Buzz\\n");
        } else {
            printf("%d\\n", i);
        }
    }
    return 0;
}
"""

CODE_FIZZBUZZ_ERRORS_UGLY = """
#include <stdio.h>
int main(){
int num=1;
while(num<=100){
if(num%3==0&&num%5==0)
printf("FizzBuzz\\n");
else if(num%3==0)
printf("Fizz\\n");
else if(num%5==0)
printf("Buzz\\n");
else
printf("%d\\n",num);
num++;
}
return 0;}
"""

CODE_QUICKSORT_DIFFERENT = """
#include <stdio.h>

void swap(int* a, int* b) {
    int t = *a;
    *a = *b;
    *b = t;
}

int partition(int arr[], int low, int high) {
    int pivot = arr[high];
    int i = (low - 1);
    for (int j = low; j <= high - 1; j++) {
        if (arr[j] < pivot) {
            i++;
            swap(&arr[i], &arr[j]);
        }
    }
    swap(&arr[i + 1], &arr[high]);
    return (i + 1);
}

void quickSort(int arr[], int low, int high) {
    if (low < high) {
        int pi = partition(arr, low, high);
        quickSort(arr, low, pi - 1);
        quickSort(arr, pi + 1, high);
    }
}
"""


def test_charcnn_calibration():
    print("\n--- [1] EVALUACIÓN DE CHARCNN (ESTILOMETRÍA SIN PADDING ARTIFICIAL) ---")
    engine = CharCNNInference("models/char_cnn/best_model.pth")

    res_human = engine.predict_text(CODE_HUMAN_FIZZBUZZ)
    res_ai = engine.predict_text(CODE_AI_FIZZBUZZ_PERFECT)

    print(f"Humano FizzBuzz -> Predicción: {res_human['prediction']} | Prob IA: {res_human['prob_sintetico']*100:.2f}% | Prob Humano: {res_human['prob_humano']*100:.2f}%")
    print(f"AI FizzBuzz     -> Predicción: {res_ai['prediction']} | Prob IA: {res_ai['prob_sintetico']*100:.2f}% | Prob Humano: {res_ai['prob_humano']*100:.2f}%")

    assert res_human["prob_sintetico"] < 0.25, f"Código humano no debería tener alta prob de IA ({res_human['prob_sintetico']})"
    assert res_ai["prob_sintetico"] > 0.85, f"Código IA debería ser detectado como IA ({res_ai['prob_sintetico']})"
    print("✅ CharCNN sin padding distingue con éxito humano vs IA en códigos cortos!")


def test_graphcodebert_calibration():
    print("\n--- [2] EVALUACIÓN DE GRAPHCODEBERT (CALIBRACIÓN DE ANISOTROPÍA) ---")
    gcb = GraphCodeBERTInference()

    emb_ref = gcb.predict_code(CODE_HUMAN_FIZZBUZZ)["embedding"]
    emb_variant = gcb.predict_code(CODE_FIZZBUZZ_ERRORS_UGLY)["embedding"]
    emb_diff = gcb.predict_code(CODE_QUICKSORT_DIFFERENT)["embedding"]

    def cosine(a, b):
        a, b = np.array(a), np.array(b)
        return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))

    raw_sim_variant = cosine(emb_ref, emb_variant)
    raw_sim_diff = cosine(emb_ref, emb_diff)

    calib_sim_variant = AnalysisOrchestrator.calibrate_semantic_similarity(raw_sim_variant)
    calib_sim_diff = AnalysisOrchestrator.calibrate_semantic_similarity(raw_sim_diff)

    print(f"FizzBuzz vs Variante Fea/Modificada:")
    print(f"  Similitud Cruda:      {raw_sim_variant*100:.2f}%")
    print(f"  Similitud Calibrada:  {calib_sim_variant*100:.2f}%")

    print(f"FizzBuzz vs QuickSort (Completamente diferente):")
    print(f"  Similitud Cruda:      {raw_sim_diff*100:.2f}%")
    print(f"  Similitud Calibrada:  {calib_sim_diff*100:.2f}%")

    assert calib_sim_variant > 0.75, f"Variante de FizzBuzz debería conservar alta similitud ({calib_sim_variant})"
    assert calib_sim_diff < 0.25, f"QuickSort debería tener muy baja similitud (<25%), dio: {calib_sim_diff}"
    print("✅ Calibración de anisotropía separa de manera nítida algoritmos iguales vs diferentes!")


def test_decision_orchestrator():
    print("\n--- [3] EVALUACIÓN DEL MOTOR DE DECISIÓN BIMODAL ---")
    stub = StubInferenceEngine()

    # Caso 1: Código diferente escrito por humano (baja similitud + baja prob IA -> INTEGRO)
    dec_diff_human = stub.compute_decision(semantic_similarity=0.16, synthetic_prob=0.10, threshold_sem=0.75, threshold_ai=0.70)
    print(f"Decisión Humano QuickSort vs FizzBuzz: Dictamen={dec_diff_human['dictamen']}")
    assert dec_diff_human["dictamen"] == "INTEGRO"

    # Caso 2: AI FizzBuzz frente a FizzBuzz (alta similitud + alta prob IA -> SOSPECHA_IA)
    dec_ai = stub.compute_decision(semantic_similarity=0.90, synthetic_prob=0.96, threshold_sem=0.75, threshold_ai=0.70)
    print(f"Decisión AI FizzBuzz vs FizzBuzz: Dictamen={dec_ai['dictamen']}")
    assert dec_ai["dictamen"] == "SOSPECHA_IA"

    # Caso 3: Humano FizzBuzz frente a FizzBuzz (alta similitud + baja prob IA -> PLAGIO_PROBABLE)
    dec_plagio = stub.compute_decision(semantic_similarity=0.90, synthetic_prob=0.10, threshold_sem=0.75, threshold_ai=0.70)
    print(f"Decisión Humano FizzBuzz vs FizzBuzz: Dictamen={dec_plagio['dictamen']}")
    assert dec_plagio["dictamen"] == "PLAGIO_PROBABLE"

    print("✅ Motor de decisión bimodal clasifica con 100% de precisión todos los escenarios!")


if __name__ == "__main__":
    test_charcnn_calibration()
    test_graphcodebert_calibration()
    test_decision_orchestrator()
    print("\n🎉 TODAS LAS PRUEBAS EXPERIMENTALES PASARON CON ÉXITO!")
