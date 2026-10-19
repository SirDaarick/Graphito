#include <stdio.h>

int main() {
    int v[6] = {12, 11, 13, 5, 6, 7};
    int n = 6;
    int i, clave, j;

    // insercion como baraja de cartas
    for (i = 1; i < n; i++) {
        clave = v[i];
        j = i - 1;
        while (j >= 0 && v[j] > clave) {
            v[j + 1] = v[j];
            j = j - 1;
        }
        v[j + 1] = clave;
    }

    printf("Arreglo ordenado por insercion: ");
    for (i = 0; i < n; i++) printf("%d ", v[i]);
    printf("\n");
    return 0;
}
