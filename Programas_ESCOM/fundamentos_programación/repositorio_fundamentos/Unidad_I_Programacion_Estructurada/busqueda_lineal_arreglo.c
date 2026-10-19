#include <stdio.h>

int main() {
    int arr[100];
    int n, buscar, encontrado = 0;
    
    printf("Cuantos datos vas a meter?: ");
    scanf("%d", &n);
    
    for(int i = 0; i < n; i++) {
        printf("Dato [%d]: ", i);
        scanf("%d", &arr[i]);
    }
    
    printf("Que numero buscas?: ");
    scanf("%d", &buscar);
    
    for(int i = 0; i < n; i++) {
        if(arr[i] == buscar) {
            printf("Si esta en la posicion %d\n", i);
            encontrado = 1;
            break;
        }
    }
    
    if(encontrado == 0) {
        printf("No se encontro el numero\n");
    }
    return 0;
}
