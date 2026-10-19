#include <iostream>
using namespace std;

void duplicar(int &numero) {
    numero = numero * 2;
}

int main() {
    int n = 7;
    cout << "Antes: " << n << endl;
    duplicar(n);
    cout << "Despues: " << n << endl;
    return 0;
}
