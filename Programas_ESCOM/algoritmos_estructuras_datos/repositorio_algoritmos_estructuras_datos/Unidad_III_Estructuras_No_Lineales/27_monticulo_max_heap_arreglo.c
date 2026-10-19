#include <stdio.h>

int heap[10];
int tam = 0;

void insertarHeap(int v) {
    int i = tam++;
    heap[i] = v;
    // flotar hacia arriba
    while(i != 0 && heap[(i - 1) / 2] < heap[i]) {
        int temp = heap[i];
        heap[i] = heap[(i - 1) / 2];
        heap[(i - 1) / 2] = temp;
        i = (i - 1) / 2;
    }
}

int main() {
    insertarHeap(10);
    insertarHeap(30);
    insertarHeap(20);
    insertarHeap(40);

    printf("Monticulo Max-Heap (la raiz siempre es la mayor): %d\n", heap[0]);
    printf("Elementos del heap: ");
    for(int i = 0; i < tam; i++) printf("%d ", heap[i]);
    printf("\n");
    return 0;
}
