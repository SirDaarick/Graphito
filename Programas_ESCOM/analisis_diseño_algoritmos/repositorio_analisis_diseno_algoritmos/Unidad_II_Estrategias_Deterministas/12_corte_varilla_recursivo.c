#include <stdio.h>

int precios[9] = {0, 1, 5, 8, 9, 10, 17, 17, 20};

// corte de varilla por recursion pura (lento exponencial)
int corteRecursivo(int n) {
    if(n <= 0) return 0;
    int maxVal = -1;
    for(int i = 1; i <= n; i++) {
        int actual = precios[i] + corteRecursivo(n - i);
        if(actual > maxVal) maxVal = actual;
    }
    return maxVal;
}

int main() {
    int longitud = 4;
    printf("Ganancia maxima corte varilla (recursivo) tam %d: %d\n", longitud, corteRecursivo(longitud));
    return 0;
}
