#include <iostream>
using namespace std;

int pesos[3] = {1, 2, 3};
int valores[3] = {10, 15, 40};
int maxPeso = 5;

// exploracion exhaustiva para la mochila 0/1
int mochila(int i, int pesoActual) {
    if(i == 3 || pesoActual == 0) return 0;
    
    // no meter el objeto
    int noMeter = mochila(i + 1, pesoActual);
    
    // si cabe, probar metiendolo
    int meter = 0;
    if(pesos[i] <= pesoActual) {
        meter = valores[i] + mochila(i + 1, pesoActual - pesos[i]);
    }
    
    return (meter > noMeter) ? meter : noMeter;
}

int main() {
    cout << "Valor maximo que cabe en la mochila: " << mochila(0, maxPeso) << endl;
    return 0;
}
