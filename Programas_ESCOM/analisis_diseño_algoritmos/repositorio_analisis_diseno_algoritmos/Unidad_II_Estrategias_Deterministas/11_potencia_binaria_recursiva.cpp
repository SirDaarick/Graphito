#include <iostream>
using namespace std;

// potencia rapida con recursion divide y venceras
long long potenciaRec(long long base, int exp) {
    if(exp == 0) return 1;
    long long mitad = potenciaRec(base, exp / 2);
    if(exp % 2 == 0) return mitad * mitad;
    else return base * mitad * mitad;
}

int main() {
    cout << "2^10 recursivo: " << potenciaRec(2, 10) << endl;
    return 0;
}
