#include <stdio.h>

int main() {
    FILE *arch = fopen("alumnos.txt", "w");
    
    if(arch == NULL) {
        printf("No se pudo crear el archivo\n");
        return 1;
    }
    
    fprintf(arch, "Registro de Alumnos\n");
    fprintf(arch, "Rodrigo 9.5\n");
    fprintf(arch, "Mariana 8.0\n");
    
    fclose(arch);
    printf("Archivo guardado con exito\n");
    return 0;
}
