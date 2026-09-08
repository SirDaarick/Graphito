"""
Semantic similarity benchmark for C/C++ code.
Evaluates embeddings on equivalent vs non-equivalent programs,
specifically focusing on pointer arithmetic, aliasing, and syntactical refactorings.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dataclasses import dataclass
from typing import Callable, List
import numpy as np


@dataclass
class CodePair:
    id: str
    name: str
    category: str  # "pointer_arithmetic", "aliasing", "refactoring", "negative"
    is_equivalent: bool
    code_a: str
    code_b: str


BENCHMARK_PAIRS: List[CodePair] = [
    # 1. Pointer arithmetic vs array indexing (sum array)
    CodePair(
        id="ptr_vs_idx_sum",
        name="Array sum: indexing vs pointer arithmetic",
        category="pointer_arithmetic",
        is_equivalent=True,
        code_a="""
int sum_array(int arr[], int n) {
    int total = 0;
    for (int i = 0; i < n; i++) {
        total += arr[i];
    }
    return total;
}
""",
        code_b="""
int sum_array(int *arr, int n) {
    int total = 0;
    int *end = arr + n;
    while (arr < end) {
        total += *arr;
        arr++;
    }
    return total;
}
""",
    ),
    # 2. String copy: classic pointer traversal vs index
    CodePair(
        id="strcpy_ptr_vs_idx",
        name="String copy: index vs pointer increment",
        category="pointer_arithmetic",
        is_equivalent=True,
        code_a="""
void string_copy(char *dest, const char *src) {
    int i = 0;
    while (src[i] != '\\0') {
        dest[i] = src[i];
        i++;
    }
    dest[i] = '\\0';
}
""",
        code_b="""
void string_copy(char *dest, const char *src) {
    while (*src != '\\0') {
        *dest++ = *src++;
    }
    *dest = '\\0';
}
""",
    ),
    # 3. Aliasing: indirect mutation through pointer vs direct
    CodePair(
        id="aliasing_mutation",
        name="Variable mutation: direct vs indirect pointer dereference",
        category="aliasing",
        is_equivalent=True,
        code_a="""
int calculate(int base) {
    int factor = 10;
    factor = factor + 5;
    return base * factor;
}
""",
        code_b="""
int calculate(int base) {
    int factor = 10;
    int *p = &factor;
    *p = *p + 5;
    return base * factor;
}
""",
    ),
    # 4. Swap values using pointers vs arithmetic swap
    CodePair(
        id="swap_pointers",
        name="Swap values: pointers vs reference",
        category="pointer_arithmetic",
        is_equivalent=True,
        code_a="""
void swap(int *x, int *y) {
    int temp = *x;
    *x = *y;
    *y = temp;
}
""",
        code_b="""
void swap(int *a, int *b) {
    if (a != b) {
        *a = *a ^ *b;
        *b = *a ^ *b;
        *a = *a ^ *b;
    }
}
""",
    ),
    # 5. String length: pointer difference vs counter
    CodePair(
        id="strlen_diff",
        name="String length: counter vs pointer difference",
        category="pointer_arithmetic",
        is_equivalent=True,
        code_a="""
int string_length(const char *str) {
    int len = 0;
    while (*str != '\\0') {
        len++;
        str++;
    }
    return len;
}
""",
        code_b="""
int string_length(const char *str) {
    const char *p = str;
    while (*p) {
        p++;
    }
    return (int)(p - str);
}
""",
    ),
    # 6. Struct member access: pointer arrow vs direct dot reference
    CodePair(
        id="struct_ptr_arrow",
        name="Struct access: pointer arrow vs direct",
        category="aliasing",
        is_equivalent=True,
        code_a="""
struct Point { int x; int y; };
int get_distance_squared(struct Point p) {
    return p.x * p.x + p.y * p.y;
}
""",
        code_b="""
struct Point { int x; int y; };
int get_distance_squared(const struct Point *p) {
    return (p->x) * (p->x) + (p->y) * (p->y);
}
""",
    ),
    # 7. Refactoring: for loop to while loop
    CodePair(
        id="loop_refactoring",
        name="Loop refactoring: for vs while",
        category="refactoring",
        is_equivalent=True,
        code_a="""
int factorial(int n) {
    int result = 1;
    for (int i = 1; i <= n; i++) {
        result *= i;
    }
    return result;
}
""",
        code_b="""
int factorial(int n) {
    int result = 1;
    int i = 1;
    while (i <= n) {
        result *= i;
        i++;
    }
    return result;
}
""",
    ),
    # 8. Refactoring: recursion vs iteration
    CodePair(
        id="fibonacci_rec_iter",
        name="Fibonacci: recursive vs iterative",
        category="refactoring",
        is_equivalent=True,
        code_a="""
int fib(int n) {
    if (n <= 1) return n;
    return fib(n - 1) + fib(n - 2);
}
""",
        code_b="""
int fib(int n) {
    if (n <= 1) return n;
    int a = 0, b = 1;
    for (int i = 2; i <= n; i++) {
        int temp = a + b;
        a = b;
        b = temp;
    }
    return b;
}
""",
    ),
    # NEGATIVE PAIRS (Different semantics)
    # 9. Array sum vs Array product
    CodePair(
        id="sum_vs_product",
        name="Array sum vs Array product",
        category="negative",
        is_equivalent=False,
        code_a="""
