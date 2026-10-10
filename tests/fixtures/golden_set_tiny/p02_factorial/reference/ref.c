#include <stdio.h>
long long fact(int n) {
    long long r = 1;
    int i;
    for (i = 2; i <= n; i++) r *= i;
    return r;
}
int main(void) {
    int n;
    scanf("%d", &n);
    printf("%lld\n", fact(n));
    return 0;
}
