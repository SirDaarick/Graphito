"""
Pruebas de casos reales basados en el temario oficial de Fundamentos de Programación (ESCOM IPN ISC 2020).
Evalúa la similitud semántica con GraphCodeBERT (DFG mejorado) en las 3 unidades temáticas.
"""

import sys
from dataclasses import dataclass
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from models.graphcodebert.inference import GraphCodeBERTInference


@dataclass
class RealCase:
    unit: str
    problem_name: str
    student_a_desc: str
    student_b_desc: str
    is_same_problem: bool
    code_a: str
    code_b: str


REAL_CASES = [
    # ── UNIDAD I: PROGRAMACIÓN ESTRUCTURADA ──
    RealCase(
        unit="Unidad I",
        problem_name="Determinar si un número es primo",
        student_a_desc="Ciclo for clásico con bandera e if",
        student_b_desc="Ciclo while optimizado con raíz cuadrada y dobles condiciones",
        is_same_problem=True,
        code_a="""
int es_primo(int n) {
    if (n <= 1) return 0;
    int primo = 1;
    for (int i = 2; i < n; i++) {
        if (n % i == 0) {
            primo = 0;
            break;
        }
    }
    return primo;
}
""",
        code_b="""
int es_primo(int num) {
    if (num <= 1) return 0;
    int divisor = 2;
    while (divisor * divisor <= num) {
        if (num % divisor == 0) {
            return 0;
        }
        divisor++;
    }
    return 1;
}
""",
    ),
    RealCase(
        unit="Unidad I",
        problem_name="Calcular el factorial de un número",
        student_a_desc="Ciclo for acumulador",
        student_b_desc="Ciclo do-while decremental",
        is_same_problem=True,
        code_a="""
long long factorial(int n) {
    long long res = 1;
    for (int i = 1; i <= n; i++) {
        res = res * i;
    }
    return res;
}
""",
        code_b="""
long long factorial(int valor) {
    if (valor <= 1) return 1;
    long long total = 1;
    int k = valor;
    do {
        total *= k;
        k--;
    } while (k > 1);
    return total;
}
""",
    ),

    # ── UNIDAD II: APUNTADORES, STRUCTS Y FUNCIONES ──
    RealCase(
        unit="Unidad II",
        problem_name="Inversión de cadena de caracteres (Strings in-place)",
        student_a_desc="Paso de string e indexación clásica con arreglo str[i]",
        student_b_desc="Aritmética de punteros con punteros inicio y fin",
        is_same_problem=True,
        code_a="""
void invertir_cadena(char str[]) {
    int i = 0, j = 0;
    while (str[j] != '\\0') {
        j++;
    }
    j--;
    while (i < j) {
        char temp = str[i];
        str[i] = str[j];
        str[j] = temp;
        i++;
        j--;
    }
}
""",
        code_b="""
void invertir_cadena(char *s) {
    char *fin = s;
    while (*fin) {
        fin++;
    }
    fin--;
    char *ini = s;
    while (ini < fin) {
        char aux = *ini;
        *ini = *fin;
        *fin = aux;
        ini++;
        fin--;
    }
}
""",
    ),
    RealCase(
        unit="Unidad II",
        problem_name="Buscar y actualizar calificación en struct Alumno",
        student_a_desc="Arreglo de structs con indexación lista[i].promedio",
        student_b_desc="Puntero a struct con operador flecha ptr->promedio",
        is_same_problem=True,
        code_a="""
struct Alumno {
    int boleta;
    float promedio;
};

int actualizar(struct Alumno lista[], int total, int boleta_buscar, float nueva_cal) {
    for (int i = 0; i < total; i++) {
        if (lista[i].boleta == boleta_buscar) {
            lista[i].promedio = nueva_cal;
            return 1;
        }
    }
    return 0;
}
""",
        code_b="""
struct Alumno {
    int boleta;
    float promedio;
};

int actualizar(struct Alumno *ptr, int total, int matricula, float calificacion) {
    struct Alumno *limite = ptr + total;
    while (ptr < limite) {
        if (ptr->boleta == matricula) {
            ptr->promedio = calificacion;
            return 1;
        }
        ptr++;
    }
    return 0;
}
""",
    ),

    # ── UNIDAD III: MEMORIA DINÁMICA Y ARCHIVOS ──
    RealCase(
        unit="Unidad III",
        problem_name="Creación y llenado dinámico de arreglo con malloc",
        student_a_desc="malloc simple con indexación vec[i]",
        student_b_desc="malloc con validación de puntero nulo y aritmética *(ptr + i)",
        is_same_problem=True,
        code_a="""
#include <stdlib.h>

int* crear_vector(int tam, int valor_inicial) {
    int *vec = (int*) malloc(tam * sizeof(int));
    if (vec == NULL) return NULL;
    for (int i = 0; i < tam; i++) {
        vec[i] = valor_inicial;
    }
    return vec;
}
""",
        code_b="""
#include <stdlib.h>

int* crear_vector(int n, int defecto) {
    int *arr = malloc(sizeof(int) * n);
    if (!arr) {
        return NULL;
    }
    int *p = arr;
    for (int k = 0; k < n; k++) {
        *p = defecto;
        p++;
    }
    return arr;
}
""",
    ),
    RealCase(
        unit="Unidad III",
        problem_name="Copiar contenido de archivo de texto",
        student_a_desc="fgetc caracter por caracter con bucle while",
        student_b_desc="fgets línea por línea con buffer dinámico",
        is_same_problem=True,
        code_a="""
#include <stdio.h>

void duplicar(const char *origen, const char *destino) {
    FILE *f1 = fopen(origen, "r");
    FILE *f2 = fopen(destino, "w");
    if (!f1 || !f2) return;
    int c;
    while ((c = fgetc(f1)) != EOF) {
        fputc(c, f2);
    }
    fclose(f1);
    fclose(f2);
}
""",
        code_b="""
#include <stdio.h>

void duplicar(const char *in_file, const char *out_file) {
    FILE *arch_in = fopen(in_file, "r");
    FILE *arch_out = fopen(out_file, "w");
    if (arch_in == NULL || arch_out == NULL) return;
    char buffer[256];
    while (fgets(buffer, sizeof(buffer), arch_in) != NULL) {
        fputs(buffer, arch_out);
    }
    fclose(arch_in);
    fclose(arch_out);
}
""",
    ),

    # ── CASOS NEGATIVOS (PROBLEMAS DISTINTOS DENTRO DEL MISMO CURSO) ──
    RealCase(
        unit="Negativo",
        problem_name="Primo vs Factorial (Distinto problema de Unidad I)",
        student_a_desc="Algoritmo de número primo",
        student_b_desc="Algoritmo de factorial",
        is_same_problem=False,
        code_a="""
int es_primo(int n) {
    if (n <= 1) return 0;
    for (int i = 2; i * i <= n; i++) {
        if (n % i == 0) return 0;
    }
    return 1;
}
""",
        code_b="""
long long factorial(int n) {
    long long res = 1;
    for (int i = 1; i <= n; i++) {
        res *= i;
    }
    return res;
}
""",
    ),
    RealCase(
        unit="Negativo",
        problem_name="Invertir String vs Contar Vocales (Distinto de Unidad II)",
        student_a_desc="Invertir cadena con punteros",
        student_b_desc="Contar vocales en cadena con punteros",
        is_same_problem=False,
        code_a="""
void invertir(char *s) {
    char *fin = s;
    while (*fin) fin++;
    fin--;
    while (s < fin) {
        char temp = *s;
        *s++ = *fin;
        *fin-- = temp;
    }
}
""",
        code_b="""
int contar_vocales(const char *ptr) {
    int total = 0;
    while (*ptr) {
        char c = *ptr;
        if (c == 'a' || c == 'e' || c == 'i' || c == 'o' || c == 'u') {
            total++;
        }
        ptr++;
    }
    return total;
}
""",
    ),
    RealCase(
        unit="Negativo",
        problem_name="Duplicar archivo vs Contar líneas (Distinto de Unidad III)",
        student_a_desc="Copiar archivo de texto",
        student_b_desc="Contar líneas de archivo",
        is_same_problem=False,
        code_a="""
#include <stdio.h>
void copiar(const char *f1, const char *f2) {
    FILE *in = fopen(f1, "r");
    FILE *out = fopen(f2, "w");
    if (!in || !out) return;
    int c;
    while ((c = fgetc(in)) != EOF) fputc(c, out);
    fclose(in);
    fclose(out);
}
""",
        code_b="""
#include <stdio.h>
int contar_lineas(const char *nom_arch) {
    FILE *arch = fopen(nom_arch, "r");
    if (!arch) return -1;
    int lineas = 0;
    int ch;
    while ((ch = fgetc(arch)) != EOF) {
        if (ch == '\\n') lineas++;
    }
    fclose(arch);
    return lineas;
}
""",
    ),
]


