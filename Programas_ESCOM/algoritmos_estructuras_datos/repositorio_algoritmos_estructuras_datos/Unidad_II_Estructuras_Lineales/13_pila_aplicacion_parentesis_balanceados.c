#include <stdio.h>
#include <string.h>

char stack[50];
int top = -1;

void push(char c) { stack[++top] = c; }
char pop() { return (top == -1) ? '\0' : stack[top--]; }

int main() {
    char expresion[50] = "(a+b)*(c-(d/e))";
    int balanceado = 1;

    for(int i = 0; i < strlen(expresion); i++) {
        if(expresion[i] == '(') push('(');
        else if(expresion[i] == ')') {
            if(pop() != '(') {
                balanceado = 0;
                break;
            }
        }
    }
    if(top != -1) balanceado = 0;

    if(balanceado) printf("Expresion: %s -> Parentesis correctos\n", expresion);
    else printf("Expresion: %s -> Parentesis incorrectos\n", expresion);
    return 0;
}
