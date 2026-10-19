#include <stdio.h>

// algoritmo iterativo de kadane para el maximo subarreglo
int main() {
    int arr[8] = {-2, -5, 6, -2, -3, 1, 5, -6};
    int n = 8;
    int maxTotal = arr[0];
    int maxActual = arr[0];

    for(int i = 1; i < n; i++) {
        if(arr[i] > maxActual + arr[i]) {
            maxActual = arr[i];
        } else {
            maxActual += arr[i];
        }

        if(maxActual > maxTotal) {
            maxTotal = maxActual;
        }
    }

    printf("Suma del maximo subarreglo (iterativo Kadane): %d\n", maxTotal);
    return 0;
}
