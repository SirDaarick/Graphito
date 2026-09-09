import json
import numpy as np
import torch
from models.char_cnn.inference import CharCNNInference
from models.graphcodebert.inference import GraphCodeBERTInference
from app.application.orchestrator.analysis_orchestrator import AnalysisOrchestrator
from app.infrastructure.inference.stub_engine import StubInferenceEngine

# ==============================================================================
# PROBLEMA: Verificación y filtrado de números primos en el rango [1, N]
# ==============================================================================

# 0. Código de Referencia Oficial del Docente
REF_CODE = """
/*
 * Práctica 3: Criba y Detección de Números Primos
 * Profesor: M. en C. Docente ESCOM
 */
#include <stdio.h>
#include <stdbool.h>

bool es_primo(int n) {
    if (n <= 1) return false;
    for (int i = 2; i * i <= n; i++) {
        if (n % i == 0) return false;
    }
    return true;
}

int main(void) {
    int limite = 100;
    printf("Numeros primos entre 1 y %d:\\n", limite);
    for (int i = 1; i <= limite; i++) {
        if (es_primo(i)) {
            printf("%d ", i);
        }
    }
    printf("\\n");
    return 0;
}
"""

ARCHETYPES = {
    "1_ia_gemini_perfecto": {
        "titulo": "Alumno IA (Gemini / ChatGPT puro)",
        "descripcion": "Generado íntegramente por LLM con comentarios explicativos, estilo canónico en inglés y nombrado descriptivo.",
        "codigo": """
#include <stdio.h>
#include <stdbool.h>

/**
 * @brief Checks if a given positive integer is prime.
 * @param number Integer to be checked.
 * @return true if prime, false otherwise.
 */
bool isPrime(int number) {
    if (number <= 1) {
        return false;
    }
    for (int divisor = 2; divisor * divisor <= number; ++divisor) {
        if (number % divisor == 0) {
            return false;
        }
    }
    return true;
}

int main(void) {
    const int UPPER_BOUND = 100;
    printf("Prime numbers up to %d:\\n", UPPER_BOUND);
    
    for (int current = 1; current <= UPPER_BOUND; ++current) {
        if (isPrime(current)) {
            printf("%d ", current);
        }
    }
    printf("\\n");
    return 0;
}
"""
    },
    "2_humano_aplicado": {
        "titulo": "Alumno Aplicado (Humano limpio)",
        "descripcion": "Estudiante responsable que resuelve el problema con funciones, nombres en español y formato estándar de laboratorio.",
        "codigo": """
// Tarea de primos - Juan Perez Grupo 3CV1
#include <stdio.h>

int verificarPrimo(int num) {
    int i;
    if (num < 2) return 0;
    for (i = 2; i < num; i++) {
        if (num % i == 0) {
            return 0;
        }
    }
    return 1;
}

int main() {
    int n = 100;
    int x;
    printf("Lista de primos:\\n");
    for (x = 1; x <= n; x++) {
        if (verificarPrimo(x) == 1) {
            printf("%d ", x);
        }
    }
    printf("\\n");
    return 0;
}
"""
    },
    "3_humano_malas_practicas": {
        "titulo": "Alumno con Malas Prácticas (Espagueti / Desorden)",
        "descripcion": "Todo en el main, variables de una letra (i, j, b, c), indentación inconsistente y sin funciones separadas.",
        "codigo": """
#include <stdio.h>
int main(){
int n=100,i,j,b;
printf("primos:\\n");
for(i=1;i<=n;i++){
if(i<=1)continue;
b=1;
for(j=2;j*j<=i;j++){
if(i%j==0){b=0;break;}
}
if(b==1)printf("%d ",i);
}
printf("\\n");return 0;
}
"""
    },
    "4_humano_intento_fallido": {
        "titulo": "Alumno que 'lo intentó pero no le salió'",
        "descripcion": "Lógica incompleta o errónea: cuenta divisores de forma deficiente, condición rota (deja pasar pares o no valida 1), imprime basura pero tiene la estructura del intento.",
        "codigo": """
#include <stdio.h>

int main() {
    int limite = 100;
    int c = 0;
    printf("Primos:\\n");
    // intento de contar si solo tiene 2 divisores pero mal indexado
    for (int i = 1; i <= limite; i++) {
        c = 0;
        for (int j = 1; j <= i; j++) {
            if (i % j == 0) {
                c++;
            }
        }
        // error: marco mayor a 2 en lugar de igual a 2, o se equivoco en la condicion
        if (c <= 2 && i != 1) {
            printf("%d ", i);
        } else {
            // codigo con prints de debug que olvido borrar
            // printf("no es primo %d\\n", i);
        }
    }
    return 0;
}
"""
    },
    "5_humano_astuto_parafraseo_ia": {
        "titulo": "El Tramposo Astuto (IA parafraseada a mano)",
        "descripcion": "Tomó la salida de ChatGPT, tradujo nombres a español, borró comentarios de Doxygen y alteró operadores para intentar engañar al detector.",
        "codigo": """
#include <stdio.h>
#include <stdbool.h>

bool checar_si_es_primo(int valor) {
    if (valor <= 1) return false;
    int d = 2;
    while (d * d <= valor) {
        if (valor % d == 0) return false;
        d++;
    }
    return true;
}

int main() {
    int maximo = 100;
    printf("Numeros encontrados:\\n");
    for (int k = 1; k <= maximo; k++) {
        if (checar_si_es_primo(k)) printf("%d ", k);
    }
    printf("\\n");
    return 0;
}
"""
    },
    "6_completamente_diferente": {
        "titulo": "El Confundido (Entregó otra práctica completamente diferente)",
        "descripcion": "Entregó el algoritmo de Ordenamiento Burbuja de un arreglo, no tiene nada que ver con números primos.",
        "codigo": """
#include <stdio.h>

void burbuja(int a[], int n) {
    int i, j, temp;
    for (i = 0; i < n - 1; i++) {
        for (j = 0; j < n - i - 1; j++) {
            if (a[j] > a[j + 1]) {
                temp = a[j];
                a[j] = a[j + 1];
                a[j + 1] = temp;
            }
        }
    }
}

int main() {
    int arr[] = {64, 34, 25, 12, 22, 11, 90};
    int n = sizeof(arr)/sizeof(arr[0]);
    burbuja(arr, n);
    printf("Arreglo ordenado:\\n");
    for (int i = 0; i < n; i++) {
        printf("%d ", arr[i]);
    }
    printf("\\n");
    return 0;
}
"""
    }
}

