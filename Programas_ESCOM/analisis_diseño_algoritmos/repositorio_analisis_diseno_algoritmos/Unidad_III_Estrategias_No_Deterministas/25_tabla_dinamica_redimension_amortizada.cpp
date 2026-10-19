#include <iostream>
using namespace std;

// tabla dinamica que se duplica cuando se llena
int main() {
    int capacidad = 1;
    int tam = 0;
    int *tabla = new int[capacidad];
    int copiasTotales = 0;

    for(int i = 1; i <= 8; i++) {
        if(tam == capacidad) {
            capacidad *= 2;
            int *nueva = new int[capacidad];
            for(int j = 0; j < tam; j++) {
                nueva[j] = tabla[j];
                copiasTotales++;
            }
            delete[] tabla;
            tabla = nueva;
        }
        tabla[tam++] = i;
    }

    cout << "Elementos insertados: " << tam << endl;
    cout << "Capacidad final de la tabla: " << capacidad << endl;
    cout << "Total de copias realizadas (amortizado O(1)): " << copiasTotales << endl;
    delete[] tabla;
    return 0;
}
