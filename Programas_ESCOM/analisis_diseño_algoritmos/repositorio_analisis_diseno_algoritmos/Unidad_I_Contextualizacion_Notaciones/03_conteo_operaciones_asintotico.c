#include <stdio.h>

int main() {
    int n = 5;
    int contadorLineal = 0;
    int contadorCuadratico = 0;

    // conteo de pasos para O(n)
    for(int i = 0; i < n; i++) {
        contadorLineal++;
    }

    // conteo de pasos para O(n^2)
    for(int i = 0; i < n; i++) {
        for(int j = 0; j < n; j++) {
            contadorCuadratico++;
        }
    }

    printf("Para n = %d:\n", n);
    printf("Operaciones en O(n): %d\n", contadorLineal);
    printf("Operaciones en O(n^2): %d\n", contadorCuadratico);
    return 0;
}
