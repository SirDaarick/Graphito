#include <stdio.h>

int a[6] = {64, 34, 25, 12, 22, 11}; // arreglo global
int n = 6;

int main() {
    int i, j, temp;
    // burbuja clasica con dos for
    for(i = 0; i < n - 1; i++) {
        for(j = 0; j < n - i - 1; j++) {
            if(a[j] > a[j + 1]) {
                temp = a[j];
                a[j] = a[j + 1];
                a[j + 1] = temp;
            }
        }
    }
    printf("Arreglo ordenado por burbuja: ");
    for(i = 0; i < n; i++) {
        printf("%d ", a[i]);
    }
    printf("\n");
    return 0;
}
