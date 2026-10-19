#include <iostream>
using namespace std;

// demostracion del contador binario de bits para analisis agregado
int main() {
    int bits[5] = {0, 0, 0, 0, 0};
    int n = 16; // 16 incrementos
    int flipsTotales = 0;

    for(int i = 0; i < n; i++) {
        int j = 0;
        while(j < 5 && bits[j] == 1) {
            bits[j] = 0;
            flipsTotales++;
            j++;
        }
        if(j < 5) {
            bits[j] = 1;
            flipsTotales++;
        }
    }

    cout << "Total de cambios de bit (flips) para 16 operaciones: " << flipsTotales << endl;
    cout << "Costo amortizado por incremento: " << (double)flipsTotales / n << endl;
    return 0;
}
