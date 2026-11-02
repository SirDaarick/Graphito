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


#include <stdio.h>
int main() {
    int numeros[]={64, 34, 25, 12, 22, 11, 90};
    int n=sizeof(numeros)/sizeof(numeros[0]);
    int aux;

    for (int i=0; i<n-1; i++) {
        for (int j=0; j<n-i-1; j++) {
            if (numeros[j]>numeros[j+1]){
                aux=numeros[j];
                numeros[j]=numeros[j + 1];
                numeros[j+1]=aux;
            }
        }
    }

    printf("numeros ordenados de menor a mayor:\n");
    for (int i=0; i<n; i++) {
        printf("%d ", numeros[i]);
    }
    return 0;
}


#include <stdio.h>

int main() {
    int tamano;
    int a[50];
    int x;
    int pos=-1;

    printf("dame la cantidad: ");
    scanf("%d", &tamano);

    for(int i=0; i<tamano; i++){
        printf("numero: ");
        scanf("%d", &a[i]);
    }

    printf("cual buscas: ");
    scanf("%d", &x);

    for(int i=0; i<tamano; i++){
        if(a[i]==x){
            pos=i;
        }
    }

    if(pos!=-1){
        printf("si esta en la posicion %d\n", pos);
    }
    else{
        printf("no existe\n");
    }

    return 0;
}