#include <stdio.h>
#include <stdlib.h>

int main() {
    int *arr;
    arr = (int*) calloc(3, sizeof(int));
    
    arr[0] = 5;
    arr[1] = 10;
    arr[2] = 15;
    
    arr = (int*) realloc(arr, 5 * sizeof(int));
    arr[3] = 20;
    arr[4] = 25;
    
    for(int i = 0; i < 5; i++) {
        printf("%d ", arr[i]);
    }
    printf("\n");
    return 0;
}
