#include <stdio.h>
int factorial(int n) {
    if (n <= 1) return 1;
    return n * factorial(n - 1);
}
int main() {
    int num;
    printf("Numero: ");
    scanf("%d", &num);
    printf("El factorial es %d\n", factorial(num));
    return 0;
}
