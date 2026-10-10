#include <stdio.h>
#include <string.h>
int main(void) {
    char txt[100];
    int p, m;
    scanf("%99s", txt);
    m = strlen(txt);
    for (p = m - 1; p >= 0; p--) putchar(txt[p]);
    putchar('\n');
    return 0;
}
