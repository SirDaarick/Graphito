#include <stdio.h>
int main(void) {
    int m, q, y, s = 0;
    scanf("%d", &m);
    for (q = 0; q < m; q++) {
        scanf("%d", &y);
        s += y;
    }
    printf("%d\n", s);
    return 0;
}
