#include <stdio.h>
#include <stdlib.h>

struct Nodo {
    int valor;
    struct Nodo* siguiente;
};

int main() {
    struct Nodo* cabeza = NULL;
    
    // insertamos 3 nodos al inicio
    for(int i = 1; i <= 3; i++) {
        struct Nodo* nuevo = (struct Nodo*)malloc(sizeof(struct Nodo));
        nuevo->valor = i * 10;
        nuevo->siguiente = cabeza;
        cabeza = nuevo;
    }
    
    // mostramos la lista
    struct Nodo* actual = cabeza;
    printf("Lista simple: ");
    while(actual != NULL) {
        printf("%d -> ", actual->valor);
        actual = actual->siguiente;
    }
    printf("NULL\n");
    return 0;
}
