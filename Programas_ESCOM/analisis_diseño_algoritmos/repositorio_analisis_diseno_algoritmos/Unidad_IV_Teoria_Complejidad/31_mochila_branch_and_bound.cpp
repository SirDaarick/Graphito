#include <iostream>
using namespace std;

int pesos[3] = {2, 3, 4};
int valores[3] = {3, 4, 5};
int capacidad = 5;
int mejorValor = 0;

// poda por ramificacion y acotamiento (branch and bound)
void branchAndBound(int idx, int pesoActual, int valorActual) {
    if(pesoActual > capacidad) return; // poda si se pasa del peso

    if(valorActual > mejorValor) {
        mejorValor = valorActual;
    }

    if(idx == 3) return;

    // rama 1: incluir objeto
    branchAndBound(idx + 1, pesoActual + pesos[idx], valorActual + valores[idx]);
    // rama 2: excluir objeto
    branchAndBound(idx + 1, pesoActual, valorActual);
}

int main() {
    branchAndBound(0, 0, 0);
    cout << "Mejor valor encontrado con Branch and Bound: " << mejorValor << endl;
    return 0;
}