def test_real_cases():
    print("=" * 70)
    print("EVALUACIÓN EN CASOS REALES: FUNDAMENTOS DE PROGRAMACIÓN (ESCOM IPN)")
    print("=" * 70)
    engine = GraphCodeBERTInference()

    pos_sims = []
    neg_sims = []

    for c in REAL_CASES:
        e1 = np.array(engine.predict_code(c.code_a.strip(), "c")["embedding"])
        e2 = np.array(engine.predict_code(c.code_b.strip(), "c")["embedding"])
        sim = float(np.dot(e1, e2) / (np.linalg.norm(e1) * np.linalg.norm(e2)))

        tipo = "MISMO PROB (PLAGIO/EQUIV)" if c.is_same_problem else "DISTINTO PROBLEMA      "
        print(f"\n[{c.unit}] {c.problem_name}")
        print(f"  Tipo: {tipo} | Similitud Coseno: {sim:.4f}")
        print(f"  Alumno A: {c.student_a_desc}")
        print(f"  Alumno B: {c.student_b_desc}")

        if c.is_same_problem:
            pos_sims.append(sim)
        else:
            neg_sims.append(sim)

    avg_pos = np.mean(pos_sims)
    avg_neg = np.mean(neg_sims)
    gap = avg_pos - avg_neg

    print("\n" + "=" * 70)
    print("RESUMEN GENERAL POR CASOS REALES")
    print("=" * 70)
    print(f"Promedio Similitud Mismo Problema (Positivos):      {avg_pos:.4f}")
    print(f"Promedio Similitud Problemas Distintos (Negativos): {avg_neg:.4f}")
    print(f"Margen de Separación (GAP):                         {gap:+.4f}")
    print(f"¿Separación clara entre mismos problemas y distintos?: {'SÍ' if gap > 0 else 'NO'}")
    print("=" * 70)


if __name__ == "__main__":
    test_real_cases()
