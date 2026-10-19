#include <iostream>
#include <cstdlib>
#include <ctime>
using namespace std;

int main() {
    srand(time(NULL));
    int totalPuntos = 100000;
    int dentroCirculo = 0;

    for(int i = 0; i < totalPuntos; i++) {
        double x = (double)rand() / RAND_MAX;
        double y = (double)rand() / RAND_MAX;

        if(x * x + y * y <= 1.0) {
            dentroCirculo++;
        }
    }

    double piAprox = 4.0 * dentroCirculo / totalPuntos;
    cout << "Aproximacion de Pi con Monte Carlo (" << totalPuntos << " puntos): " << piAprox << endl;
    return 0;
}
