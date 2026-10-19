#include <stdio.h>
#include <stdlib.h>
#include <time.h>

void cambiar(int *a, int *b) {
    int t = *a; *a = *b; *b = t;
}

int particion(int a[], int l, int r) {
    int pivote = a[r];
    int i = l - 1;
    for(int j = l; j < r; j++) {
        if(a[j] < pivote) {
            i++;
            cambiar(&a[i], &a[j]);
        }
    }
    cambiar(&a[i + 1], &a[r]);
    return i + 1;
}

int particionAleatoria(int a[], int l, int r) {
    int randomIdx = l + rand() % (r - l + 1);
    cambiar(&a[randomIdx], &a[r]); // movemos pivote al final
    return particion(a, l, r);
}

void quicksortRand(int a[], int l, int r) {
    if(l < r) {
        int p = particionAleatoria(a, l, r);
        quicksortRand(a, l, p - 1);
        quicksortRand(a, p + 1, r);
    }
}

int main() {
    srand(time(NULL));
    int arr[6] = {10, 7, 8, 9, 1, 5};
    quicksortRand(arr, 0, 5);

    printf("Arreglo ordenado con Quicksort Aleatorizado: ");
    for(int i = 0; i < 6; i++) printf("%d ", arr[i]);
    printf("\n");
    return 0;
}
