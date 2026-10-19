#include <stdio.h>

int main() {
    int m1[2][2], m2[2][2], res[2][2];
    
    printf("Llenar primera matriz:\n");
    for(int i = 0; i < 2; i++) {
        for(int j = 0; j < 2; j++) {
            printf("M1[%d][%d]: ", i, j);
            scanf("%d", &m1[i][j]);
        }
    }
    
    printf("Llenar segunda matriz:\n");
    for(int i = 0; i < 2; i++) {
        for(int j = 0; j < 2; j++) {
            printf("M2[%d][%d]: ", i, j);
            scanf("%d", &m2[i][j]);
            res[i][j] = m1[i][j] + m2[i][j];
        }
    }
    
    printf("Matriz resultante:\n");
    for(int i = 0; i < 2; i++) {
        for(int j = 0; j < 2; j++) {
            printf("%d ", res[i][j]);
        }
        printf("\n");
    }
    return 0;
}
