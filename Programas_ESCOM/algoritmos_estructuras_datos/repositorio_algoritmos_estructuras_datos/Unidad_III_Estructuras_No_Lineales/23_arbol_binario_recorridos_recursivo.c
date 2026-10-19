#include <stdio.h>
#include <stdlib.h>

struct NodoArbol {
    int dato;
    struct NodoArbol* izq;
    struct NodoArbol* der;
};

struct NodoArbol* crear(int v) {
    struct NodoArbol* n = (struct NodoArbol*)malloc(sizeof(struct NodoArbol));
    n->dato = v;
    n->izq = n->der = NULL;
    return n;
}

void preorden(struct NodoArbol* r) {
    if(r != NULL) {
        printf("%d ", r->dato);
        preorden(r->izq);
        preorden(r->der);
    }
}

void inorden(struct NodoArbol* r) {
    if(r != NULL) {
        inorden(r->izq);
        printf("%d ", r->dato);
        inorden(r->der);
    }
}

void postorden(struct NodoArbol* r) {
    if(r != NULL) {
        postorden(r->izq);
        postorden(r->der);
        printf("%d ", r->dato);
    }
}

int main() {
    struct NodoArbol* raiz = crear(1);
    raiz->izq = crear(2);
    raiz->der = crear(3);

    printf("Preorden: "); preorden(raiz); printf("\n");
    printf("Inorden: "); inorden(raiz); printf("\n");
    printf("Postorden: "); postorden(raiz); printf("\n");
    return 0;
}
