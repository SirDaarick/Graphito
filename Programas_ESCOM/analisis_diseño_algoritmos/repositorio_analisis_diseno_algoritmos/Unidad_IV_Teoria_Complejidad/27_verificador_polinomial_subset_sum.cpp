#include <iostream>
using namespace std;

// problema de la suma de subconjuntos: verificador en tiempo lineal O(k)
int main() {
    int objetivo = 25;
    int certificado[3] = {5, 12, 8}; // subconjunto propuesto
    int tam = 3;
    int suma = 0;

    for(int i = 0; i < tam; i++) {
        suma += certificado[i];
    }

    if(suma == objetivo) {
        cout << "Certificado correcto para Subset-Sum! La suma dio: " << suma << endl;
    } else {
        cout << "Certificado incorrecto" << endl;
    }
    return 0;
}
