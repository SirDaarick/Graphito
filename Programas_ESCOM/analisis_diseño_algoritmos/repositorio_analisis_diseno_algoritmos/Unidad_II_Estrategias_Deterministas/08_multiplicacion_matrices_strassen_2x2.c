#include <stdio.h>

// multiplicacion de strassen para matrices 2x2 usando 7 multiplicaciones
int main() {
    int A[2][2] = {{1, 3}, {7, 5}};
    int B[2][2] = {{6, 8}, {4, 2}};

    int m1 = (A[0][0] + A[1][1]) * (B[0][0] + B[1][1]);
    int m2 = (A[1][0] + A[1][1]) * B[0][0];
    int m3 = A[0][0] * (B[0][1] - B[1][1]);
    int m4 = A[1][1] * (B[1][0] - B[0][0]);
    int m5 = (A[0][0] + A[0][1]) * B[1][1];
    int m6 = (A[1][0] - A[0][0]) * (B[0][0] + B[0][1]);
    int m7 = (A[0][1] - A[1][1]) * (B[1][0] + B[1][1]);

    int C[2][2];
    C[0][0] = m1 + m4 - m5 + m7;
    C[0][1] = m3 + m5;
    C[1][0] = m2 + m4;
    C[1][1] = m1 - m2 + m3 + m6;

    printf("Resultado matriz Strassen 2x2:\n");
    printf("%d %d\n%d %d\n", C[0][0], C[0][1], C[1][0], C[1][1]);
    return 0;
}
