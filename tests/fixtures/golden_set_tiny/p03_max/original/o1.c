#include <stdio.h>
int main() {
    int a[50], n, i, mayor;
    scanf("%d", &n);
    for (i = 0; i < n; i++) scanf("%d", &a[i]);
    mayor = a[0];
    for (i = 1; i < n; i++)
        if (a[i] > mayor) mayor = a[i];
    printf("El mayor es %d\n", mayor);
    return 0;
}
