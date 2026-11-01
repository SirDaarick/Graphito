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
