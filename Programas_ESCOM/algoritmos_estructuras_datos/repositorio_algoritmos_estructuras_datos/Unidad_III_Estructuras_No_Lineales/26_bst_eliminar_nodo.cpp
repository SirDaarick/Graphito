#include <iostream>
using namespace std;

struct Nodo {
    int val;
    Nodo *izq, *der;
};

Nodo* minValorNodo(Nodo* n) {
    Nodo* act = n;
    while(act && act->izq != NULL) act = act->izq;
    return act;
}

Nodo* borrar(Nodo* r, int v) {
    if(r == NULL) return r;
    if(v < r->val) r->izq = borrar(r->izq, v);
    else if(v > r->val) r->der = borrar(r->der, v);
    else {
        if(r->izq == NULL) {
            Nodo* t = r->der;
            delete r;
            return t;
        } else if(r->der == NULL) {
            Nodo* t = r->izq;
            delete r;
            return t;
        }
        Nodo* t = minValorNodo(r->der);
        r->val = t->val;
        r->der = borrar(r->der, t->val);
    }
    return r;
}

void ver(Nodo* r) {
    if(r) { ver(r->izq); cout << r->val << " "; ver(r->der); }
}

int main() {
    Nodo* raiz = new Nodo{20, new Nodo{10, NULL, NULL}, new Nodo{30, NULL, NULL}};
    cout << "Arbol original: "; ver(raiz); cout << endl;
    raiz = borrar(raiz, 10);
    cout << "Despues de borrar 10: "; ver(raiz); cout << endl;
    return 0;
}
