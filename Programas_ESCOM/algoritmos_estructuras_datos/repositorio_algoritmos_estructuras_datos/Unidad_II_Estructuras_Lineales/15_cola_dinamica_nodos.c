#include <stdio.h>
#include <stdlib.h>

struct Nodo {
    int num;
    struct Nodo* sig;
};

struct Nodo *frente = NULL, *fondo = NULL;

void meter(int n) {
    struct Nodo* nuevo = (struct Nodo*)malloc(sizeof(struct Nodo));
    nuevo->num = n;
    nuevo->sig = NULL;
    if(fondo == NULL) {
        frente = fondo = nuevo;
    } else {
        fondo->sig = nuevo;
        fondo = nuevo;
    }
}

void sacar() {
    if(frente == NULL) {
        printf("Cola vacia\n");
        return;
    }
    struct Nodo* temp = frente;
    printf("Sacado de la cola: %d\n", temp->num);
    frente = frente->sig;
    if(frente == NULL) fondo = NULL;
    free(temp);
}

int main() {
    meter(55);
    meter(77);
    meter(99);
    sacar();
    sacar();
    return 0;
}
