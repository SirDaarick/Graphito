#include <stdio.h>

// potencia rapida en O(log b) de forma iterativa
long long potenciaIterativa(long long base, int exp) {
    long long res = 1;
    while(exp > 0) {
        if(exp % 2 == 1) {
            res *= base;
        }
        base *= base;
        exp /= 2;
    }
    return res;
}

int main() {
    long long b = 3;
    int e = 13;
    printf("%lld elevado a la %d es: %lld\n", b, e, potenciaIterativa(b, e));
    return 0;
}
