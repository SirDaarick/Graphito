import { Docente, Problema, CodigoFuente, ReporteAnalisis, ReportCodeComparison, ComentarioRevision, CatalogSubject, CatalogProgramDetail } from "./api";

export const DEMO_DOCENTE: Docente = {
    id: 1,
    nombre: "Dr. Alan Turing",
    email: "alan.turing@graphito.edu",
    created_at: "2026-01-15T08:00:00Z",
};

export const DEMO_PROBLEMAS: Problema[] = [
    {
        id: 1,
        docente_id: 1,
        titulo: "Algoritmo de Dijkstra para Rutas Óptimas",
        enunciado: "Implementar en C el algoritmo de caminos mínimos de Dijkstra para un grafo ponderado no dirigido representado mediante matriz de adyacencia. El programa debe determinar el vector de distancias mínimas y la ruta desde el nodo origen hacia todos los demás nodos.",
        lenguaje: "c",
        fecha_creacion: "2026-09-15T10:00:00Z",
    },
    {
        id: 2,
        docente_id: 1,
        titulo: "Árboles AVL: Rotaciones Simples y Dobles",
        enunciado: "Implementar en C las operaciones de inserción y rebalanceo para un árbol binario de búsqueda auto-balanceable (AVL). El programa debe calcular el factor de balanceo y realizar rotaciones LL, RR, LR y RL cuando corresponda.",
        lenguaje: "c",
        fecha_creacion: "2026-09-10T09:00:00Z",
    },
];

const DIJKSTRA_REF_CODE = `#include <stdio.h>
#include <limits.h>
#include <stdbool.h>

#define V 6

int minDistance(int dist[], bool sptSet[]) {
    int min = INT_MAX, min_index = -1;
    for (int v = 0; v < V; v++) {
        if (!sptSet[v] && dist[v] <= min) {
            min = dist[v];
            min_index = v;
        }
    }
    return min_index;
}

void printSolution(int dist[]) {
    printf("Vertice \\t Distancia desde Origen\\n");
    for (int i = 0; i < V; i++)
        printf("%d \\t\\t %d\\n", i, dist[i]);
}

void dijkstra(int graph[V][V], int src) {
    int dist[V];
    bool sptSet[V];

    for (int i = 0; i < V; i++) {
        dist[i] = INT_MAX;
        sptSet[i] = false;
    }

    dist[src] = 0;

    for (int count = 0; count < V - 1; count++) {
        int u = minDistance(dist, sptSet);
        if (u == -1) break;
        sptSet[u] = true;

        for (int v = 0; v < V; v++) {
            if (!sptSet[v] && graph[u][v] && dist[u] != INT_MAX
                && dist[u] + graph[u][v] < dist[v]) {
                dist[v] = dist[u] + graph[u][v];
            }
        }
    }

    printSolution(dist);
}
`;

const DIJKSTRA_PLAGIO_CODE = `#include <stdio.h>
#include <limits.h>
#include <stdbool.h>

#define NODOS 6

// Funcion para obtener la distancia minima
int obtener_minimo(int distancias[], bool visitados[]) {
    int menor = INT_MAX, indice_menor = -1;
    for (int i = 0; i < NODOS; i++) {
        if (!visitados[i] && distancias[i] <= menor) {
            menor = distancias[i];
            indice_menor = i;
        }
    }
    return indice_menor;
}

void imprimir_tabla(int distancias[]) {
    printf("Vertice \\t Distancia minima\\n");
    for (int k = 0; k < NODOS; k++)
        printf("%d \\t\\t %d\\n", k, distancias[k]);
}

void resolver_dijkstra(int matriz[NODOS][NODOS], int origen) {
    int d_arr[NODOS];
    bool v_flag[NODOS];

    for (int j = 0; j < NODOS; j++) {
        d_arr[j] = INT_MAX;
        v_flag[j] = false;
    }

    d_arr[origen] = 0;

    for (int paso = 0; paso < NODOS - 1; paso++) {
        int actual = obtener_minimo(d_arr, v_flag);
        if (actual == -1) break;
        v_flag[actual] = true;

        for (int vecino = 0; vecino < NODOS; vecino++) {
            if (!v_flag[vecino] && matriz[actual][vecino] && d_arr[actual] != INT_MAX
                && d_arr[actual] + matriz[actual][vecino] < d_arr[vecino]) {
                d_arr[vecino] = d_arr[actual] + matriz[actual][vecino];
            }
        }
    }

    imprimir_tabla(d_arr);
}
`;