int compute(int arr[], int n) {
    int acc = 0;
    for (int i = 0; i < n; i++) {
        acc += arr[i];
    }
    return acc;
}
""",
        code_b="""
int compute(int arr[], int n) {
    int acc = 1;
    for (int i = 0; i < n; i++) {
        acc *= arr[i];
    }
    return acc;
}
""",
    ),
    # 10. Find minimum vs Find maximum
    CodePair(
        id="min_vs_max",
        name="Find minimum vs Find maximum",
        category="negative",
        is_equivalent=False,
        code_a="""
int find_extreme(int arr[], int n) {
    int val = arr[0];
    for (int i = 1; i < n; i++) {
        if (arr[i] < val) {
            val = arr[i];
        }
    }
    return val;
}
""",
        code_b="""
int find_extreme(int arr[], int n) {
    int val = arr[0];
    for (int i = 1; i < n; i++) {
        if (arr[i] > val) {
            val = arr[i];
        }
    }
    return val;
}
""",
    ),
    # 11. String copy vs String reverse
    CodePair(
        id="copy_vs_reverse",
        name="String copy vs String reverse",
        category="negative",
        is_equivalent=False,
        code_a="""
void process_str(char *dest, const char *src, int n) {
    for (int i = 0; i < n; i++) {
        dest[i] = src[i];
    }
    dest[n] = '\\0';
}
""",
        code_b="""
void process_str(char *dest, const char *src, int n) {
    for (int i = 0; i < n; i++) {
        dest[i] = src[n - 1 - i];
    }
    dest[n] = '\\0';
}
""",
    ),
    # 12. Linear search vs Count occurrences
    CodePair(
        id="search_vs_count",
        name="Linear search vs Count occurrences",
        category="negative",
        is_equivalent=False,
        code_a="""
int scan(int arr[], int n, int target) {
    for (int i = 0; i < n; i++) {
        if (arr[i] == target) return i;
    }
    return -1;
}
""",
        code_b="""
int scan(int arr[], int n, int target) {
    int count = 0;
    for (int i = 0; i < n; i++) {
        if (arr[i] == target) count++;
    }
    return count;
}
""",
    ),
]


def cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
    a = np.array(vec_a, dtype=np.float32)
    b = np.array(vec_b, dtype=np.float32)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


def run_benchmark(embed_fn: Callable[[str], List[float]], model_name: str = "Model") -> dict:
    pos_sims = []
    neg_sims = []
    ptr_pos_sims = []
    details = []

    print(f"\\n=======================================================")
    print(f"BENCHMARK: {model_name}")
    print(f"=======================================================")

    for pair in BENCHMARK_PAIRS:
        emb_a = embed_fn(pair.code_a.strip())
        emb_b = embed_fn(pair.code_b.strip())
        sim = cosine_similarity(emb_a, emb_b)
        details.append({
            "id": pair.id,
            "name": pair.name,
            "category": pair.category,
            "is_equivalent": pair.is_equivalent,
            "similarity": sim,
        })
        status = "EQUIV" if pair.is_equivalent else "DIFF "
        print(f"[{status}] [{pair.category:<18}] {pair.name:<50} -> {sim:.4f}")

        if pair.is_equivalent:
            pos_sims.append(sim)
            if pair.category in ("pointer_arithmetic", "aliasing"):
                ptr_pos_sims.append(sim)
        else:
            neg_sims.append(sim)

    avg_pos = float(np.mean(pos_sims)) if pos_sims else 0.0
    avg_neg = float(np.mean(neg_sims)) if neg_sims else 0.0
    avg_ptr_pos = float(np.mean(ptr_pos_sims)) if ptr_pos_sims else 0.0
    separation_margin = avg_pos - avg_neg

    # Optimal threshold classification
    all_sims = neg_sims + pos_sims
    best_f1 = 0.0
    best_thresh = 0.0
    for thresh in np.linspace(min(all_sims), max(all_sims), 50):
        tp = sum(1 for s in pos_sims if s >= thresh)
        fp = sum(1 for s in neg_sims if s >= thresh)
        fn = sum(1 for s in pos_sims if s < thresh)
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
        if f1 > best_f1:
            best_f1 = f1
            best_thresh = thresh

    print(f"\\n--- Resumen de Métricas ---")
    print(f"Promedio Similitud Positivos (Equivalentes): {avg_pos:.4f}")
    print(f"Promedio Similitud Punteros / Alias:        {avg_ptr_pos:.4f}")
    print(f"Promedio Similitud Negativos (Diferentes):   {avg_neg:.4f}")
    print(f"Margen de Separación (Pos - Neg):           {separation_margin:.4f}")
    print(f"Mejor F1-Score:                             {best_f1:.4f} (Umbral: {best_thresh:.4f})")
    print(f"=======================================================\\n")

    return {
        "model": model_name,
        "avg_positive": avg_pos,
        "avg_pointer_positive": avg_ptr_pos,
        "avg_negative": avg_neg,
        "separation_margin": separation_margin,
        "best_f1": best_f1,
        "best_threshold": best_thresh,
        "details": details,
    }


if __name__ == "__main__":
    from models.graphcodebert.inference import GraphCodeBERTInference

    print("Cargando GraphCodeBERT base...")
    engine = GraphCodeBERTInference()
    run_benchmark(lambda code: engine.predict_code(code, "c")["embedding"], "GraphCodeBERT (Base Actual)")
