#include <iostream>
using namespace std;

int main() {
    int monedas[5] = {20, 10, 5, 2, 1}; // ordenadas de mayor a menor
    int cambio = 47;
    int totalMonedas = 0;

    cout << "Cambio para $" << cambio << ":" << endl;
    for(int i = 0; i < 5; i++) {
        while(cambio >= monedas[i]) {
            cambio -= monedas[i];
            totalMonedas++;
            cout << "Moneda de $" << monedas[i] << endl;
        }
    }
    cout << "Total de monedas usadas: " << totalMonedas << endl;
    return 0;
}
