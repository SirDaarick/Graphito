#include <stdio.h>
#include <string.h>

/**
 * Reverses a string read from standard input and prints the result.
 */
static void reverse_in_place(char *text) {
    size_t left = 0;
    size_t right = strlen(text);

    if (right == 0) {
        return;
    }
    --right;

    while (left < right) {
        char temp = text[left];
        text[left] = text[right];
        text[right] = temp;
        ++left;
        --right;
    }
}

int main(void) {
    char buffer[100];

    if (scanf("%99s", buffer) != 1) {
        return 1;
    }

    reverse_in_place(buffer);
    printf("%s\n", buffer);
    return 0;
}
