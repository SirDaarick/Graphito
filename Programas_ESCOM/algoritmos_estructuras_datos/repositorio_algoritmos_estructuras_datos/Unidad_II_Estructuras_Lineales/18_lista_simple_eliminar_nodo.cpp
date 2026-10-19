#include <iostream>
using namespace std;

struct Nodo {
    int dato;
    Nodo* sig;
};

void eliminar(Nodo* &cab, int val) {
    if(cab == NULL) return;
    if(cab->dato == val) {
        Nodo* borrar = cab;
        cab = cab->sig;
        delete borrar;
        return;
    }
    Nodo* act = cab;
    while(act->sig != NULL && act->sig->dato != val) {
        act = act->sig;
    }
    if(act->sig != NULL) {
        Nodo* borrar = act->sig;
        act->sig = act->sig->sig;
        delete borrar;
    }
}

int main() {
    Nodo* cabeza = new Nodo{5, new Nodo{15, new Nodo{25, NULL}}};
    cout << "Eliminando 15..." << endl;
    eliminar(cabeza, 15);
    for(Nodo* p = cabeza; p != NULL; p = p->sig) cout << p->dato << " ";
    cout << endl;
    return 0;
}
