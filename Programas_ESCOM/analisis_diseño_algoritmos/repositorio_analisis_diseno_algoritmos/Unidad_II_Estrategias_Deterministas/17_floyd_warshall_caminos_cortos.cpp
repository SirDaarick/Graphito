#include <iostream>
using namespace std;
#define INF 9999

int main() {
    int dist[4][4] = {
        {0, 5, INF, 10},
        {INF, 0, 3, INF},
        {INF, INF, 0, 1},
        {INF, INF, INF, 0}
    };

    // algoritmo de floyd warshall
    for(int k = 0; k < 4; k++) {
        for(int i = 0; i < 4; i++) {
            for(int j = 0; j < 4; j++) {
                if(dist[i][k] + dist[k][j] < dist[i][j]) {
                    dist[i][j] = dist[i][k] + dist[k][j];
                }
            }
        }
    }

    cout << "Matriz de distancias minimas entre todos los pares:" << endl;
    for(int i = 0; i < 4; i++) {
        for(int j = 0; j < 4; j++) {
            if(dist[i][j] == INF) cout << "INF ";
            else cout << dist[i][j] << " ";
        }
        cout << endl;
    }
    return 0;
}
