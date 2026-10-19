#include <iostream>
using namespace std;

int arr[6] = {38, 27, 43, 3, 9, 82};

void merge(int inicio, int medio, int fin) {
    int temp[100]; // arreglo auxiliar grande
    int i = inicio, j = medio + 1, k = inicio;
    
    while(i <= medio && j <= fin) {
        if(arr[i] <= arr[j]) {
            temp[k++] = arr[i++];
        } else {
            temp[k++] = arr[j++];
        }
    }
    while(i <= medio) temp[k++] = arr[i++];
    while(j <= fin) temp[k++] = arr[j++];
    
    for(int p = inicio; p <= fin; p++) {
        arr[p] = temp[p];
    }
}

void mergeSort(int l, int r) {
    if(l < r) {
        int m = (l + r) / 2;
        mergeSort(l, m);
        mergeSort(m + 1, r);
        merge(l, m, r);
    }
}

int main() {
    mergeSort(0, 5);
    cout << "Merge Sort terminado: ";
    for(int i = 0; i < 6; i++) cout << arr[i] << " ";
    cout << endl;
    return 0;
}
