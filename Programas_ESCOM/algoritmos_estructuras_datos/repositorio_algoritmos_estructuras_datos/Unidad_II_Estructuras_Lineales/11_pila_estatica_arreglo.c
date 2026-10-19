#include <stdio.h>
#define MAX 5

int pila[MAX];
int tope = -1;

void push(int x) {
    if(tope == MAX - 1) printf("Pila llena\n");
    else pila[++tope] = x;
}

int pop() {
    if(tope == -1) {
        printf("Pila vacia\n");
        return -1;
    }
    return pila[tope--];
}

int main() {
    push(10);
    push(20);
    push(30);
    printf("Sacado de la pila: %d\n", pop());
    printf("Sacado de la pila: %d\n", pop());
    return 0;
}