const DIJKSTRA_AI_CODE = `/**
 * @file dijkstra.c
 * @brief Implementación robusta del algoritmo de Dijkstra para grafos densos.
 * Generado con optimizaciones de claridad y documentación exhaustiva.
 */

#include <stdio.h>
#include <stdlib.h>
#include <limits.h>
#include <stdbool.h>

#define NUM_VERTICES 6

/**
 * @brief Encuentra el nodo con la distancia tentativa más pequeña.
 */
static int find_closest_unvisited_node(const int distances[NUM_VERTICES], const bool visited[NUM_VERTICES]) {
    int min_val = INT_MAX;
    int optimal_index = -1;

    for (int node_idx = 0; node_idx < NUM_VERTICES; ++node_idx) {
        if (!visited[node_idx] && distances[node_idx] <= min_val) {
            min_val = distances[node_idx];
            optimal_index = node_idx;
        }
    }
    return optimal_index;
}

/**
 * @brief Imprime las distancias calculadas en formato tabular legible.
 */
static void output_distance_results(const int distances[NUM_VERTICES]) {
    printf("========================================\\n");
    printf(" Node  | Shortest Path from Origin\\n");
    printf("========================================\\n");
    for (int i = 0; i < NUM_VERTICES; ++i) {
        printf("   %2d  |  %d\\n", i, distances[i]);
    }
    printf("========================================\\n");
}

void execute_dijkstra_algorithm(int adjacency_matrix[NUM_VERTICES][NUM_VERTICES], int source_vertex) {
    int distances[NUM_VERTICES];
    bool visited[NUM_VERTICES];

    // Paso 1: Inicialización de vectores de estado
    for (int i = 0; i < NUM_VERTICES; ++i) {
        distances[i] = INT_MAX;
        visited[i] = false;
    }

    distances[source_vertex] = 0;

    // Paso 2: Bucle principal de relajación de aristas
    for (int iteration = 0; iteration < NUM_VERTICES - 1; ++iteration) {
        int current_node = find_closest_unvisited_node(distances, visited);
        if (current_node == -1) {
            break; // No hay más nodos alcanzables
        }

        visited[current_node] = true;

        for (int neighbor = 0; neighbor < NUM_VERTICES; ++neighbor) {
            int edge_weight = adjacency_matrix[current_node][neighbor];
            if (!visited[neighbor] && edge_weight > 0 && distances[current_node] != INT_MAX) {
                int alternative_path = distances[current_node] + edge_weight;
                if (alternative_path < distances[neighbor]) {
                    distances[neighbor] = alternative_path;
                }
            }
        }
    }

    output_distance_results(distances);
}
`;

const DIJKSTRA_ORIGINAL_CODE = `#include <stdio.h>
#define N 6
#define INF 999999

int main() {
    int g[N][N];
    int d[N], visit[N];
    int ini = 0;

    // Inicializar matriz con datos de prueba
    for (int i = 0; i < N; i++) {
        visit[i] = 0;
        d[i] = INF;
        for (int j = 0; j < N; j++) g[i][j] = 0;
    }
    
    // Conexiones de ejemplo
    g[0][1] = 4; g[0][2] = 2;
    g[1][2] = 1; g[1][3] = 5;
    g[2][3] = 8; g[2][4] = 10;
    g[3][4] = 2; g[3][5] = 6;
    g[4][5] = 3;

    d[ini] = 0;

    for (int c = 0; c < N; c++) {
        int menor = INF;
        int act = -1;
        for (int i = 0; i < N; i++) {
            if (!visit[i] && d[i] < menor) {
                menor = d[i];
                act = i;
            }
        }

        if (act == -1) break;
        visit[act] = 1;

        for (int j = 0; j < N; j++) {
            if (g[act][j] > 0 && !visit[j]) {
                if (d[act] + g[act][j] < d[j]) {
                    d[j] = d[act] + g[act][j];
                }
            }
        }
    }

    for (int i = 0; i < N; i++) {
        printf("Nodo %d -> Distancia: %d\\n", i, d[i]);
    }
    return 0;
}
`;

