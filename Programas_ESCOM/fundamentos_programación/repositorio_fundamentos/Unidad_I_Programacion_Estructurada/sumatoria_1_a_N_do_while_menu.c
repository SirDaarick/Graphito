#include <stdio.h>

int main() {
    int opc, num, total;
    
    do {
        total = 0;
        printf("\n1. Calcular suma\n2. Salir\nOpcion: ");
        scanf("%d", &opc);
        
        if(opc == 1) {
            printf("Ingresa n: ");
            scanf("%d", &num);
            int j = 1;
            do {
                total += j;
                j++;
            } while(j <= num);
            printf("La suma dio: %d\n", total);
        }
    } while(opc != 2);
    
    return 0;
}
