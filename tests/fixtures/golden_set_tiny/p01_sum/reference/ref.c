#include <stdio.h>
int main(void) {
    int n, i, x, sum = 0;
    scanf("%d", &n);
    for (i = 0; i < n; i++) {
        scanf("%d", &x);
        sum += x;
    }
    printf("%d\n", sum);
    return 0;
}
