#include <iostream>
using namespace std;

struct NodoVecino {
    int vertice;
    NodoVecino* sig;
};

NodoVecino* listaAdj[4];

void conectar(int u, int v) {
    NodoVecino* n1 = new NodoVecino{v, listaAdj[u]};
    listaAdj[u] = n1;
    NodoVecino* n2 = new NodoVecino{u, listaAdj[v]};
    listaAdj[v] = n2;
}

int main() {
    for(int i = 0; i < 4; i++) listaAdj[i] = NULL;
    conectar(0, 1);
    conectar(0, 3);
    conectar(1, 2);

    cout << "Lista de adyacencia:" << endl;
    for(int i = 0; i < 4; i++) {
        cout << "Vertice " << i << ": ";
        NodoVecino* p = listaAdj[i];
        while(p) {
            cout << p->vertice << " -> ";
            p = p->sig;
        }
        cout << "NULL" << endl;
    }
    return 0;
}
