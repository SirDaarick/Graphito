#include <iostream>
using namespace std;
#define INF 9999

int costo[4][4] = {
    {0, 4, 2, INF},
    {4, 0, 1, 5},
    {2, 1, 0, 8},
    {INF, 5, 8, 0}
};

int dist[4];
bool visto[4];

int main() {
    for(int i = 0; i < 4; i++) {
        dist[i] = INF;
        visto[i] = false;
    }
    dist[0] = 0; // origen en vertice 0

    for(int count = 0; count < 4 - 1; count++) {
        int min = INF, u = -1;
        for(int v = 0; v < 4; v++) {
            if(!visto[v] && dist[v] <= min) {
                min = dist[v];
                u = v;
            }
        }
        visto[u] = true;
        for(int v = 0; v < 4; v++) {
            if(!visto[v] && costo[u][v] != INF && dist[u] + costo[u][v] < dist[v]) {
                dist[v] = dist[u] + costo[u][v];
            }
        }
    }

    cout << "Distancias mas cortas desde el vertice 0 (Dijkstra):" << endl;
    for(int i = 0; i < 4; i++) {
        cout << "Hasta nodo " << i << ": " << dist[i] << endl;
    }
    return 0;
}
