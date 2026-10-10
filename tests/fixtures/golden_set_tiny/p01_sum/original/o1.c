#include <stdio.h>
int main() {
    int cuantos, total = 0, v;
    scanf("%d", &cuantos);
    while (cuantos--) {
        scanf("%d", &v);
        total = total + v;
    }
    printf("Suma: %d\n", total);
}
