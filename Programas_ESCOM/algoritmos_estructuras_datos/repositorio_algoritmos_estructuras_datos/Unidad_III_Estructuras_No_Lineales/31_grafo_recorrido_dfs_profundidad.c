#include <stdio.h>

int matriz[4][4] = {
    {0, 1, 1, 0},
    {1, 0, 0, 1},
    {1, 0, 0, 0},
    {0, 1, 0, 0}
};

int visitados[4] = {0};

void dfs(int v) {
    visitados[v] = 1;
    printf("%d ", v);

    for(int i = 0; i < 4; i++) {
        if(matriz[v][i] == 1 && !visitados[i]) {
            dfs(i); // recursion en profundidad
        }
    }
}

int main() {
    printf("Recorrido DFS (profundidad): ");
    dfs(0);
    printf("\n");
    return 0;
}