// Demo reports (VITE_DEMO_MODE): example values in the current API shape, labelled engine "demo"
// so the UI shows a DEMO badge. They are not model results and carry no thresholds or hashes.
const DEMO_PROVENANCE = {
    engine: "demo",
    canal_a_metodo: "jaccard",
    umbral_a: null,
    umbral_b: null,
    clave_umbral_a: null,
    clave_umbral_b: null,
    puntaje_calibrado_a: null,
    calibracion_sha_a: null,
    calibracion_sha_b: null,
    checkpoint_sha_b: null,
    manifest_sha: null,
    gcb_estado: "DEMO",
    versiones_modelo: null,
    estado_calibracion: "demo",
    discrepancia_score: null,
    etiqueta_validacion:
        "DEMO: datos de ejemplo. No validado contra plagio derivado de la referencia: los umbrales se calibraron con pares estudiante-estudiante.",
} as const;

export const DEMO_REPORTS: Record<number, ReporteAnalisis> = {
    101: {
        ...DEMO_PROVENANCE,
        id: 101,
        entrega_id: "sub-101",
        referencia_id: "ref-1",
        reference_id: "ref-1",
        similitud_semantica: 0.94,
        probabilidad_ia: 0.14,
        gcb_similarity: 0.97,
        estado_canal_a: "EVALUADO",
        estado_canal_b: "EVALUADO",
        flag_a: true,
        flag_b: false,
        dictamen: "REVISION_SEMANTICA",
        estado: "COMPLETADO",
        decision_docente: "PENDIENTE",
        indicadores: [
            {
                tipo_alerta: "CONVERGENCIA_ESTRUCTURAL",
                descripcion: "DEMO — Bandera semántica: Canal A (Jaccard léxico, 5 tokens) sobre el umbral.",
                severidad: "MEDIA",
                numero_linea: null,
                categoria: "GENERAL",
                origen: "decision",
            },
            {
                tipo_alerta: "Similitud léxica con la referencia (archivo completo)",
                descripcion: "DEMO — Jaccard léxico (shingles de 5 tokens) 0.9400. Referencia más cercana: Solución de la cátedra (ref-1).",
                severidad: "ALTA",
                numero_linea: null,
                categoria: "SIMILITUD_ARCHIVO",
                origen: "decision",
            },
        ],
    },
    102: {
        ...DEMO_PROVENANCE,
        id: 102,
        entrega_id: "sub-102",
        referencia_id: "ref-1",
        reference_id: "ref-1",
        similitud_semantica: 0.68,
        probabilidad_ia: 0.93,
        gcb_similarity: 0.81,
        estado_canal_a: "EVALUADO",
        estado_canal_b: "EVALUADO",
        flag_a: false,
        flag_b: true,
        dictamen: "REVISION_ESTILOMETRICA",
        estado: "COMPLETADO",
        decision_docente: "PENDIENTE",
        indicadores: [
            {
                tipo_alerta: "PATRON_SINTETICO",
                descripcion: "DEMO — Bandera estilométrica: Canal B (CharCNN v2) sobre el umbral.",
                severidad: "MEDIA",
                numero_linea: null,
                categoria: "GENERAL",
                origen: "decision",
            },
            {
                tipo_alerta: "Heurística: Patrón de Documentación LLM",
                descripcion: "Heurística (no es salida del modelo). Línea 178: comentarios paso a paso ('Paso 1: Inicialización...', 'Paso 2: Bucle...') frecuentes en código generado.",
                severidad: "MEDIA",
                numero_linea: 178,
                categoria: "ESTILO_LLM",
                origen: "heuristica",
            },
        ],
    },
    103: {
        ...DEMO_PROVENANCE,
        id: 103,
        entrega_id: "sub-103",
        referencia_id: "ref-1",
        reference_id: "ref-1",
        similitud_semantica: 0.22,
        probabilidad_ia: 0.08,
        gcb_similarity: 0.41,
        estado_canal_a: "EVALUADO",
        estado_canal_b: "EVALUADO",
        flag_a: false,
        flag_b: false,
        dictamen: "SIN_ALERTAS",
        estado: "COMPLETADO",
        indicadores: [],
    },
    201: {
        ...DEMO_PROVENANCE,
        id: 201,
        entrega_id: "sub-201",
        referencia_id: "ref-2",
        reference_id: "ref-2",
        similitud_semantica: 0.88,
        probabilidad_ia: 0.85,
        gcb_similarity: null,
        estado_canal_a: "EVALUADO",
        estado_canal_b: "EVALUADO",
        flag_a: true,
        flag_b: true,
        dictamen: "DISCREPANCIA_DUAL",
        estado: "COMPLETADO",
        indicadores: [
            {
                tipo_alerta: "DISCREPANCIA_ESTILOMETRICA",
                descripcion: "DEMO — Bandera dual: Canal A (Jaccard léxico, 5 tokens) y Canal B (CharCNN v2) sobre sus umbrales. Revisión docente sugerida.",
                severidad: "ALTA",
                numero_linea: null,
                categoria: "GENERAL",
                origen: "decision",
            },
        ],
    },
};

