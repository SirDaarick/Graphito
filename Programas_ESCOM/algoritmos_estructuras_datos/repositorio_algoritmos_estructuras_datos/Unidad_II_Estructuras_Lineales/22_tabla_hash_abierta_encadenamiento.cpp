#include <iostream>
using namespace std;
#define TAM 5

struct Nodo {
    int dato;
    Nodo* sig;
};

Nodo* tabla[TAM]; // arreglo de listas

void insertarHash(int val) {
    int bucket = val % TAM;
    Nodo* nuevo = new Nodo{val, tabla[bucket]};
    tabla[bucket] = nuevo;
}

int main() {
    for(int i = 0; i < TAM; i++) tabla[i] = NULL;

    insertarHash(10);
    insertarHash(15);
    insertarHash(22);

    for(int i = 0; i < TAM; i++) {
        cout << "Casilla [" << i << "]: ";
        Nodo* p = tabla[i];
        while(p) {
            cout << p->dato << " -> ";
            p = p->sig;
        }
        cout << "NULL" << endl;
    }
    return 0;
}
