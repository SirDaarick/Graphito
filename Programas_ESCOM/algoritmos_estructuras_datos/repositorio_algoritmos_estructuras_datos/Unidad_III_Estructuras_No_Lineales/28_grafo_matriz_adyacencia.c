#include <stdio.h>

int grafo[4][4]; // 4 vertices (0 a 3)

void agregarArista(int u, int v) {
    grafo[u][v] = 1;
    grafo[v][u] = 1; // no dirigido
}

int main() {
    agregarArista(0, 1);
    agregarArista(0, 2);
    agregarArista(1, 3);

    printf("Matriz de adyacencia del grafo:\n");
    for(int i = 0; i < 4; i++) {
        for(int j = 0; j < 4; j++) {
            printf("%d ", grafo[i][j]);
        }
        printf("\n");
    }
    return 0;
}
