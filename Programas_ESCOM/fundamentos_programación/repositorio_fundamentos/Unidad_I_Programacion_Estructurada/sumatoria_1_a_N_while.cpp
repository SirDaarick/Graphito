#include <iostream>
using namespace std;

int main() {
    int limite;
    int acum = 0;
    int contador = 1;
    
    cout << "Ingresa el limite: ";
    cin >> limite;
    
    // ciclo while hasta llegar al tope
    while(contador <= limite) {
        acum += contador;
        contador++;
    }
    
    cout << "Total acumulado: " << acum << endl;
    return 0;
}
