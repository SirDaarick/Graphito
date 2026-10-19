#include <stdio.h>
#include <string.h>

char X[10] = "AGGTAB";
char Y[10] = "GXTXAYB";
int dp[10][10];

int main() {
    int m = strlen(X);
    int n = strlen(Y);

    for(int i = 0; i <= m; i++) {
        for(int j = 0; j <= n; j++) {
            if(i == 0 || j == 0) dp[i][j] = 0;
            else if(X[i - 1] == Y[j - 1]) dp[i][j] = 1 + dp[i - 1][j - 1];
            else {
                int a = dp[i - 1][j];
                int b = dp[i][j - 1];
                dp[i][j] = (a > b) ? a : b;
            }
        }
    }

    printf("Longitud de la subsecuencia comun mas larga (LCS): %d\n", dp[m][n]);
    return 0;
}
