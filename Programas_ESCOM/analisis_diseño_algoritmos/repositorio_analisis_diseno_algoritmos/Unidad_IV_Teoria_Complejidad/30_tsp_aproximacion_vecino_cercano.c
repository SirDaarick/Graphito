#include <stdio.h>
#define INF 9999

int distancia[4][4] = {
    {0, 10, 15, 20},
    {10, 0, 35, 25},
    {15, 35, 0, 30},
    {20, 25, 30, 0}
};

int visitado[4] = {0};

int main() {
    int ciudadActual = 0;
    int costoTotal = 0;
    visitado[ciudadActual] = 1;

    printf("Ruta aproximada TSP (Vecino Mas Cercano):\n");
    printf("%d -> ", ciudadActual);

    for(int paso = 0; paso < 3; paso++) {
        int mejorDist = INF;
        int proxima = -1;

        for(int j = 0; j < 4; j++) {
            if(!visitado[j] && distancia[ciudadActual][j] < mejorDist) {
                mejorDist = distancia[ciudadActual][j];
                proxima = j;
            }
        }
        visitado[proxima] = 1;
        costoTotal += mejorDist;
        ciudadActual = proxima;
        printf("%d -> ", ciudadActual);
    }

    // volvemos al inicio
    costoTotal += distancia[ciudadActual][0];
    printf("0\n");
    printf("Costo total aproximado del tour: %d\n", costoTotal);
    return 0;
}
