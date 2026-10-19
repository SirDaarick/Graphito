#include <iostream>
#include <string.h>
using namespace std;

int main() {
    char texto[50];
    char invertido[50];
    
    cout << "Escribe una palabra: ";
    cin >> texto;
    
    int tam = strlen(texto);
    int aux = 0;
    
    for(int i = tam - 1; i >= 0; i--) {
        invertido[aux] = texto[i];
        aux++;
    }
    invertido[aux] = '\0';
    
    cout << "Palabra al reves: " << invertido << endl;
    return 0;
}
