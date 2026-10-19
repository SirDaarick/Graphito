#include <stdio.h>

int factorialIterativo(int n) {
    int res = 1;
    for(int i = 1; i <= n; i++) {
        res = res * i;
    }
    return res;
}

int main() {
    int num;
    printf("Dame el numero: ");
    scanf("%d", &num);
    printf("Factorial de %d es: %d\n", num, factorialIterativo(num));
    return 0;
}
