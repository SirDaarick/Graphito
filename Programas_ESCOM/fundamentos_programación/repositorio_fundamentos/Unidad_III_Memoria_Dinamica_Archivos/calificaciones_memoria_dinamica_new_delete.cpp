#include <iostream>
using namespace std;

int main() {
    int n;
    cout << "Cuantas calificaciones son?: ";
    cin >> n;
    
    float *califs = new float[n];
    
    for(int i = 0; i < n; i++) {
        cout << "Calificacion " << i + 1 << ": ";
        cin >> califs[i];
    }
    
    cout << "Notas registradas correctamente" << endl;
    delete[] califs;
    return 0;
}
