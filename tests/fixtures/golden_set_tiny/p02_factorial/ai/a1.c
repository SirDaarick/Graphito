#include <stdio.h>

/**
 * Computes the factorial of a non-negative integer iteratively.
 */
static unsigned long long factorial(int n) {
    unsigned long long result = 1ULL;
    for (int i = 2; i <= n; ++i) {
        result *= (unsigned long long)i;
    }
    return result;
}

int main(void) {
    int n = 0;
    if (scanf("%d", &n) != 1 || n < 0) {
        return 1;
    }
    printf("%llu\n", factorial(n));
    return 0;
}
