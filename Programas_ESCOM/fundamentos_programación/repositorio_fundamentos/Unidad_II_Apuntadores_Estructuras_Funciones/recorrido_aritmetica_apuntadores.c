#include <stdio.h>

int main() {
    int datos[5] = {10, 25, 30, 45, 50};
    int *p = datos;
    
    for(int i = 0; i < 5; i++) {
        printf("Posicion %d: valor %d en direccion %p\n", i, *(p + i), (p + i));
    }
    return 0;
}
