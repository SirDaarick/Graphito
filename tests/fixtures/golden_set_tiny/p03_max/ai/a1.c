#include <stdio.h>
#include <limits.h>

/**
 * Finds the maximum value among N integers read from standard input.
 */
int main(void) {
    int count = 0;
    int maximum = INT_MIN;

    if (scanf("%d", &count) != 1 || count <= 0) {
        return 1;
    }

    for (int i = 0; i < count; ++i) {
        int value = 0;
        if (scanf("%d", &value) != 1) {
            return 1;
        }
        if (value > maximum) {
            maximum = value;
        }
    }

    printf("%d\n", maximum);
    return 0;
}
