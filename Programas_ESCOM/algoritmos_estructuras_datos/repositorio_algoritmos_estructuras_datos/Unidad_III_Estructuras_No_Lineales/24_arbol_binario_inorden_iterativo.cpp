#include <iostream>
using namespace std;

struct Nodo {
    int info;
    Nodo *izq, *der;
};

int main() {
    Nodo* raiz = new Nodo{10, new Nodo{5, NULL, NULL}, new Nodo{20, NULL, NULL}};
    Nodo* pila[20];
    int tope = -1;
    Nodo* act = raiz;

    cout << "Inorden iterativo con pila: ";
    while(act != NULL || tope != -1) {
        while(act != NULL) {
            pila[++tope] = act;
            act = act->izq;
        }
        act = pila[tope--];
        cout << act->info << " ";
        act = act->der;
    }
    cout << endl;
    return 0;
}
