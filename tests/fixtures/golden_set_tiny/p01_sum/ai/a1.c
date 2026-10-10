#include <stdio.h>

/**
 * Reads N integers from standard input and prints their sum.
 */
int main(void) {
    int count = 0;
    long long total = 0;

    if (scanf("%d", &count) != 1) {
        return 1;
    }

    for (int index = 0; index < count; ++index) {
        int value = 0;
        if (scanf("%d", &value) != 1) {
            return 1;
        }
        total += value;
    }

    printf("%lld\n", total);
    return 0;
}
