#include <iostream>
using namespace std;

struct Elemento {
    string tarea;
    int prioridad; // mayor numero = mas importante
};

Elemento colaPrio[5];
int total = 0;

void encolarPrio(string t, int p) {
    if(total < 5) {
        colaPrio[total].tarea = t;
        colaPrio[total].prioridad = p;
        total++;
    }
}

void desencolarPrio() {
    if(total == 0) return;
    int mayor = 0;
    for(int i = 1; i < total; i++) {
        if(colaPrio[i].prioridad > colaPrio[mayor].prioridad) {
            mayor = i;
        }
    }
    cout << "Ejecutando tarea: " << colaPrio[mayor].tarea << " (Prioridad " << colaPrio[mayor].prioridad << ")" << endl;
    for(int j = mayor; j < total - 1; j++) {
        colaPrio[j] = colaPrio[j + 1];
    }
    total--;
}

int main() {
    encolarPrio("Reporte Word", 2);
    encolarPrio("Error Kernel", 10);
    encolarPrio("Imprimir PDF", 1);
    desencolarPrio();
    desencolarPrio();
    return 0;
}
