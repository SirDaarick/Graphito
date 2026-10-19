#include <stdio.h>

int main() {
    int numeros[7] = {15, 3, 89, 4, 21, 60, 42};
    int buscado, pos = -1;

    printf("Que numero buscas?: ");
    scanf("%d", &buscado);

    // recorremos todo el arreglo uno por uno
    for(int i = 0; i < 7; i++) {
        if(numeros[i] == buscado) {
            pos = i;
            break;
        }
    }

    if(pos != -1) {
        printf("Numero encontrado en la posicion %d\n", pos);
    } else {
        printf("El numero no existe en el arreglo\n");
    }
    return 0;
}
