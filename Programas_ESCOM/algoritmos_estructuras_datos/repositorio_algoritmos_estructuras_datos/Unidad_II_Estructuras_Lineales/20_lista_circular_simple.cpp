#include <iostream>
using namespace std;

struct Nodo {
    int num;
    Nodo* sig;
};

int main() {
    Nodo* primero = new Nodo{1, NULL};
    Nodo* segundo = new Nodo{2, NULL};
    Nodo* tercero = new Nodo{3, NULL};

    primero->sig = segundo;
    segundo->sig = tercero;
    tercero->sig = primero; // cerramos el circulo

    Nodo* temp = primero;
    cout << "Recorrido circular: ";
    for(int i = 0; i < 6; i++) { // recorremos 2 vueltas completas
        cout << temp->num << " -> ";
        temp = temp->sig;
    }
    cout << "..." << endl;
    return 0;
}
