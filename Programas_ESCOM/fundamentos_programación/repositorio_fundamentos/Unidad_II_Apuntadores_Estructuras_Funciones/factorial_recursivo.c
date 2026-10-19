#include <stdio.h>

int factorialRecursivo(int n) {
    if(n == 0 || n == 1) {
        return 1;
    }
    return n * factorialRecursivo(n - 1);
}

int main() {
    int num;
    printf("Ingresa valor: ");
    scanf("%d", &num);
    printf("El factorial recursivo es: %d\n", factorialRecursivo(num));
    return 0;
}