def run_benchmarks():
    print("Iniciando motores de inferencia...")
    char_cnn = CharCNNInference("models/char_cnn/best_model.pth")
    gcb = GraphCodeBERTInference()
    stub = StubInferenceEngine()

    # Embedding de la referencia
    ref_emb = gcb.predict_code(REF_CODE)["embedding"]

    def cosine(a, b):
        a, b = np.array(a), np.array(b)
        return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))

    results = []

    for key, data in ARCHETYPES.items():
        code = data["codigo"].strip()
        
        # Canal A: Semántica
        sem_res = gcb.predict_code(code)
        raw_sem = cosine(ref_emb, sem_res["embedding"])
        calib_sem = AnalysisOrchestrator.calibrate_semantic_similarity(raw_sem)

        # Canal B: Estilometría
        char_res = char_cnn.predict_text(code)
        ai_prob = char_res["prob_sintetico"]
        hum_prob = char_res["prob_humano"]
        char_pred = char_res["prediction"]

        # Motor de Decisión Bimodal
        decision = stub.compute_decision(
            semantic_similarity=calib_sem,
            synthetic_prob=ai_prob,
            threshold_sem=0.75,
            threshold_ai=0.70,
        )

        results.append({
            "key": key,
            "titulo": data["titulo"],
            "descripcion": data["descripcion"],
            "raw_sem": round(raw_sem, 4),
            "calib_sem": round(calib_sem, 4),
            "ai_prob": round(ai_prob, 4),
            "hum_prob": round(hum_prob, 4),
            "char_pred": char_pred,
            "dictamen": decision["dictamen"],
            "discrepancia": decision["discrepancia_score"],
            "indicadores": decision["indicadores"],
        })

    with open("benchmark_archetypes_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print("Resultados calculados y guardados en benchmark_archetypes_results.json")

if __name__ == "__main__":
    run_benchmarks()
