#include <stdio.h>

int main() {
    int A[2][2] = {{1, 2}, {3, 4}};
    int B[2][2] = {{5, 6}, {7, 8}};
    int C[2][2] = {{0, 0}, {0, 0}};
    int n = 2;
    int operaciones = 0;

    // multiplicacion tradicional de matrices O(n^3)
    for(int i = 0; i < n; i++) {
        for(int j = 0; j < n; j++) {
            for(int k = 0; k < n; k++) {
                C[i][j] += A[i][k] * B[k][j];
                operaciones++;
            }
        }
    }

    printf("Matriz resultante:\n");
    for(int i = 0; i < n; i++) {
        for(int j = 0; j < n; j++) {
            printf("%d ", C[i][j]);
        }
        printf("\n");
    }
    printf("Total de multiplicaciones O(n^3): %d\n", operaciones);
    return 0;
}
