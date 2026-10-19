#include <stdio.h>
#include <stdlib.h>

struct NodoDoble {
    int dato;
    struct NodoDoble* ant;
    struct NodoDoble* sig;
};

int main() {
    struct NodoDoble* n1 = (struct NodoDoble*)malloc(sizeof(struct NodoDoble));
    struct NodoDoble* n2 = (struct NodoDoble*)malloc(sizeof(struct NodoDoble));
    
    n1->dato = 100; n1->ant = NULL; n1->sig = n2;
    n2->dato = 200; n2->ant = n1; n2->sig = NULL;

    printf("Hacia adelante: %d -> %d\n", n1->dato, n1->sig->dato);
    printf("Hacia atras: %d -> %d\n", n2->dato, n2->ant->dato);
    return 0;
}
