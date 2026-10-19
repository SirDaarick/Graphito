#include <stdio.h>
#include <stdlib.h>

int main() {
    int tam;
    int *vector;
    
    printf("Cuantos enteros vas a guardar?: ");
    scanf("%d", &tam);
    
    vector = (int*) malloc(tam * sizeof(int));
    
    for(int i = 0; i < tam; i++) {
        vector[i] = (i + 1) * 10;
        printf("vector[%d] = %d\n", i, vector[i]);
    }
    
    return 0;
}
