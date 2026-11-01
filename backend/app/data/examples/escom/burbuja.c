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
