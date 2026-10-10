#include <stdio.h>
#include <string.h>
int main() {
    char palabra[64], inv[64];
    int len, k;
    gets(palabra);
    len = strlen(palabra);
    for (k = 0; k < len; k++) inv[k] = palabra[len - 1 - k];
    inv[len] = '\0';
    printf("%s\n", inv);
    return 0;
}
