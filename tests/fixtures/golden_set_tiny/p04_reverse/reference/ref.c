#include <stdio.h>
#include <string.h>
int main(void) {
    char s[100];
    int i, n;
    scanf("%99s", s);
    n = strlen(s);
    for (i = n - 1; i >= 0; i--) putchar(s[i]);
    putchar('\n');
    return 0;
}
