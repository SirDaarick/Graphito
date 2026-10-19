#include <stdio.h>

struct Indice {
    int clave;
    int pos;
};

int main() {
    // arreglo ordenado de datos
    int base[9] = {10, 20, 30, 40, 50, 60, 70, 80, 90};
    // tabla de indices cada 3 casillas
    struct Indice idx[3] = {{10, 0}, {40, 3}, {70, 6}};
    
    int buscado = 50;
    int inicio = 0, fin = 8;

    // buscamos en la tabla de indices primero
    for(int i = 0; i < 3; i++) {
        if(idx[i].clave <= buscado) {
            inicio = idx[i].pos;
            fin = (i == 2) ? 8 : idx[i + 1].pos;
        }
    }

    // busqueda secuencial en el rango encontrado
    int hallado = -1;
    for(int j = inicio; j <= fin; j++) {
        if(base[j] == buscado) {
            hallado = j;
            break;
        }
    }

    printf("Busqueda indexada de %d dio posicion: %d\n", buscado, hallado);
    return 0;
}
