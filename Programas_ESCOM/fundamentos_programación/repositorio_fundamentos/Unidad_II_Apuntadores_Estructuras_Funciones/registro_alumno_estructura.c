#include <stdio.h>

struct Alumno {
    char nombre[30];
    int boleta;
    float promedio;
};

int main() {
    struct Alumno a1;
    
    printf("Nombre: ");
    scanf("%s", a1.nombre);
    printf("Boleta: ");
    scanf("%d", &a1.boleta);
    printf("Promedio: ");
    scanf("%f", &a1.promedio);
    
    printf("\nDatos capturados:\n");
    printf("Nombre: %s | Boleta: %d | Promedio: %.2f\n", a1.nombre, a1.boleta, a1.promedio);
    return 0;
}
