#include <stdio.h>
int main(void) {
    int n, i, x, max;
    scanf("%d", &n);
    scanf("%d", &max);
    for (i = 1; i < n; i++) {
        scanf("%d", &x);
        if (x > max) max = x;
    }
    printf("%d\n", max);
    return 0;
}
