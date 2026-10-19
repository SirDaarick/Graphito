#include <iostream>
using namespace std;

// algoritmo 2-aproximacion para Cobertura de Vertices
int main() {
    int aristas[4][2] = {{0, 1}, {1, 2}, {2, 3}, {0, 2}};
    int numAristas = 4;
    bool cubierto[4] = {false, false, false, false};

    cout << "Vertices seleccionados para el Vertex Cover aproximado:" << endl;
    for(int i = 0; i < numAristas; i++) {
        int u = aristas[i][0];
        int v = aristas[i][1];

        // si ningun extremo esta cubierto, tomamos ambos
        if(!cubierto[u] && !cubierto[v]) {
            cubierto[u] = true;
            cubierto[v] = true;
            cout << "Vertice " << u << " y Vertice " << v << endl;
        }
    }
    return 0;
}
