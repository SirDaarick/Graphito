#include <iostream>
using namespace std;

int main() {
    int ordenados[8] = {2, 5, 8, 12, 16, 23, 38, 56};
    int n = 8, valor = 23;
    int inf = 0, sup = n - 1;
    int encontrado = -1;

    // ciclo binario dividiendo a la mitad
    while(inf <= sup) {
        int med = (inf + sup) / 2;
        if(ordenados[med] == valor) {
            encontrado = med;
            break;
        }
        if(ordenados[med] < valor) inf = med + 1;
        else sup = med - 1;
    }

    if(encontrado != -1) cout << "Valor " << valor << " hallado en casilla: " << encontrado << endl;
    else cout << "No se encontro" << endl;
    return 0;
}
