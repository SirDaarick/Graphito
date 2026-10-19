#include <stdio.h>

void intercambiar(int *ptr1, int *ptr2) {
    int temp = *ptr1;
    *ptr1 = *ptr2;
    *ptr2 = temp;
}

int main() {
    int x = 15, y = 80;
    printf("Originales: x=%d, y=%d\n", x, y);
    intercambiar(&x, &y);
    printf("Cambiados: x=%d, y=%d\n", x, y);
    return 0;
}
