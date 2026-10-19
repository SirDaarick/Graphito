#include <stdio.h>

int grafo[4][4] = {
    {0, 1, 1, 0},
    {1, 0, 1, 1},
    {1, 1, 0, 1},
    {0, 1, 1, 0}
};

// prueba todas las combinaciones 2^n por fuerza bruta
int main() {
    int n = 4;
    int maxClique = 0;

    for(int mascara = 1; mascara < (1 << n); mascara++) {
        int esClique = 1;
        int tamActual = 0;

        for(int i = 0; i < n; i++) {
            if(mascara & (1 << i)) {
                tamActual++;
                for(int j = i + 1; j < n; j++) {
                    if((mascara & (1 << j)) && grafo[i][j] == 0) {
                        esClique = 0;
                        break;
                    }
                }
            }
        }
        if(esClique && tamActual > maxClique) {
            maxClique = tamActual;
        }
    }

    printf("Tamano de la Clique Maxima por fuerza bruta O(2^n): %d\n", maxClique);
    return 0;
}
