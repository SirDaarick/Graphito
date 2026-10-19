#include <stdio.h>

int tablero[4][4]; // tablero 4x4

int esSeguro(int fila, int col) {
    // revisamos hacia la izquierda
    for (int i = 0; i < col; i++) if (tablero[fila][i]) return 0;
    // diagonal superior izquierda
    for (int i = fila, j = col; i >= 0 && j >= 0; i--, j--) if (tablero[i][j]) return 0;
    // diagonal inferior izquierda
    for (int i = fila, j = col; j >= 0 && i < 4; i++, j--) if (tablero[i][j]) return 0;
    return 1;
}

int resolverReinas(int col) {
    if (col >= 4) return 1; // se colocaron las 4 reinas
    for (int i = 0; i < 4; i++) {
        if (esSeguro(i, col)) {
            tablero[i][col] = 1;
            if (resolverReinas(col + 1)) return 1;
            tablero[i][col] = 0; // backtracking quitamos reina
        }
    }
    return 0;
}

int main() {
    if (resolverReinas(0)) {
        printf("Solucion N-Reinas 4x4:\n");
        for (int i = 0; i < 4; i++) {
            for (int j = 0; j < 4; j++) printf("%d ", tablero[i][j]);
            printf("\n");
        }
    }
    return 0;
}
