#include <stdio.h>

struct Coordenada {
    int x;
    int y;
};

int main() {
    struct Coordenada punto = {12, 24};
    struct Coordenada *ptr = &punto;
    
    printf("Coordenada original: (%d, %d)\n", ptr->x, ptr->y);
    
    ptr->x = 50;
    ptr->y = 100;
    printf("Coordenada modificada: (%d, %d)\n", punto.x, punto.y);
    return 0;
}
