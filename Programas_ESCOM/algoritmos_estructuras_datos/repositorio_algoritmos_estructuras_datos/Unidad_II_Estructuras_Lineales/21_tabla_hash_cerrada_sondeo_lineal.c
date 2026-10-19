#include <stdio.h>
#define TAM 7

int tabla[TAM];

int fHash(int clave) { return clave % TAM; }

void insertar(int clave) {
    int pos = fHash(clave);
    // sondeo lineal si esta ocupado
    while(tabla[pos] != -1) {
        pos = (pos + 1) % TAM;
    }
    tabla[pos] = clave;
}

int main() {
    for(int i = 0; i < TAM; i++) tabla[i] = -1; // -1 significa vacio
    
    insertar(10); // 10 % 7 = 3
    insertar(17); // colision en 3, salta a 4
    insertar(24); // colision en 3 y 4, salta a 5
    
    printf("Tabla hash cerrada:\n");
    for(int j = 0; j < TAM; j++) printf("[%d]: %d\n", j, tabla[j]);
    return 0;
}
