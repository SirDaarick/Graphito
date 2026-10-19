#include <stdio.h>

int pila[20];
int tope = -1;
int costoTotal = 0;

void push(int x) {
    pila[++tope] = x;
    costoTotal += 1;
}

void multipop(int k) {
    while(tope >= 0 && k > 0) {
        tope--;
        k--;
        costoTotal += 1; // cada pop cuesta 1 operacion
    }
}

int main() {
    // hacemos una secuencia de operaciones
    push(10);
    push(20);
    push(30);
    multipop(2);
    push(40);
    multipop(5);

    printf("Operaciones de pila completadas.\n");
    printf("Costo total real acumulado: %d operaciones\n", costoTotal);
    return 0;
}