export const DEMO_SUBMISSIONS: Record<number, CodigoFuente[]> = {
    1: [
        {
            id: "sub-101",
            problema_id: 1,
            tipo: "ENTREGA_ALUMNO",
            autor: "Carlos Mendoza (Grupo 3)",
            contenido: DIJKSTRA_PLAGIO_CODE,
            lenguaje: "c",
            created_at: "2026-09-20T14:32:00Z",
            reporte: DEMO_REPORTS[101],
        },
        {
            id: "sub-102",
            problema_id: 1,
            tipo: "ENTREGA_ALUMNO",
            autor: "Valeria Ramos (Grupo 1)",
            contenido: DIJKSTRA_AI_CODE,
            lenguaje: "c",
            created_at: "2026-09-21T02:15:00Z",
            reporte: DEMO_REPORTS[102],
        },
        {
            id: "sub-103",
            problema_id: 1,
            tipo: "ENTREGA_ALUMNO",
            autor: "Esteban Morales (Grupo 2)",
            contenido: DIJKSTRA_ORIGINAL_CODE,
            lenguaje: "c",
            created_at: "2026-09-21T18:40:00Z",
            reporte: DEMO_REPORTS[103],
        },
    ],
    2: [
        {
            id: "sub-201",
            problema_id: 2,
            tipo: "ENTREGA_ALUMNO",
            autor: "Sofia Herrera (Grupo 4)",
            contenido: "// Implementación AVL con rotaciones dobles...\n",
            lenguaje: "c",
            created_at: "2026-09-18T16:20:00Z",
            reporte: DEMO_REPORTS[201],
        },
    ],
};

export const DEMO_CODE_COMPARISONS: Record<number, ReportCodeComparison> = {
    101: {
        reporte_id: 101,
        student_author: "Carlos Mendoza (Grupo 3)",
        student_code: DIJKSTRA_PLAGIO_CODE,
        reference_author: "Prof. Alan Turing (Cátedra)",
        reference_code: DIJKSTRA_REF_CODE,
        language: "c",
        problem_title: "Algoritmo de Dijkstra para Rutas Óptimas",
    },
    102: {
        reporte_id: 102,
        student_author: "Valeria Ramos (Grupo 1)",
        student_code: DIJKSTRA_AI_CODE,
        reference_author: "Prof. Alan Turing (Cátedra)",
        reference_code: DIJKSTRA_REF_CODE,
        language: "c",
        problem_title: "Algoritmo de Dijkstra para Rutas Óptimas",
    },
    103: {
        reporte_id: 103,
        student_author: "Esteban Morales (Grupo 2)",
        student_code: DIJKSTRA_ORIGINAL_CODE,
        reference_author: "Prof. Alan Turing (Cátedra)",
        reference_code: DIJKSTRA_REF_CODE,
        language: "c",
        problem_title: "Algoritmo de Dijkstra para Rutas Óptimas",
    },
    201: {
        reporte_id: 201,
        student_author: "Sofia Herrera (Grupo 4)",
        student_code: "// Implementación AVL con rotaciones dobles...\n",
        reference_author: "Prof. Alan Turing (Cátedra)",
        reference_code: "// Solución de referencia AVL...\n",
        language: "c",
        problem_title: "Árboles AVL: Rotaciones Simples y Dobles",
    },
};

