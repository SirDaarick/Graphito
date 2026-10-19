#include <stdio.h>
#include <time.h>

int main() {
    clock_t inicio, fin;
    double tiempoTotal;
    long long suma = 0;
    long long n = 10000000;

    // medimos cuanto tarda en correr el ciclo
    inicio = clock();
    for(long long i = 0; i < n; i++) {
        suma += i;
    }
    fin = clock();

    tiempoTotal = (double)(fin - inicio) / CLOCKS_PER_SEC;
    printf("Suma: %lld\n", suma);
    printf("Tiempo de ejecucion: %f segundos\n", tiempoTotal);
    return 0;
}
