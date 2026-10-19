#include <iostream>
using namespace std;

int factorialWhile(int n) {
    int mult = 1;
    while(n > 1) {
        mult *= n;
        n--;
    }
    return mult;
}

int main() {
    int valor;
    cout << "Numero a calcular: ";
    cin >> valor;
    cout << "Resultado: " << factorialWhile(valor) << endl;
    return 0;
}
