#include <iostream>
using namespace std;

int ady[4][4] = {
    {0, 1, 1, 0},
    {1, 0, 0, 1},
    {1, 0, 0, 0},
    {0, 1, 0, 0}
};

int visitado[4] = {0};
int cola[10], frente = 0, fin = 0;

int main() {
    int inicio = 0;
    cout << "Recorrido BFS (amplitud): ";
    
    visitado[inicio] = 1;
    cola[fin++] = inicio;

    while(frente < fin) {
        int v = cola[frente++];
        cout << v << " ";

        for(int j = 0; j < 4; j++) {
            if(ady[v][j] == 1 && !visitado[j]) {
                visitado[j] = 1;
                cola[fin++] = j;
            }
        }
    }
    cout << endl;
    return 0;
}
