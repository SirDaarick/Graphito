#include <iostream>
using namespace std;

int particion(int a[], int l, int r) {
    int pivote = a[r];
    int i = l;
    for(int j = l; j < r; j++) {
        if(a[j] <= pivote) {
            int aux = a[i]; a[i] = a[j]; a[j] = aux;
            i++;
        }
    }
    int aux = a[i]; a[i] = a[r]; a[r] = aux;
    return i;
}

// divide y venceras para hallar el k-esimo menor
int quickSelect(int a[], int l, int r, int k) {
    if(l == r) return a[l];
    int p = particion(a, l, r);
    if(p == k) return a[p];
    else if(p > k) return quickSelect(a, l, p - 1, k);
    else return quickSelect(a, p + 1, r, k);
}

int main() {
    int arr[7] = {12, 3, 5, 7, 4, 19, 26};
    int k = 3; // buscamos el elemento con indice 3 ordenado
    cout << "El elemento en la posicion " << k << " (mediana/estadistico) es: " 
         << quickSelect(arr, 0, 6, k) << endl;
    return 0;
}
