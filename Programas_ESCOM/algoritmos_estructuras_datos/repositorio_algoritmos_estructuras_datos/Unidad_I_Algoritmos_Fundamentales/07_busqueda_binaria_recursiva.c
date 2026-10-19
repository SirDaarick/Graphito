#include <stdio.h>

int busquedaBinariaRec(int a[], int ini, int fin, int x) {
    if(ini > fin) return -1; // caso base si no esta
    
    int med = (ini + fin) / 2;
    if(a[med] == x) return med;
    if(a[med] > x) return busquedaBinariaRec(a, ini, med - 1, x);
    return busquedaBinariaRec(a, med + 1, fin, x);
}

int main() {
    int vector[6] = {10, 20, 30, 40, 50, 60};
    int dato = 50;
    int r = busquedaBinariaRec(vector, 0, 5, dato);
    
    if(r != -1) printf("Encontrado recursivamente en posicion %d\n", r);
    else printf("No existe\n");
    return 0;
}
