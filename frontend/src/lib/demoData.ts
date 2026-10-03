import { Docente, Problema, CodigoFuente, ReporteAnalisis, ReportCodeComparison, ComentarioRevision } from "./api";

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

export const DEMO_REPORTS: Record<number, ReporteAnalisis> = {
    101: {
        id: 101,
        entrega_id: "sub-101",
        referencia_id: "ref-1",
        similitud_semantica: 0.94,
        probabilidad_ia: 0.14,
        discrepancia_score: 0.80,
        dictamen: "PLAGIO_PROBABLE",
        estado: "COMPLETADO",
        indicadores: [
            {
                tipo_alerta: "ISOMORFISMO_DFG",
                descripcion: "El grafo de flujo de datos (DFG) es 96% idéntico al código canónico de la cátedra con renombrado sistemático de variables.",
                severidad: "CRITICA",
            },
            {
                tipo_alerta: "MUTACION_COSMETICA_AST",
                descripcion: "Sustitución directa de identificadores ('dist' -> 'd_arr', 'sptSet' -> 'v_flag', 'minDistance' -> 'obtener_minimo') sin alterar topología ni orden de sentencias.",
                severidad: "ALTA",
            },
        ],
    },
    102: {
        id: 102,
        entrega_id: "sub-102",
        referencia_id: "ref-1",
        similitud_semantica: 0.68,
        probabilidad_ia: 0.93,
        discrepancia_score: 0.25,
        dictamen: "SOSPECHA_IA",
        estado: "COMPLETADO",
        indicadores: [
            {
                tipo_alerta: "PERPLEJIDAD_ESTILOMETRICA_BAJA",
                descripcion: "La red neuronal convolucional a nivel de caracteres (CharCNN) detectó uniformidad atípica en espaciado, nombres autodocumentados y longitud de tokens.",
                severidad: "ALTA",
            },
            {
                tipo_alerta: "PATRON_COMENTARIOS_LLM",
                descripcion: "Uso de directivas Doxygen completas y comentarios paso a paso ('Paso 1: Inicialización...', 'Paso 2: Bucle...') típicos de respuestas de ChatGPT o Claude.",
                severidad: "MEDIA",
            },
        ],
    },
    103: {
        id: 103,
        entrega_id: "sub-103",
        referencia_id: "ref-1",
        similitud_semantica: 0.22,
        probabilidad_ia: 0.08,
        discrepancia_score: 0.14,
        dictamen: "INTEGRO",
        estado: "COMPLETADO",
        indicadores: [],
    },
    201: {
        id: 201,
        entrega_id: "sub-201",
        referencia_id: "ref-2",
        similitud_semantica: 0.88,
        probabilidad_ia: 0.85,
        discrepancia_score: 0.03,
        dictamen: "DISCREPANCIA_DUAL",
        estado: "COMPLETADO",
        indicadores: [
            {
                tipo_alerta: "PATRON_REPOSITORIO_PUBLICO",
                descripcion: "Estructura de rotaciones AVL con coincidencia alta de fragmentos encontrados en repositorios públicos de GitHub y prompts generativos.",
                severidad: "MEDIA",
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
