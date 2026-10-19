#include <iostream>
using namespace std;

int main() {
    int datos[5] = {29, 10, 14, 37, 13};
    int n = 5;
    
    // ordenamiento por seleccion
    for(int i = 0; i < n - 1; i++) {
        int min_idx = i;
        for(int j = i + 1; j < n; j++) {
            if(datos[j] < datos[min_idx]) {
                min_idx = j;
            }
        }
        int aux = datos[min_idx];
        datos[min_idx] = datos[i];
        datos[i] = aux;
    }
    
    cout << "Arreglo ordenado por seleccion: ";
    for(int k = 0; k < n; k++) {
        cout << datos[k] << " ";
    }
    cout << endl;
    return 0;
}
