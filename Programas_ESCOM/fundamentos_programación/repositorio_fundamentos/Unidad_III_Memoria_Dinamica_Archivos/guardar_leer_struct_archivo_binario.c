#include <stdio.h>

struct Jugador {
    char nick[20];
    int puntaje;
};

int main() {
    struct Jugador j1 = {"PlayerOne", 9999};
    struct Jugador leido;
    
    FILE *f1 = fopen("partida.dat", "wb");
    fwrite(&j1, sizeof(struct Jugador), 1, f1);
    fclose(f1);
    printf("Guardado en binario\n");
    
    FILE *f2 = fopen("partida.dat", "rb");
    fread(&leido, sizeof(struct Jugador), 1, f2);
    fclose(f2);
    
    printf("Leido del binario: Jugador=%s, Score=%d\n", leido.nick, leido.puntaje);
    return 0;
}
