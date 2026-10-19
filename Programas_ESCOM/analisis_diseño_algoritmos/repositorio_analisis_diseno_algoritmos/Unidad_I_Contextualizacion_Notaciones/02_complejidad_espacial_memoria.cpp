#include <iostream>
using namespace std;

// vemos cuanta memoria ocupa un arreglo estatico vs uno dinamico
int main() {
    int tam = 5;
    int estatico[5] = {1, 2, 3, 4, 5}; // memoria en el stack
    int *dinamico = new int[tam];      // memoria en el heap

    for(int i = 0; i < tam; i++) {
        dinamico[i] = estatico[i] * 10;
    }

    cout << "Bytes del arreglo estatico: " << sizeof(estatico) << endl;
    cout << "Bytes del puntero dinamico: " << sizeof(dinamico) << endl;

    for(int j = 0; j < tam; j++) {
        cout << dinamico[j] << " ";
    }
    cout << endl;
    delete[] dinamico;
    return 0;
}
