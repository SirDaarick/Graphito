#include <stdio.h>
int main(void) {
    int t, w, z, big;
    scanf("%d", &t);
    scanf("%d", &big);
    for (w = 1; w < t; w++) {
        scanf("%d", &z);
        if (z > big) big = z;
    }
    printf("%d\n", big);
    return 0;
}
