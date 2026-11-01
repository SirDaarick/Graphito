#include <stdio.h>
#include <string.h>

void u(int n, char *s) {
    for (int i = 0; s[i]; i++) {
        if (s[i] == ' ') printf("%d", n);
        else putchar(s[i]);
    }
}

int main() {
    char s[1000];
    int n;
    printf("Unesite tekst: ");
    fgets(s, 1000, stdin);
    s[strcspn(s, "\n")] = 0;
    printf("Unesite broj: ");
    scanf("%d", &n);
    u(n, s);
    putchar('\n');
    return 0;
}