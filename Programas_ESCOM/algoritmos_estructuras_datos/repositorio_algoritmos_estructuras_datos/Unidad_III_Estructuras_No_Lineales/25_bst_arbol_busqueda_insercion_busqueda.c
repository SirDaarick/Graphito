#include <stdio.h>
#include <stdlib.h>

struct BST {
    int valor;
    struct BST *izq, *der;
};

struct BST* insertar(struct BST* r, int v) {
    if(r == NULL) {
        struct BST* n = (struct BST*)malloc(sizeof(struct BST));
        n->valor = v;
        n->izq = n->der = NULL;
        return n;
    }
    if(v < r->valor) r->izq = insertar(r->izq, v);
    else r->der = insertar(r->der, v);
    return r;
}

int buscar(struct BST* r, int v) {
    if(r == NULL) return 0;
    if(r->valor == v) return 1;
    if(v < r->valor) return buscar(r->izq, v);
    return buscar(r->der, v);
}

int main() {
    struct BST* arbol = NULL;
    arbol = insertar(arbol, 50);
    arbol = insertar(arbol, 30);
    arbol = insertar(arbol, 70);

    if(buscar(arbol, 30)) printf("El 30 si existe en el BST\n");
    if(!buscar(arbol, 99)) printf("El 99 no existe en el BST\n");
    return 0;
}
