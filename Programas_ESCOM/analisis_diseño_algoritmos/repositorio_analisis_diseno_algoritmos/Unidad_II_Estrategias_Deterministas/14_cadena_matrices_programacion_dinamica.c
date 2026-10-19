#include <stdio.h>
#define INF 999999

int p[5] = {10, 20, 30, 40, 30}; // dimensiones de las 4 matrices
int m[5][5];

int main() {
    int n = 4; // 4 matrices

    for(int i = 1; i <= n; i++) m[i][i] = 0;

    for(int L = 2; L <= n; L++) {
        for(int i = 1; i <= n - L + 1; i++) {
            int j = i + L - 1;
            m[i][j] = INF;
            for(int k = i; k <= j - 1; k++) {
                int costo = m[i][k] + m[k + 1][j] + p[i - 1] * p[k] * p[j];
                if(costo < m[i][j]) m[i][j] = costo;
            }
        }
    }

    printf("Minimo costo de multiplicaciones de cadena de matrices: %d\n", m[1][n]);
    return 0;
}
