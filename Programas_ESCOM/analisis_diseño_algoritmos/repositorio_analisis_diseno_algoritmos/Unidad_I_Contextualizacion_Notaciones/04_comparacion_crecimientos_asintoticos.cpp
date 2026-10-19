#include <iostream>
#include <cmath>
using namespace std;

// comparamos como crecen las funciones tipicas de orden
int main() {
    int valoresN[4] = {2, 4, 8, 16};

    cout << "n\tLog2(n)\tn\tn^2\t2^n" << endl;
    for(int i = 0; i < 4; i++) {
        int n = valoresN[i];
        cout << n << "\t" 
             << log2(n) << "\t" 
             << n << "\t" 
             << n * n << "\t" 
             << pow(2, n) << endl;
    }
    return 0;
}