export const DEMO_COMMENTS: Record<number, ComentarioRevision[]> = {
    101: [
        {
            id: 1,
            reporte_id: 101,
            docente_id: 1,
            numero_linea: 38,
            contenido: "La secuencia de relajación de aristas y la condición de frontera son idénticas a la implementación canónica. Solo se modificaron los identificadores.",
            created_at: "2026-09-22T09:30:00Z",
            autor_nombre: "Dr. Alan Turing",
        },
    ],
    102: [
        {
            id: 2,
            reporte_id: 102,
            docente_id: 1,
            numero_linea: 19,
            contenido: "Patrón estilométrico característico de modelo generativo: documentación Doxygen hiper-detallada y nombres estandarizados inusuales para el contexto del curso.",
            created_at: "2026-09-22T10:15:00Z",
            autor_nombre: "Dr. Alan Turing",
        },
    ],
    103: [
        {
            id: 3,
            reporte_id: 103,
            docente_id: 1,
            numero_linea: null,
            contenido: "Código original y conciso. Implementación personalizada adecuada para el problema planteado.",
            created_at: "2026-09-22T11:00:00Z",
            autor_nombre: "Dr. Alan Turing",
        },
    ],
};

export interface DemoGrupo {
    id: number;
    docente_id: number;
    nombre: string;
    codigo_grupo: string;
    periodo: string;
    descripcion?: string;
    created_at: string;
    total_problemas?: number;
    total_entregas?: number;
}

export const DEMO_GRUPOS: DemoGrupo[] = [
    {
        id: 1,
        docente_id: 1,
        nombre: "Estructuras de Datos",
        codigo_grupo: "2CM1",
        periodo: "2026-B",
        descripcion: "Grupo matutino. Punteros, memoria dinámica y grafos en C.",
        created_at: "2026-08-20T08:00:00Z",
        total_problemas: 2,
        total_entregas: 3,
    },
    {
        id: 2,
        docente_id: 1,
        nombre: "Programación Avanzada",
        codigo_grupo: "3CV2",
        periodo: "2026-B",
        descripcion: "Grupo vespertino. Algoritmos avanzados de grafos y árboles balanceados.",
        created_at: "2026-08-22T14:00:00Z",
        total_problemas: 1,
        total_entregas: 1,
    },
    {
        id: 3,
        docente_id: 1,
        nombre: "Algoritmia y Complejidad",
        codigo_grupo: "4CM1",
        periodo: "2026-A",
        descripcion: "Semestre anterior archivado. Análisis asintótico y árboles AVL.",
        created_at: "2026-01-15T09:00:00Z",
        total_problemas: 1,
        total_entregas: 0,
    },
];

const demoCatalogEntry = (
    id: string,
    titulo: string,
    lenguaje: "c" | "cpp",
    nombre_archivo: string,
    materia: string,
    materia_nombre: string,
    unidad: string,
    unidad_nombre: string,
    codigo: string,
): CatalogProgramDetail => ({
    id, titulo, lenguaje, nombre_archivo, materia, materia_nombre, unidad, unidad_nombre, codigo,
});

