#include <iostream>
using namespace std;

int main() {
    int pesos[4] = {0, 2, 3, 4};
    int valores[4] = {0, 3, 4, 5};
    int cap = 5;
    int dp[4][6];

    for(int i = 0; i <= 3; i++) {
        for(int w = 0; w <= cap; w++) {
            if(i == 0 || w == 0) {
                dp[i][w] = 0;
            } else if(pesos[i] <= w) {
                int incluir = valores[i] + dp[i - 1][w - pesos[i]];
                int excluir = dp[i - 1][w];
                dp[i][w] = (incluir > excluir) ? incluir : excluir;
            } else {
                dp[i][w] = dp[i - 1][w];
            }
        }
    }

    cout << "Maximo valor en la mochila con DP: " << dp[3][cap] << endl;
    return 0;
}
