#include <stdio.h>
long long calc(int k) {
    long long res = 1;
    int j;
    for (j = 2; j <= k; j++) res *= j;
    return res;
}
int main(void) {
    int k;
    scanf("%d", &k);
    printf("%lld\n", calc(k));
    return 0;
}