const DEMO_CATALOG_ENTRIES: CatalogProgramDetail[] = [
    demoCatalogEntry("demo-ed-u1-pila", "Pila con arreglo", "c", "pila_arreglo.c",
        "estructuras_de_datos", "Estructuras de Datos", "unidad_1", "Unidad 1: Pilas y colas",
        `#include <stdio.h>

#define MAX 100

int pila[MAX];
int tope = -1;

void push(int x) {
    if (tope < MAX - 1) pila[++tope] = x;
}

int pop(void) {
    return tope >= 0 ? pila[tope--] : -1;
}

int main(void) {
    push(3);
    push(7);
    printf("%d\\n", pop());
    return 0;
}
`),
    demoCatalogEntry("demo-ed-u1-cola", "Cola circular", "c", "cola_circular.c",
        "estructuras_de_datos", "Estructuras de Datos", "unidad_1", "Unidad 1: Pilas y colas",
        `#include <stdio.h>

#define N 5

int cola[N];
int frente = 0, tam = 0;

void encolar(int x) {
    if (tam < N) cola[(frente + tam++) % N] = x;
}

int desencolar(void) {
    if (tam == 0) return -1;
    int v = cola[frente];
    frente = (frente + 1) % N;
    tam--;
    return v;
}

int main(void) {
    encolar(1);
    encolar(2);
    printf("%d\\n", desencolar());
    return 0;
}
`),
    demoCatalogEntry("demo-ed-u2-lista", "Lista enlazada simple", "c", "lista_simple.c",
        "estructuras_de_datos", "Estructuras de Datos", "unidad_2", "Unidad 2: Listas",
        `#include <stdio.h>
#include <stdlib.h>

typedef struct Nodo {
    int dato;
    struct Nodo *sig;
} Nodo;

Nodo *insertar(Nodo *cabeza, int dato) {
    Nodo *n = malloc(sizeof(Nodo));
    n->dato = dato;
    n->sig = cabeza;
    return n;
}

int main(void) {
    Nodo *l = insertar(insertar(NULL, 2), 1);
    for (Nodo *p = l; p; p = p->sig) printf("%d ", p->dato);
    return 0;
}
`),
    demoCatalogEntry("demo-ed-u2-busqueda", "Busqueda binaria", "c", "busqueda_binaria.c",
        "estructuras_de_datos", "Estructuras de Datos", "unidad_2", "Unidad 2: Listas",
        `#include <stdio.h>

int busqueda_binaria(int a[], int n, int x) {
    int lo = 0, hi = n - 1;
    while (lo <= hi) {
        int mid = lo + (hi - lo) / 2;
        if (a[mid] == x) return mid;
        if (a[mid] < x) lo = mid + 1;
        else hi = mid - 1;
    }
    return -1;
}

int main(void) {
    int a[] = {1, 3, 5, 7, 9};
    printf("%d\\n", busqueda_binaria(a, 5, 7));
    return 0;
}
`),
    demoCatalogEntry("demo-pa-u1-fib", "Fibonacci con memoizacion", "cpp", "fibonacci_memo.cpp",
        "programacion_avanzada", "Programación Avanzada", "unidad_1", "Unidad 1: Programación dinámica",
        `#include <iostream>
#include <vector>

long long fib(int n, std::vector<long long>& memo) {
    if (n < 2) return n;
    if (memo[n] != -1) return memo[n];
    return memo[n] = fib(n - 1, memo) + fib(n - 2, memo);
}

int main() {
    std::vector<long long> memo(51, -1);
    std::cout << fib(50, memo) << std::endl;
    return 0;
}
`),
    demoCatalogEntry("demo-pa-u2-bfs", "Recorrido BFS", "cpp", "bfs.cpp",
        "programacion_avanzada", "Programación Avanzada", "unidad_2", "Unidad 2: Grafos",
        `#include <iostream>
#include <queue>
#include <vector>

void bfs(const std::vector<std::vector<int>>& g, int s) {
    std::vector<bool> vis(g.size(), false);
    std::queue<int> q;
    q.push(s);
    vis[s] = true;
    while (!q.empty()) {
        int u = q.front();
        q.pop();
        std::cout << u << " ";
        for (int v : g[u]) {
            if (!vis[v]) {
                vis[v] = true;
                q.push(v);
            }
        }
    }
}

int main() {
    bfs({{1, 2}, {3}, {3}, {}}, 0);
    return 0;
}
`),
];

export const DEMO_CATALOG_DETAILS: Record<string, CatalogProgramDetail> = Object.fromEntries(
    DEMO_CATALOG_ENTRIES.map((e) => [e.id, e]),
);

/** Builds the grouped catalog list (no code) from the flat demo entries. */
export const DEMO_CATALOG: CatalogSubject[] = DEMO_CATALOG_ENTRIES.reduce<CatalogSubject[]>((subjects, e) => {
    let subject = subjects.find((s) => s.materia === e.materia);
    if (!subject) {
        subject = { materia: e.materia, materia_nombre: e.materia_nombre, total: 0, unidades: [] };
        subjects.push(subject);
    }
    let unit = subject.unidades.find((u) => u.unidad === e.unidad);
    if (!unit) {
        unit = { unidad: e.unidad, unidad_nombre: e.unidad_nombre, programas: [] };
        subject.unidades.push(unit);
    }
    unit.programas.push({ id: e.id, titulo: e.titulo, lenguaje: e.lenguaje, nombre_archivo: e.nombre_archivo });
    subject.total += 1;
    return subjects;
}, []);