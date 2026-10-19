#include <iostream>
using namespace std;
#define TAM 4

int cola[TAM];
int frente = -1, final = -1;

void encolar(int x) {
    if((final + 1) % TAM == frente) {
        cout << "Cola circular llena" << endl;
        return;
    }
    if(frente == -1) frente = 0;
    final = (final + 1) % TAM;
    cola[final] = x;
}

void desencolar() {
    if(frente == -1) {
        cout << "Cola vacia" << endl;
        return;
    }
    cout << "Atendido: " << cola[frente] << endl;
    if(frente == final) frente = final = -1;
    else frente = (frente + 1) % TAM;
}

int main() {
    encolar(1);
    encolar(2);
    encolar(3);
    desencolar();
    encolar(4);
    desencolar();
    return 0;
}
