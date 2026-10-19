#include <iostream>
#include <stdio.h>
using namespace std;

int main() {
    FILE *archivo;
    char bufer[100];
    
    archivo = fopen("alumnos.txt", "r");
    
    if(archivo != NULL) {
        cout << "Leyendo archivo:" << endl;
        while(fgets(bufer, 100, archivo) != NULL) {
            cout << bufer;
        }
        fclose(archivo);
    } else {
        cout << "Error: no existe el archivo alumnos.txt" << endl;
    }
    return 0;
}
