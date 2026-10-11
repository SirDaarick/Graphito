"""Student-archetype benchmark over the backend's shared scoring path.

Run from `backend/` (so `app` is importable), with the same settings as the backend:
  INFERENCE_MODE=REAL python ../scripts/benchmark_student_archetypes.py
Writes `benchmark_archetypes_results.json` in the current directory.
"""

import asyncio
import json

from app.application.services.scoring_service import ScoringService
from app.config import settings
from app.domain.ports.vector_store_port import VectorStorePort
from app.infrastructure.inference.runtime import build_runtime

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

class _NoVectorStore(VectorStorePort):
    """No Chroma offline: the exploratory GraphCodeBERT signal reports `SIN_INDICE` (never decides)."""

    async def upsert_reference(self, reference_id, embedding, metadata, document=None):
        raise NotImplementedError("the benchmark never writes vectors")

    async def query_nearest(self, embedding, problema_id, top_k=1):
        return []

    async def delete_reference(self, reference_id):
        raise NotImplementedError("the benchmark never deletes vectors")


async def _score_all(scoring: ScoringService):
    results = []
    for key, data in ARCHETYPES.items():
        outcome = await scoring.score_code(data["codigo"].strip(), [("referencia", REF_CODE)], language="c")
        a, b = outcome.channel_a, outcome.channel_b
        results.append({
            "key": key,
            "titulo": data["titulo"],
            "descripcion": data["descripcion"],
            "engine": outcome.engine,
            "jaccard_raw": a.raw,
            "jaccard_calibrado": a.calibrated,
            "umbral_a": a.threshold,
            "estado_canal_a": outcome.estado_canal_a,
            "flag_a": outcome.flag_a,
            "charcnn_calibrado": b.calibrated,
            "umbral_b": b.threshold,
            "estado_canal_b": outcome.estado_canal_b,
            "flag_b": outcome.flag_b,
            "dictamen": outcome.dictamen,
            "indicadores": ScoringService.build_indicators(outcome),
        })
    return results


def run_benchmarks():
    """Score every archetype with the backend's shared `ScoringService` (spec AS1): Channel A
    lexical Jaccard and Channel B CharCNN v2 with the deploy-artifact calibrations and thresholds
    (`INFERENCE_MODE=REAL`), or the stub engine and fixed development thresholds (`STUB`)."""
    print("Iniciando motores de inferencia...")
    runtime = build_runtime(settings)
    if not runtime.ready:
        raise SystemExit(f"Inferencia no lista (engine={runtime.engine_label}, motivo={runtime.reason}).")
    scoring = ScoringService(runtime.engine, runtime.calibration, _NoVectorStore(), runtime.lexical)
    try:
        results = asyncio.run(_score_all(scoring))
    finally:
        close = getattr(runtime.engine, "close", None)
        if callable(close):
            close()

    with open("benchmark_archetypes_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print("Resultados calculados y guardados en benchmark_archetypes_results.json")

if __name__ == "__main__":
    run_benchmarks()
