#include <iostream>
using namespace std;

int precios[9] = {0, 1, 5, 8, 9, 10, 17, 17, 20};

// corte de varilla con programacion dinamica bottom-up
int corteDP(int n) {
    int tabla[10];
    tabla[0] = 0;

    for(int j = 1; j <= n; j++) {
        int maxVal = -1;
        for(int i = 1; i <= j; i++) {
            if(precios[i] + tabla[j - i] > maxVal) {
                maxVal = precios[i] + tabla[j - i];
            }
        }
        tabla[j] = maxVal;
    }
    return tabla[n];
}

int main() {
    int tam = 8;
    cout << "Ganancia maxima corte varilla con DP para tam " << tam << ": " << corteDP(tam) << endl;
    return 0;
}
