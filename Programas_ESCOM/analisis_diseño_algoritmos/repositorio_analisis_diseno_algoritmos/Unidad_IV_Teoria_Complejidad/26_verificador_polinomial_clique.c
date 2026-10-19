#include <stdio.h>

// verificador polinomial para saber si un certificado es una Clique
int grafo[4][4] = {
    {0, 1, 1, 1},
    {1, 0, 1, 0},
    {1, 1, 0, 1},
    {1, 0, 1, 0}
};

int main() {
    int candidatos[3] = {0, 1, 2}; // certificado a verificar de tamano 3
    int tam = 3;
    int esValido = 1;

    for(int i = 0; i < tam; i++) {
        for(int j = i + 1; j < tam; j++) {
            int u = candidatos[i];
            int v = candidatos[j];
            if(grafo[u][v] == 0) {
                esValido = 0;
                break;
            }
        }
    }

    if(esValido) printf("Certificado verificado en O(k^2): Es una Clique valida\n");
    else printf("No es una Clique\n");
    return 0;
}
