#include <iostream>
using namespace std;

struct Nodo {
    int valor;
    Nodo* siguiente;
};

Nodo* tope = NULL;

void push(int v) {
    Nodo* nuevo = new Nodo();
    nuevo->valor = v;
    nuevo->siguiente = tope;
    tope = nuevo;
}

void pop() {
    if(tope == NULL) cout << "No hay nada que sacar" << endl;
    else {
        Nodo* aux = tope;
        cout << "Pop: " << aux->valor << endl;
        tope = tope->siguiente;
        delete aux;
    }
}

int main() {
    push(100);
    push(200);
    pop();
    pop();
    return 0;
}
