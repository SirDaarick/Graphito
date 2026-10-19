#include <stdio.h>

// las actividades ya vienen ordenadas por tiempo de fin
int inicio[6] = {1, 3, 0, 5, 8, 5};
int fin[6]    = {2, 4, 6, 7, 9, 9};

int main() {
    int n = 6;
    printf("Actividades seleccionadas (greedy):\n");

    int i = 0;
    printf("Actividad %d (inicio %d, fin %d)\n", i, inicio[i], fin[i]);

    for(int j = 1; j < n; j++) {
        if(inicio[j] >= fin[i]) {
            printf("Actividad %d (inicio %d, fin %d)\n", j, inicio[j], fin[j]);
            i = j;
        }
    }
    return 0;
}
