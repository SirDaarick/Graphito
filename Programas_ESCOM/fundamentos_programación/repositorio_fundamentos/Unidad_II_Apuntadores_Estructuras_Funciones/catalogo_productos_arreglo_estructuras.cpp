#include <iostream>
using namespace std;

struct Producto {
    char nombre[20];
    float precio;
    int stock;
};

int main() {
    struct Producto tienda[3];
    
    for(int i = 0; i < 3; i++) {
        cout << "Producto " << i + 1 << " nombre: ";
        cin >> tienda[i].nombre;
        cout << "Precio: ";
        cin >> tienda[i].precio;
        cout << "Stock: ";
        cin >> tienda[i].stock;
    }
    
    cout << "\n--- LISTA REGISTRADA ---" << endl;
    for(int i = 0; i < 3; i++) {
        cout << tienda[i].nombre << " cuesta $" << tienda[i].precio << " (Quedan: " << tienda[i].stock << ")" << endl;
    }
    return 0;
}
