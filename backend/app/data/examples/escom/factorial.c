#include <stdio.h>
int main(){
    int numero;
    int resultado = 1;
    printf("Ingresa un numero que no sea negativo para calcular el factorial: ");
    scanf("%d",&numero);

    if(numero < 0){
        printf("El numero no puede ser negativo.\n");
    }else{
        for(int i = 1; i<=numero; i++) {
            resultado = resultado * i;
        }
        printf("El factorial de %d es: %d\n", numero, resultado);
    }
    return 0;
}
