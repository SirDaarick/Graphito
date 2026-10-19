#include <stdio.h>
#include <stdlib.h>

int n, suma = 0; // variables para la operacion

int main() {
    printf("Hasta que numero quieres sumar?: ");
    scanf("%d", &n);
    
    // sumamos todo con el for
    for(int i = 1; i <= n; i++) {
        suma = suma + i;
    }
    
    printf("El resultado de la suma es: %d\n", suma);
    system("pause"); // para que no se cierre la consola
    return 0;
}
