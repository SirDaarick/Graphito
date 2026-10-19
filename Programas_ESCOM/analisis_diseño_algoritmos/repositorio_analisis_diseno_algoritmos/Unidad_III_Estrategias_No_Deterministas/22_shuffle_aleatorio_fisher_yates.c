#include <stdio.h>
#include <stdlib.h>
#include <time.h>

// algoritmo para barajar arreglo de forma aleatoria
int main() {
    srand(time(NULL));
    int baraja[8] = {1, 2, 3, 4, 5, 6, 7, 8};
    int n = 8;

    for(int i = n - 1; i > 0; i--) {
        int j = rand() % (i + 1);
        int temp = baraja[i];
        baraja[i] = baraja[j];
        baraja[j] = temp;
    }

    printf("Arreglo barajado con Fisher-Yates: ");
    for(int k = 0; k < n; k++) printf("%d ", baraja[k]);
    printf("\n");
    return 0;
}
