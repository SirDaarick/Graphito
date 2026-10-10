#include <stdio.h>
#define MAX 100
int main() {
    int datos[MAX], k, j, acc = 0;
    scanf("%d", &k);
    for (j = 0; j < k; j++) scanf("%d", &datos[j]);
    for (j = 0; j < k; j++) acc += datos[j];
    printf("%d\n", acc);
    return 0;
}
