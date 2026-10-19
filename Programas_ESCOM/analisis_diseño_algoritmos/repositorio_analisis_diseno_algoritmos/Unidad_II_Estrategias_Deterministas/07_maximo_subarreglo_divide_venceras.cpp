#include <iostream>
using namespace std;

int cruzado(int arr[], int l, int m, int h) {
    int suma = 0;
    int izqSuma = -99999;
    for(int i = m; i >= l; i--) {
        suma += arr[i];
        if(suma > izqSuma) izqSuma = suma;
    }

    suma = 0;
    int derSuma = -99999;
    for(int i = m + 1; i <= h; i++) {
        suma += arr[i];
        if(suma > derSuma) derSuma = suma;
    }
    return izqSuma + derSuma;
}

int maxSubArrayRec(int arr[], int l, int h) {
    if(l == h) return arr[l];
    int m = (l + h) / 2;

    int izq = maxSubArrayRec(arr, l, m);
    int der = maxSubArrayRec(arr, m + 1, h);
    int cruce = cruzado(arr, l, m, h);

    int mayor = (izq > der) ? izq : der;
    return (mayor > cruce) ? mayor : cruce;
}

int main() {
    int datos[8] = {-2, -5, 6, -2, -3, 1, 5, -6};
    cout << "Maximo subarreglo (Divide y Venceras): " << maxSubArrayRec(datos, 0, 7) << endl;
    return 0;
}
