# Repositorio General de Programas ESCOM

**Total de ejercicios compilados:** 124

---

## Materia: ALGORITMOS ESTRUCTURAS DATOS

### Carpeta: Unidad_III_Estructuras_No_Lineales

#### Archivo: `23_arbol_binario_recorridos_recursivo.c`
- **Ruta en carpeta:** `algoritmos_estructuras_datos/repositorio_algoritmos_estructuras_datos/Unidad_III_Estructuras_No_Lineales/23_arbol_binario_recorridos_recursivo.c`

```c
#include <stdio.h>
#include <stdlib.h>

struct NodoArbol {
    int dato;
    struct NodoArbol* izq;
    struct NodoArbol* der;
};

struct NodoArbol* crear(int v) {
    struct NodoArbol* n = (struct NodoArbol*)malloc(sizeof(struct NodoArbol));
    n->dato = v;
    n->izq = n->der = NULL;
    return n;
}

void preorden(struct NodoArbol* r) {
    if(r != NULL) {
        printf("%d ", r->dato);
        preorden(r->izq);
        preorden(r->der);
    }
}

void inorden(struct NodoArbol* r) {
    if(r != NULL) {
        inorden(r->izq);
        printf("%d ", r->dato);
        inorden(r->der);
    }
}

void postorden(struct NodoArbol* r) {
    if(r != NULL) {
        postorden(r->izq);
        postorden(r->der);
        printf("%d ", r->dato);
    }
}

int main() {
    struct NodoArbol* raiz = crear(1);
    raiz->izq = crear(2);
    raiz->der = crear(3);

    printf("Preorden: "); preorden(raiz); printf("\n");
    printf("Inorden: "); inorden(raiz); printf("\n");
    printf("Postorden: "); postorden(raiz); printf("\n");
    return 0;
}
```

#### Archivo: `24_arbol_binario_inorden_iterativo.cpp`
- **Ruta en carpeta:** `algoritmos_estructuras_datos/repositorio_algoritmos_estructuras_datos/Unidad_III_Estructuras_No_Lineales/24_arbol_binario_inorden_iterativo.cpp`

```cpp
#include <iostream>
using namespace std;

struct Nodo {
    int info;
    Nodo *izq, *der;
};

int main() {
    Nodo* raiz = new Nodo{10, new Nodo{5, NULL, NULL}, new Nodo{20, NULL, NULL}};
    Nodo* pila[20];
    int tope = -1;
    Nodo* act = raiz;

    cout << "Inorden iterativo con pila: ";
    while(act != NULL || tope != -1) {
        while(act != NULL) {
            pila[++tope] = act;
            act = act->izq;
        }
        act = pila[tope--];
        cout << act->info << " ";
        act = act->der;
    }
    cout << endl;
    return 0;
}
```

#### Archivo: `25_bst_arbol_busqueda_insercion_busqueda.c`
- **Ruta en carpeta:** `algoritmos_estructuras_datos/repositorio_algoritmos_estructuras_datos/Unidad_III_Estructuras_No_Lineales/25_bst_arbol_busqueda_insercion_busqueda.c`

```c
#include <stdio.h>
#include <stdlib.h>

struct BST {
    int valor;
    struct BST *izq, *der;
};

struct BST* insertar(struct BST* r, int v) {
    if(r == NULL) {
        struct BST* n = (struct BST*)malloc(sizeof(struct BST));
        n->valor = v;
        n->izq = n->der = NULL;
        return n;
    }
    if(v < r->valor) r->izq = insertar(r->izq, v);
    else r->der = insertar(r->der, v);
    return r;
}

int buscar(struct BST* r, int v) {
    if(r == NULL) return 0;
    if(r->valor == v) return 1;
    if(v < r->valor) return buscar(r->izq, v);
    return buscar(r->der, v);
}

int main() {
    struct BST* arbol = NULL;
    arbol = insertar(arbol, 50);
    arbol = insertar(arbol, 30);
    arbol = insertar(arbol, 70);

    if(buscar(arbol, 30)) printf("El 30 si existe en el BST\n");
    if(!buscar(arbol, 99)) printf("El 99 no existe en el BST\n");
    return 0;
}
```

#### Archivo: `26_bst_eliminar_nodo.cpp`
- **Ruta en carpeta:** `algoritmos_estructuras_datos/repositorio_algoritmos_estructuras_datos/Unidad_III_Estructuras_No_Lineales/26_bst_eliminar_nodo.cpp`

```cpp
#include <iostream>
using namespace std;

struct Nodo {
    int val;
    Nodo *izq, *der;
};

Nodo* minValorNodo(Nodo* n) {
    Nodo* act = n;
    while(act && act->izq != NULL) act = act->izq;
    return act;
}

Nodo* borrar(Nodo* r, int v) {
    if(r == NULL) return r;
    if(v < r->val) r->izq = borrar(r->izq, v);
    else if(v > r->val) r->der = borrar(r->der, v);
    else {
        if(r->izq == NULL) {
            Nodo* t = r->der;
            delete r;
            return t;
        } else if(r->der == NULL) {
            Nodo* t = r->izq;
            delete r;
            return t;
        }
        Nodo* t = minValorNodo(r->der);
        r->val = t->val;
        r->der = borrar(r->der, t->val);
    }
    return r;
}

void ver(Nodo* r) {
    if(r) { ver(r->izq); cout << r->val << " "; ver(r->der); }
}

int main() {
    Nodo* raiz = new Nodo{20, new Nodo{10, NULL, NULL}, new Nodo{30, NULL, NULL}};
    cout << "Arbol original: "; ver(raiz); cout << endl;
    raiz = borrar(raiz, 10);
    cout << "Despues de borrar 10: "; ver(raiz); cout << endl;
    return 0;
}
```

#### Archivo: `27_monticulo_max_heap_arreglo.c`
- **Ruta en carpeta:** `algoritmos_estructuras_datos/repositorio_algoritmos_estructuras_datos/Unidad_III_Estructuras_No_Lineales/27_monticulo_max_heap_arreglo.c`

```c
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
```

#### Archivo: `28_grafo_matriz_adyacencia.c`
- **Ruta en carpeta:** `algoritmos_estructuras_datos/repositorio_algoritmos_estructuras_datos/Unidad_III_Estructuras_No_Lineales/28_grafo_matriz_adyacencia.c`

```c
#include <stdio.h>

int grafo[4][4]; // 4 vertices (0 a 3)

void agregarArista(int u, int v) {
    grafo[u][v] = 1;
    grafo[v][u] = 1; // no dirigido
}

int main() {
    agregarArista(0, 1);
    agregarArista(0, 2);
    agregarArista(1, 3);

    printf("Matriz de adyacencia del grafo:\n");
    for(int i = 0; i < 4; i++) {
        for(int j = 0; j < 4; j++) {
            printf("%d ", grafo[i][j]);
        }
        printf("\n");
    }
    return 0;
}
```

#### Archivo: `29_grafo_lista_adyacencia.cpp`
- **Ruta en carpeta:** `algoritmos_estructuras_datos/repositorio_algoritmos_estructuras_datos/Unidad_III_Estructuras_No_Lineales/29_grafo_lista_adyacencia.cpp`

```cpp
#include <iostream>
using namespace std;

struct NodoVecino {
    int vertice;
    NodoVecino* sig;
};

NodoVecino* listaAdj[4];

void conectar(int u, int v) {
    NodoVecino* n1 = new NodoVecino{v, listaAdj[u]};
    listaAdj[u] = n1;
    NodoVecino* n2 = new NodoVecino{u, listaAdj[v]};
    listaAdj[v] = n2;
}

int main() {
    for(int i = 0; i < 4; i++) listaAdj[i] = NULL;
    conectar(0, 1);
    conectar(0, 3);
    conectar(1, 2);

    cout << "Lista de adyacencia:" << endl;
    for(int i = 0; i < 4; i++) {
        cout << "Vertice " << i << ": ";
        NodoVecino* p = listaAdj[i];
        while(p) {
            cout << p->vertice << " -> ";
            p = p->sig;
        }
        cout << "NULL" << endl;
    }
    return 0;
}
```

#### Archivo: `30_grafo_recorrido_bfs_amplitud.cpp`
- **Ruta en carpeta:** `algoritmos_estructuras_datos/repositorio_algoritmos_estructuras_datos/Unidad_III_Estructuras_No_Lineales/30_grafo_recorrido_bfs_amplitud.cpp`

```cpp
#include <iostream>
using namespace std;

int ady[4][4] = {
    {0, 1, 1, 0},
    {1, 0, 0, 1},
    {1, 0, 0, 0},
    {0, 1, 0, 0}
};

int visitado[4] = {0};
int cola[10], frente = 0, fin = 0;

int main() {
    int inicio = 0;
    cout << "Recorrido BFS (amplitud): ";
    
    visitado[inicio] = 1;
    cola[fin++] = inicio;

    while(frente < fin) {
        int v = cola[frente++];
        cout << v << " ";

        for(int j = 0; j < 4; j++) {
            if(ady[v][j] == 1 && !visitado[j]) {
                visitado[j] = 1;
                cola[fin++] = j;
            }
        }
    }
    cout << endl;
    return 0;
}
```

#### Archivo: `31_grafo_recorrido_dfs_profundidad.c`
- **Ruta en carpeta:** `algoritmos_estructuras_datos/repositorio_algoritmos_estructuras_datos/Unidad_III_Estructuras_No_Lineales/31_grafo_recorrido_dfs_profundidad.c`

```c
#include <stdio.h>

int matriz[4][4] = {
    {0, 1, 1, 0},
    {1, 0, 0, 1},
    {1, 0, 0, 0},
    {0, 1, 0, 0}
};

int visitados[4] = {0};

void dfs(int v) {
    visitados[v] = 1;
    printf("%d ", v);

    for(int i = 0; i < 4; i++) {
        if(matriz[v][i] == 1 && !visitados[i]) {
            dfs(i); // recursion en profundidad
        }
    }
}

int main() {
    printf("Recorrido DFS (profundidad): ");
    dfs(0);
    printf("\n");
    return 0;
}
```

#### Archivo: `32_grafo_dijkstra_camino_corto.cpp`
- **Ruta en carpeta:** `algoritmos_estructuras_datos/repositorio_algoritmos_estructuras_datos/Unidad_III_Estructuras_No_Lineales/32_grafo_dijkstra_camino_corto.cpp`

```cpp
#include <iostream>
using namespace std;
#define INF 9999

int costo[4][4] = {
    {0, 4, 2, INF},
    {4, 0, 1, 5},
    {2, 1, 0, 8},
    {INF, 5, 8, 0}
};

int dist[4];
bool visto[4];

int main() {
    for(int i = 0; i < 4; i++) {
        dist[i] = INF;
        visto[i] = false;
    }
    dist[0] = 0; // origen en vertice 0

    for(int count = 0; count < 4 - 1; count++) {
        int min = INF, u = -1;
        for(int v = 0; v < 4; v++) {
            if(!visto[v] && dist[v] <= min) {
                min = dist[v];
                u = v;
            }
        }
        visto[u] = true;
        for(int v = 0; v < 4; v++) {
            if(!visto[v] && costo[u][v] != INF && dist[u] + costo[u][v] < dist[v]) {
                dist[v] = dist[u] + costo[u][v];
            }
        }
    }

    cout << "Distancias mas cortas desde el vertice 0 (Dijkstra):" << endl;
    for(int i = 0; i < 4; i++) {
        cout << "Hasta nodo " << i << ": " << dist[i] << endl;
    }
    return 0;
}
```

### Carpeta: Unidad_II_Estructuras_Lineales

#### Archivo: `11_pila_estatica_arreglo.c`
- **Ruta en carpeta:** `algoritmos_estructuras_datos/repositorio_algoritmos_estructuras_datos/Unidad_II_Estructuras_Lineales/11_pila_estatica_arreglo.c`

```c
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
```

#### Archivo: `12_pila_dinamica_nodos.cpp`
- **Ruta en carpeta:** `algoritmos_estructuras_datos/repositorio_algoritmos_estructuras_datos/Unidad_II_Estructuras_Lineales/12_pila_dinamica_nodos.cpp`

```cpp
#include <iostream>
using namespace std;

struct Nodo {
    int valor;
    Nodo* siguiente;
};

Nodo* tope = NULL;

void push(int v) {
    Nodo* nuevo = new Nodo();
    nuevo->valor = v;
    nuevo->siguiente = tope;
    tope = nuevo;
}

void pop() {
    if(tope == NULL) cout << "No hay nada que sacar" << endl;
    else {
        Nodo* aux = tope;
        cout << "Pop: " << aux->valor << endl;
        tope = tope->siguiente;
        delete aux;
    }
}

int main() {
    push(100);
    push(200);
    pop();
    pop();
    return 0;
}
```

#### Archivo: `13_pila_aplicacion_parentesis_balanceados.c`
- **Ruta en carpeta:** `algoritmos_estructuras_datos/repositorio_algoritmos_estructuras_datos/Unidad_II_Estructuras_Lineales/13_pila_aplicacion_parentesis_balanceados.c`

```c
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
```

#### Archivo: `14_cola_estatica_circular.cpp`
- **Ruta en carpeta:** `algoritmos_estructuras_datos/repositorio_algoritmos_estructuras_datos/Unidad_II_Estructuras_Lineales/14_cola_estatica_circular.cpp`

```cpp
#include <iostream>
using namespace std;
#define TAM 4

int cola[TAM];
int frente = -1, final = -1;

void encolar(int x) {
    if((final + 1) % TAM == frente) {
        cout << "Cola circular llena" << endl;
        return;
    }
    if(frente == -1) frente = 0;
    final = (final + 1) % TAM;
    cola[final] = x;
}

void desencolar() {
    if(frente == -1) {
        cout << "Cola vacia" << endl;
        return;
    }
    cout << "Atendido: " << cola[frente] << endl;
    if(frente == final) frente = final = -1;
    else frente = (frente + 1) % TAM;
}

int main() {
    encolar(1);
    encolar(2);
    encolar(3);
    desencolar();
    encolar(4);
    desencolar();
    return 0;
}
```

#### Archivo: `15_cola_dinamica_nodos.c`
- **Ruta en carpeta:** `algoritmos_estructuras_datos/repositorio_algoritmos_estructuras_datos/Unidad_II_Estructuras_Lineales/15_cola_dinamica_nodos.c`

```c
#include <stdio.h>
#include <stdlib.h>

struct Nodo {
    int num;
    struct Nodo* sig;
};

struct Nodo *frente = NULL, *fondo = NULL;

void meter(int n) {
    struct Nodo* nuevo = (struct Nodo*)malloc(sizeof(struct Nodo));
    nuevo->num = n;
    nuevo->sig = NULL;
    if(fondo == NULL) {
        frente = fondo = nuevo;
    } else {
        fondo->sig = nuevo;
        fondo = nuevo;
    }
}

void sacar() {
    if(frente == NULL) {
        printf("Cola vacia\n");
        return;
    }
    struct Nodo* temp = frente;
    printf("Sacado de la cola: %d\n", temp->num);
    frente = frente->sig;
    if(frente == NULL) fondo = NULL;
    free(temp);
}

int main() {
    meter(55);
    meter(77);
    meter(99);
    sacar();
    sacar();
    return 0;
}
```

#### Archivo: `16_cola_prioridad_arreglo.cpp`
- **Ruta en carpeta:** `algoritmos_estructuras_datos/repositorio_algoritmos_estructuras_datos/Unidad_II_Estructuras_Lineales/16_cola_prioridad_arreglo.cpp`

```cpp
#include <iostream>
using namespace std;

struct Elemento {
    string tarea;
    int prioridad; // mayor numero = mas importante
};

Elemento colaPrio[5];
int total = 0;

void encolarPrio(string t, int p) {
    if(total < 5) {
        colaPrio[total].tarea = t;
        colaPrio[total].prioridad = p;
        total++;
    }
}

void desencolarPrio() {
    if(total == 0) return;
    int mayor = 0;
    for(int i = 1; i < total; i++) {
        if(colaPrio[i].prioridad > colaPrio[mayor].prioridad) {
            mayor = i;
        }
    }
    cout << "Ejecutando tarea: " << colaPrio[mayor].tarea << " (Prioridad " << colaPrio[mayor].prioridad << ")" << endl;
    for(int j = mayor; j < total - 1; j++) {
        colaPrio[j] = colaPrio[j + 1];
    }
    total--;
}

int main() {
    encolarPrio("Reporte Word", 2);
    encolarPrio("Error Kernel", 10);
    encolarPrio("Imprimir PDF", 1);
    desencolarPrio();
    desencolarPrio();
    return 0;
}
```

#### Archivo: `17_lista_simple_enlazada_insertar_mostrar.c`
- **Ruta en carpeta:** `algoritmos_estructuras_datos/repositorio_algoritmos_estructuras_datos/Unidad_II_Estructuras_Lineales/17_lista_simple_enlazada_insertar_mostrar.c`

```c
#include <stdio.h>
#include <stdlib.h>

struct Nodo {
    int valor;
    struct Nodo* siguiente;
};

int main() {
    struct Nodo* cabeza = NULL;
    
    // insertamos 3 nodos al inicio
    for(int i = 1; i <= 3; i++) {
        struct Nodo* nuevo = (struct Nodo*)malloc(sizeof(struct Nodo));
        nuevo->valor = i * 10;
        nuevo->siguiente = cabeza;
        cabeza = nuevo;
    }
    
    // mostramos la lista
    struct Nodo* actual = cabeza;
    printf("Lista simple: ");
    while(actual != NULL) {
        printf("%d -> ", actual->valor);
        actual = actual->siguiente;
    }
    printf("NULL\n");
    return 0;
}
```

#### Archivo: `18_lista_simple_eliminar_nodo.cpp`
- **Ruta en carpeta:** `algoritmos_estructuras_datos/repositorio_algoritmos_estructuras_datos/Unidad_II_Estructuras_Lineales/18_lista_simple_eliminar_nodo.cpp`

```cpp
#include <iostream>
using namespace std;

struct Nodo {
    int dato;
    Nodo* sig;
};

void eliminar(Nodo* &cab, int val) {
    if(cab == NULL) return;
    if(cab->dato == val) {
        Nodo* borrar = cab;
        cab = cab->sig;
        delete borrar;
        return;
    }
    Nodo* act = cab;
    while(act->sig != NULL && act->sig->dato != val) {
        act = act->sig;
    }
    if(act->sig != NULL) {
        Nodo* borrar = act->sig;
        act->sig = act->sig->sig;
        delete borrar;
    }
}

int main() {
    Nodo* cabeza = new Nodo{5, new Nodo{15, new Nodo{25, NULL}}};
    cout << "Eliminando 15..." << endl;
    eliminar(cabeza, 15);
    for(Nodo* p = cabeza; p != NULL; p = p->sig) cout << p->dato << " ";
    cout << endl;
    return 0;
}
```

#### Archivo: `19_lista_doblemente_enlazada.c`
- **Ruta en carpeta:** `algoritmos_estructuras_datos/repositorio_algoritmos_estructuras_datos/Unidad_II_Estructuras_Lineales/19_lista_doblemente_enlazada.c`

```c
#include <stdio.h>
#include <stdlib.h>

struct NodoDoble {
    int dato;
    struct NodoDoble* ant;
    struct NodoDoble* sig;
};

int main() {
    struct NodoDoble* n1 = (struct NodoDoble*)malloc(sizeof(struct NodoDoble));
    struct NodoDoble* n2 = (struct NodoDoble*)malloc(sizeof(struct NodoDoble));
    
    n1->dato = 100; n1->ant = NULL; n1->sig = n2;
    n2->dato = 200; n2->ant = n1; n2->sig = NULL;

    printf("Hacia adelante: %d -> %d\n", n1->dato, n1->sig->dato);
    printf("Hacia atras: %d -> %d\n", n2->dato, n2->ant->dato);
    return 0;
}
```

#### Archivo: `20_lista_circular_simple.cpp`
- **Ruta en carpeta:** `algoritmos_estructuras_datos/repositorio_algoritmos_estructuras_datos/Unidad_II_Estructuras_Lineales/20_lista_circular_simple.cpp`

```cpp
#include <iostream>
using namespace std;

struct Nodo {
    int num;
    Nodo* sig;
};

int main() {
    Nodo* primero = new Nodo{1, NULL};
    Nodo* segundo = new Nodo{2, NULL};
    Nodo* tercero = new Nodo{3, NULL};

    primero->sig = segundo;
    segundo->sig = tercero;
    tercero->sig = primero; // cerramos el circulo

    Nodo* temp = primero;
    cout << "Recorrido circular: ";
    for(int i = 0; i < 6; i++) { // recorremos 2 vueltas completas
        cout << temp->num << " -> ";
        temp = temp->sig;
    }
    cout << "..." << endl;
    return 0;
}
```

#### Archivo: `21_tabla_hash_cerrada_sondeo_lineal.c`
- **Ruta en carpeta:** `algoritmos_estructuras_datos/repositorio_algoritmos_estructuras_datos/Unidad_II_Estructuras_Lineales/21_tabla_hash_cerrada_sondeo_lineal.c`

```c
#include <stdio.h>
#define TAM 7

int tabla[TAM];

int fHash(int clave) { return clave % TAM; }

void insertar(int clave) {
    int pos = fHash(clave);
    // sondeo lineal si esta ocupado
    while(tabla[pos] != -1) {
        pos = (pos + 1) % TAM;
    }
    tabla[pos] = clave;
}

int main() {
    for(int i = 0; i < TAM; i++) tabla[i] = -1; // -1 significa vacio
    
    insertar(10); // 10 % 7 = 3
    insertar(17); // colision en 3, salta a 4
    insertar(24); // colision en 3 y 4, salta a 5
    
    printf("Tabla hash cerrada:\n");
    for(int j = 0; j < TAM; j++) printf("[%d]: %d\n", j, tabla[j]);
    return 0;
}
```

#### Archivo: `22_tabla_hash_abierta_encadenamiento.cpp`
- **Ruta en carpeta:** `algoritmos_estructuras_datos/repositorio_algoritmos_estructuras_datos/Unidad_II_Estructuras_Lineales/22_tabla_hash_abierta_encadenamiento.cpp`

```cpp
#include <iostream>
using namespace std;
#define TAM 5

struct Nodo {
    int dato;
    Nodo* sig;
};

Nodo* tabla[TAM]; // arreglo de listas

void insertarHash(int val) {
    int bucket = val % TAM;
    Nodo* nuevo = new Nodo{val, tabla[bucket]};
    tabla[bucket] = nuevo;
}

int main() {
    for(int i = 0; i < TAM; i++) tabla[i] = NULL;

    insertarHash(10);
    insertarHash(15);
    insertarHash(22);

    for(int i = 0; i < TAM; i++) {
        cout << "Casilla [" << i << "]: ";
        Nodo* p = tabla[i];
        while(p) {
            cout << p->dato << " -> ";
            p = p->sig;
        }
        cout << "NULL" << endl;
    }
    return 0;
}
```

### Carpeta: Unidad_I_Algoritmos_Fundamentales

#### Archivo: `01_ordenamiento_burbuja_iterativo.c`
- **Ruta en carpeta:** `algoritmos_estructuras_datos/repositorio_algoritmos_estructuras_datos/Unidad_I_Algoritmos_Fundamentales/01_ordenamiento_burbuja_iterativo.c`

```c
#include <stdio.h>

int a[6] = {64, 34, 25, 12, 22, 11}; // arreglo global
int n = 6;

int main() {
    int i, j, temp;
    // burbuja clasica con dos for
    for(i = 0; i < n - 1; i++) {
        for(j = 0; j < n - i - 1; j++) {
            if(a[j] > a[j + 1]) {
                temp = a[j];
                a[j] = a[j + 1];
                a[j + 1] = temp;
            }
        }
    }
    printf("Arreglo ordenado por burbuja: ");
    for(i = 0; i < n; i++) {
        printf("%d ", a[i]);
    }
    printf("\n");
    return 0;
}
```

#### Archivo: `02_ordenamiento_seleccion_iterativo.cpp`
- **Ruta en carpeta:** `algoritmos_estructuras_datos/repositorio_algoritmos_estructuras_datos/Unidad_I_Algoritmos_Fundamentales/02_ordenamiento_seleccion_iterativo.cpp`

```cpp
#include <iostream>
using namespace std;

int main() {
    int datos[5] = {29, 10, 14, 37, 13};
    int n = 5;
    
    // ordenamiento por seleccion
    for(int i = 0; i < n - 1; i++) {
        int min_idx = i;
        for(int j = i + 1; j < n; j++) {
            if(datos[j] < datos[min_idx]) {
                min_idx = j;
            }
        }
        int aux = datos[min_idx];
        datos[min_idx] = datos[i];
        datos[i] = aux;
    }
    
    cout << "Arreglo ordenado por seleccion: ";
    for(int k = 0; k < n; k++) {
        cout << datos[k] << " ";
    }
    cout << endl;
    return 0;
}
```

#### Archivo: `03_ordenamiento_insercion_iterativo.c`
- **Ruta en carpeta:** `algoritmos_estructuras_datos/repositorio_algoritmos_estructuras_datos/Unidad_I_Algoritmos_Fundamentales/03_ordenamiento_insercion_iterativo.c`

```c
#include <stdio.h>

int main() {
    int v[6] = {12, 11, 13, 5, 6, 7};
    int n = 6;
    int i, clave, j;

    // insercion como baraja de cartas
    for (i = 1; i < n; i++) {
        clave = v[i];
        j = i - 1;
        while (j >= 0 && v[j] > clave) {
            v[j + 1] = v[j];
            j = j - 1;
        }
        v[j + 1] = clave;
    }

    printf("Arreglo ordenado por insercion: ");
    for (i = 0; i < n; i++) printf("%d ", v[i]);
    printf("\n");
    return 0;
}
```

#### Archivo: `04_ordenamiento_merge_sort_recursivo.cpp`
- **Ruta en carpeta:** `algoritmos_estructuras_datos/repositorio_algoritmos_estructuras_datos/Unidad_I_Algoritmos_Fundamentales/04_ordenamiento_merge_sort_recursivo.cpp`

```cpp
#include <iostream>
using namespace std;

int arr[6] = {38, 27, 43, 3, 9, 82};

void merge(int inicio, int medio, int fin) {
    int temp[100]; // arreglo auxiliar grande
    int i = inicio, j = medio + 1, k = inicio;
    
    while(i <= medio && j <= fin) {
        if(arr[i] <= arr[j]) {
            temp[k++] = arr[i++];
        } else {
            temp[k++] = arr[j++];
        }
    }
    while(i <= medio) temp[k++] = arr[i++];
    while(j <= fin) temp[k++] = arr[j++];
    
    for(int p = inicio; p <= fin; p++) {
        arr[p] = temp[p];
    }
}

void mergeSort(int l, int r) {
    if(l < r) {
        int m = (l + r) / 2;
        mergeSort(l, m);
        mergeSort(m + 1, r);
        merge(l, m, r);
    }
}

int main() {
    mergeSort(0, 5);
    cout << "Merge Sort terminado: ";
    for(int i = 0; i < 6; i++) cout << arr[i] << " ";
    cout << endl;
    return 0;
}
```

#### Archivo: `05_busqueda_secuencial_iterativa.c`
- **Ruta en carpeta:** `algoritmos_estructuras_datos/repositorio_algoritmos_estructuras_datos/Unidad_I_Algoritmos_Fundamentales/05_busqueda_secuencial_iterativa.c`

```c
#include <stdio.h>

int main() {
    int numeros[7] = {15, 3, 89, 4, 21, 60, 42};
    int buscado, pos = -1;

    printf("Que numero buscas?: ");
    scanf("%d", &buscado);

    // recorremos todo el arreglo uno por uno
    for(int i = 0; i < 7; i++) {
        if(numeros[i] == buscado) {
            pos = i;
            break;
        }
    }

    if(pos != -1) {
        printf("Numero encontrado en la posicion %d\n", pos);
    } else {
        printf("El numero no existe en el arreglo\n");
    }
    return 0;
}
```

#### Archivo: `06_busqueda_binaria_iterativa.cpp`
- **Ruta en carpeta:** `algoritmos_estructuras_datos/repositorio_algoritmos_estructuras_datos/Unidad_I_Algoritmos_Fundamentales/06_busqueda_binaria_iterativa.cpp`

```cpp
#include <iostream>
using namespace std;

int main() {
    int ordenados[8] = {2, 5, 8, 12, 16, 23, 38, 56};
    int n = 8, valor = 23;
    int inf = 0, sup = n - 1;
    int encontrado = -1;

    // ciclo binario dividiendo a la mitad
    while(inf <= sup) {
        int med = (inf + sup) / 2;
        if(ordenados[med] == valor) {
            encontrado = med;
            break;
        }
        if(ordenados[med] < valor) inf = med + 1;
        else sup = med - 1;
    }

    if(encontrado != -1) cout << "Valor " << valor << " hallado en casilla: " << encontrado << endl;
    else cout << "No se encontro" << endl;
    return 0;
}
```

#### Archivo: `07_busqueda_binaria_recursiva.c`
- **Ruta en carpeta:** `algoritmos_estructuras_datos/repositorio_algoritmos_estructuras_datos/Unidad_I_Algoritmos_Fundamentales/07_busqueda_binaria_recursiva.c`

```c
#include <stdio.h>

int busquedaBinariaRec(int a[], int ini, int fin, int x) {
    if(ini > fin) return -1; // caso base si no esta
    
    int med = (ini + fin) / 2;
    if(a[med] == x) return med;
    if(a[med] > x) return busquedaBinariaRec(a, ini, med - 1, x);
    return busquedaBinariaRec(a, med + 1, fin, x);
}

int main() {
    int vector[6] = {10, 20, 30, 40, 50, 60};
    int dato = 50;
    int r = busquedaBinariaRec(vector, 0, 5, dato);
    
    if(r != -1) printf("Encontrado recursivamente en posicion %d\n", r);
    else printf("No existe\n");
    return 0;
}
```

#### Archivo: `08_busqueda_indexada_iterativa.c`
- **Ruta en carpeta:** `algoritmos_estructuras_datos/repositorio_algoritmos_estructuras_datos/Unidad_I_Algoritmos_Fundamentales/08_busqueda_indexada_iterativa.c`

```c
#include <stdio.h>

struct Indice {
    int clave;
    int pos;
};

int main() {
    // arreglo ordenado de datos
    int base[9] = {10, 20, 30, 40, 50, 60, 70, 80, 90};
    // tabla de indices cada 3 casillas
    struct Indice idx[3] = {{10, 0}, {40, 3}, {70, 6}};
    
    int buscado = 50;
    int inicio = 0, fin = 8;

    // buscamos en la tabla de indices primero
    for(int i = 0; i < 3; i++) {
        if(idx[i].clave <= buscado) {
            inicio = idx[i].pos;
            fin = (i == 2) ? 8 : idx[i + 1].pos;
        }
    }

    // busqueda secuencial en el rango encontrado
    int hallado = -1;
    for(int j = inicio; j <= fin; j++) {
        if(base[j] == buscado) {
            hallado = j;
            break;
        }
    }

    printf("Busqueda indexada de %d dio posicion: %d\n", buscado, hallado);
    return 0;
}
```

#### Archivo: `09_backtracking_problema_mochila.cpp`
- **Ruta en carpeta:** `algoritmos_estructuras_datos/repositorio_algoritmos_estructuras_datos/Unidad_I_Algoritmos_Fundamentales/09_backtracking_problema_mochila.cpp`

```cpp
#include <iostream>
using namespace std;

int pesos[3] = {1, 2, 3};
int valores[3] = {10, 15, 40};
int maxPeso = 5;

// exploracion exhaustiva para la mochila 0/1
int mochila(int i, int pesoActual) {
    if(i == 3 || pesoActual == 0) return 0;
    
    // no meter el objeto
    int noMeter = mochila(i + 1, pesoActual);
    
    // si cabe, probar metiendolo
    int meter = 0;
    if(pesos[i] <= pesoActual) {
        meter = valores[i] + mochila(i + 1, pesoActual - pesos[i]);
    }
    
    return (meter > noMeter) ? meter : noMeter;
}

int main() {
    cout << "Valor maximo que cabe en la mochila: " << mochila(0, maxPeso) << endl;
    return 0;
}
```

#### Archivo: `10_backtracking_n_reinas.c`
- **Ruta en carpeta:** `algoritmos_estructuras_datos/repositorio_algoritmos_estructuras_datos/Unidad_I_Algoritmos_Fundamentales/10_backtracking_n_reinas.c`

```c
#include <stdio.h>

int tablero[4][4]; // tablero 4x4

int esSeguro(int fila, int col) {
    // revisamos hacia la izquierda
    for (int i = 0; i < col; i++) if (tablero[fila][i]) return 0;
    // diagonal superior izquierda
    for (int i = fila, j = col; i >= 0 && j >= 0; i--, j--) if (tablero[i][j]) return 0;
    // diagonal inferior izquierda
    for (int i = fila, j = col; j >= 0 && i < 4; i++, j--) if (tablero[i][j]) return 0;
    return 1;
}

int resolverReinas(int col) {
    if (col >= 4) return 1; // se colocaron las 4 reinas
    for (int i = 0; i < 4; i++) {
        if (esSeguro(i, col)) {
            tablero[i][col] = 1;
            if (resolverReinas(col + 1)) return 1;
            tablero[i][col] = 0; // backtracking quitamos reina
        }
    }
    return 0;
}

int main() {
    if (resolverReinas(0)) {
        printf("Solucion N-Reinas 4x4:\n");
        for (int i = 0; i < 4; i++) {
            for (int j = 0; j < 4; j++) printf("%d ", tablero[i][j]);
            printf("\n");
        }
    }
    return 0;
}
```

---

## Materia: ANALISIS DISEÑO ALGORITMOS

### Carpeta: Unidad_III_Estrategias_No_Deterministas

#### Archivo: `20_quicksort_aleatorizado.c`
- **Ruta en carpeta:** `analisis_diseño_algoritmos/repositorio_analisis_diseno_algoritmos/Unidad_III_Estrategias_No_Deterministas/20_quicksort_aleatorizado.c`

```c
#include <stdio.h>
#include <stdlib.h>
#include <time.h>

void cambiar(int *a, int *b) {
    int t = *a; *a = *b; *b = t;
}

int particion(int a[], int l, int r) {
    int pivote = a[r];
    int i = l - 1;
    for(int j = l; j < r; j++) {
        if(a[j] < pivote) {
            i++;
            cambiar(&a[i], &a[j]);
        }
    }
    cambiar(&a[i + 1], &a[r]);
    return i + 1;
}

int particionAleatoria(int a[], int l, int r) {
    int randomIdx = l + rand() % (r - l + 1);
    cambiar(&a[randomIdx], &a[r]); // movemos pivote al final
    return particion(a, l, r);
}

void quicksortRand(int a[], int l, int r) {
    if(l < r) {
        int p = particionAleatoria(a, l, r);
        quicksortRand(a, l, p - 1);
        quicksortRand(a, p + 1, r);
    }
}

int main() {
    srand(time(NULL));
    int arr[6] = {10, 7, 8, 9, 1, 5};
    quicksortRand(arr, 0, 5);

    printf("Arreglo ordenado con Quicksort Aleatorizado: ");
    for(int i = 0; i < 6; i++) printf("%d ", arr[i]);
    printf("\n");
    return 0;
}
```

#### Archivo: `21_monte_carlo_aproximacion_pi.cpp`
- **Ruta en carpeta:** `analisis_diseño_algoritmos/repositorio_analisis_diseno_algoritmos/Unidad_III_Estrategias_No_Deterministas/21_monte_carlo_aproximacion_pi.cpp`

```cpp
#include <iostream>
#include <cstdlib>
#include <ctime>
using namespace std;

int main() {
    srand(time(NULL));
    int totalPuntos = 100000;
    int dentroCirculo = 0;

    for(int i = 0; i < totalPuntos; i++) {
        double x = (double)rand() / RAND_MAX;
        double y = (double)rand() / RAND_MAX;

        if(x * x + y * y <= 1.0) {
            dentroCirculo++;
        }
    }

    double piAprox = 4.0 * dentroCirculo / totalPuntos;
    cout << "Aproximacion de Pi con Monte Carlo (" << totalPuntos << " puntos): " << piAprox << endl;
    return 0;
}
```

#### Archivo: `22_shuffle_aleatorio_fisher_yates.c`
- **Ruta en carpeta:** `analisis_diseño_algoritmos/repositorio_analisis_diseno_algoritmos/Unidad_III_Estrategias_No_Deterministas/22_shuffle_aleatorio_fisher_yates.c`

```c
#include <stdio.h>
#include <stdlib.h>
#include <time.h>

// algoritmo para barajar arreglo de forma aleatoria
int main() {
    srand(time(NULL));
    int baraja[8] = {1, 2, 3, 4, 5, 6, 7, 8};
    int n = 8;

    for(int i = n - 1; i > 0; i--) {
        int j = rand() % (i + 1);
        int temp = baraja[i];
        baraja[i] = baraja[j];
        baraja[j] = temp;
    }

    printf("Arreglo barajado con Fisher-Yates: ");
    for(int k = 0; k < n; k++) printf("%d ", baraja[k]);
    printf("\n");
    return 0;
}
```

#### Archivo: `23_contador_binario_analisis_agregado.cpp`
- **Ruta en carpeta:** `analisis_diseño_algoritmos/repositorio_analisis_diseno_algoritmos/Unidad_III_Estrategias_No_Deterministas/23_contador_binario_analisis_agregado.cpp`

```cpp
#include <iostream>
using namespace std;

// demostracion del contador binario de bits para analisis agregado
int main() {
    int bits[5] = {0, 0, 0, 0, 0};
    int n = 16; // 16 incrementos
    int flipsTotales = 0;

    for(int i = 0; i < n; i++) {
        int j = 0;
        while(j < 5 && bits[j] == 1) {
            bits[j] = 0;
            flipsTotales++;
            j++;
        }
        if(j < 5) {
            bits[j] = 1;
            flipsTotales++;
        }
    }

    cout << "Total de cambios de bit (flips) para 16 operaciones: " << flipsTotales << endl;
    cout << "Costo amortizado por incremento: " << (double)flipsTotales / n << endl;
    return 0;
}
```

#### Archivo: `24_pila_multipop_analisis_amortizado.c`
- **Ruta en carpeta:** `analisis_diseño_algoritmos/repositorio_analisis_diseno_algoritmos/Unidad_III_Estrategias_No_Deterministas/24_pila_multipop_analisis_amortizado.c`

```c
#include <stdio.h>

int pila[20];
int tope = -1;
int costoTotal = 0;

void push(int x) {
    pila[++tope] = x;
    costoTotal += 1;
}

void multipop(int k) {
    while(tope >= 0 && k > 0) {
        tope--;
        k--;
        costoTotal += 1; // cada pop cuesta 1 operacion
    }
}

int main() {
    // hacemos una secuencia de operaciones
    push(10);
    push(20);
    push(30);
    multipop(2);
    push(40);
    multipop(5);

    printf("Operaciones de pila completadas.\n");
    printf("Costo total real acumulado: %d operaciones\n", costoTotal);
    return 0;
}
```

#### Archivo: `25_tabla_dinamica_redimension_amortizada.cpp`
- **Ruta en carpeta:** `analisis_diseño_algoritmos/repositorio_analisis_diseno_algoritmos/Unidad_III_Estrategias_No_Deterministas/25_tabla_dinamica_redimension_amortizada.cpp`

```cpp
#include <iostream>
using namespace std;

// tabla dinamica que se duplica cuando se llena
int main() {
    int capacidad = 1;
    int tam = 0;
    int *tabla = new int[capacidad];
    int copiasTotales = 0;

    for(int i = 1; i <= 8; i++) {
        if(tam == capacidad) {
            capacidad *= 2;
            int *nueva = new int[capacidad];
            for(int j = 0; j < tam; j++) {
                nueva[j] = tabla[j];
                copiasTotales++;
            }
            delete[] tabla;
            tabla = nueva;
        }
        tabla[tam++] = i;
    }

    cout << "Elementos insertados: " << tam << endl;
    cout << "Capacidad final de la tabla: " << capacidad << endl;
    cout << "Total de copias realizadas (amortizado O(1)): " << copiasTotales << endl;
    delete[] tabla;
    return 0;
}
```

### Carpeta: Unidad_II_Estrategias_Deterministas

#### Archivo: `06_maximo_subarreglo_iterativo.c`
- **Ruta en carpeta:** `analisis_diseño_algoritmos/repositorio_analisis_diseno_algoritmos/Unidad_II_Estrategias_Deterministas/06_maximo_subarreglo_iterativo.c`

```c
#include <stdio.h>

// algoritmo iterativo de kadane para el maximo subarreglo
int main() {
    int arr[8] = {-2, -5, 6, -2, -3, 1, 5, -6};
    int n = 8;
    int maxTotal = arr[0];
    int maxActual = arr[0];

    for(int i = 1; i < n; i++) {
        if(arr[i] > maxActual + arr[i]) {
            maxActual = arr[i];
        } else {
            maxActual += arr[i];
        }

        if(maxActual > maxTotal) {
            maxTotal = maxActual;
        }
    }

    printf("Suma del maximo subarreglo (iterativo Kadane): %d\n", maxTotal);
    return 0;
}
```

#### Archivo: `07_maximo_subarreglo_divide_venceras.cpp`
- **Ruta en carpeta:** `analisis_diseño_algoritmos/repositorio_analisis_diseno_algoritmos/Unidad_II_Estrategias_Deterministas/07_maximo_subarreglo_divide_venceras.cpp`

```cpp
#include <iostream>
using namespace std;

int cruzado(int arr[], int l, int m, int h) {
    int suma = 0;
    int izqSuma = -99999;
    for(int i = m; i >= l; i--) {
        suma += arr[i];
        if(suma > izqSuma) izqSuma = suma;
    }

    suma = 0;
    int derSuma = -99999;
    for(int i = m + 1; i <= h; i++) {
        suma += arr[i];
        if(suma > derSuma) derSuma = suma;
    }
    return izqSuma + derSuma;
}

int maxSubArrayRec(int arr[], int l, int h) {
    if(l == h) return arr[l];
    int m = (l + h) / 2;

    int izq = maxSubArrayRec(arr, l, m);
    int der = maxSubArrayRec(arr, m + 1, h);
    int cruce = cruzado(arr, l, m, h);

    int mayor = (izq > der) ? izq : der;
    return (mayor > cruce) ? mayor : cruce;
}

int main() {
    int datos[8] = {-2, -5, 6, -2, -3, 1, 5, -6};
    cout << "Maximo subarreglo (Divide y Venceras): " << maxSubArrayRec(datos, 0, 7) << endl;
    return 0;
}
```

#### Archivo: `08_multiplicacion_matrices_strassen_2x2.c`
- **Ruta en carpeta:** `analisis_diseño_algoritmos/repositorio_analisis_diseno_algoritmos/Unidad_II_Estrategias_Deterministas/08_multiplicacion_matrices_strassen_2x2.c`

```c
#include <stdio.h>

// multiplicacion de strassen para matrices 2x2 usando 7 multiplicaciones
int main() {
    int A[2][2] = {{1, 3}, {7, 5}};
    int B[2][2] = {{6, 8}, {4, 2}};

    int m1 = (A[0][0] + A[1][1]) * (B[0][0] + B[1][1]);
    int m2 = (A[1][0] + A[1][1]) * B[0][0];
    int m3 = A[0][0] * (B[0][1] - B[1][1]);
    int m4 = A[1][1] * (B[1][0] - B[0][0]);
    int m5 = (A[0][0] + A[0][1]) * B[1][1];
    int m6 = (A[1][0] - A[0][0]) * (B[0][0] + B[0][1]);
    int m7 = (A[0][1] - A[1][1]) * (B[1][0] + B[1][1]);

    int C[2][2];
    C[0][0] = m1 + m4 - m5 + m7;
    C[0][1] = m3 + m5;
    C[1][0] = m2 + m4;
    C[1][1] = m1 - m2 + m3 + m6;

    printf("Resultado matriz Strassen 2x2:\n");
    printf("%d %d\n%d %d\n", C[0][0], C[0][1], C[1][0], C[1][1]);
    return 0;
}
```

#### Archivo: `09_quickselect_mediana_recursivo.cpp`
- **Ruta en carpeta:** `analisis_diseño_algoritmos/repositorio_analisis_diseno_algoritmos/Unidad_II_Estrategias_Deterministas/09_quickselect_mediana_recursivo.cpp`

```cpp
#include <iostream>
using namespace std;

int particion(int a[], int l, int r) {
    int pivote = a[r];
    int i = l;
    for(int j = l; j < r; j++) {
        if(a[j] <= pivote) {
            int aux = a[i]; a[i] = a[j]; a[j] = aux;
            i++;
        }
    }
    int aux = a[i]; a[i] = a[r]; a[r] = aux;
    return i;
}

// divide y venceras para hallar el k-esimo menor
int quickSelect(int a[], int l, int r, int k) {
    if(l == r) return a[l];
    int p = particion(a, l, r);
    if(p == k) return a[p];
    else if(p > k) return quickSelect(a, l, p - 1, k);
    else return quickSelect(a, p + 1, r, k);
}

int main() {
    int arr[7] = {12, 3, 5, 7, 4, 19, 26};
    int k = 3; // buscamos el elemento con indice 3 ordenado
    cout << "El elemento en la posicion " << k << " (mediana/estadistico) es: " 
         << quickSelect(arr, 0, 6, k) << endl;
    return 0;
}
```

#### Archivo: `10_potencia_binaria_iterativa.c`
- **Ruta en carpeta:** `analisis_diseño_algoritmos/repositorio_analisis_diseno_algoritmos/Unidad_II_Estrategias_Deterministas/10_potencia_binaria_iterativa.c`

```c
#include <stdio.h>

// potencia rapida en O(log b) de forma iterativa
long long potenciaIterativa(long long base, int exp) {
    long long res = 1;
    while(exp > 0) {
        if(exp % 2 == 1) {
            res *= base;
        }
        base *= base;
        exp /= 2;
    }
    return res;
}

int main() {
    long long b = 3;
    int e = 13;
    printf("%lld elevado a la %d es: %lld\n", b, e, potenciaIterativa(b, e));
    return 0;
}
```

#### Archivo: `11_potencia_binaria_recursiva.cpp`
- **Ruta en carpeta:** `analisis_diseño_algoritmos/repositorio_analisis_diseno_algoritmos/Unidad_II_Estrategias_Deterministas/11_potencia_binaria_recursiva.cpp`

```cpp
#include <iostream>
using namespace std;

// potencia rapida con recursion divide y venceras
long long potenciaRec(long long base, int exp) {
    if(exp == 0) return 1;
    long long mitad = potenciaRec(base, exp / 2);
    if(exp % 2 == 0) return mitad * mitad;
    else return base * mitad * mitad;
}

int main() {
    cout << "2^10 recursivo: " << potenciaRec(2, 10) << endl;
    return 0;
}
```

#### Archivo: `12_corte_varilla_recursivo.c`
- **Ruta en carpeta:** `analisis_diseño_algoritmos/repositorio_analisis_diseno_algoritmos/Unidad_II_Estrategias_Deterministas/12_corte_varilla_recursivo.c`

```c
#include <stdio.h>

int precios[9] = {0, 1, 5, 8, 9, 10, 17, 17, 20};

// corte de varilla por recursion pura (lento exponencial)
int corteRecursivo(int n) {
    if(n <= 0) return 0;
    int maxVal = -1;
    for(int i = 1; i <= n; i++) {
        int actual = precios[i] + corteRecursivo(n - i);
        if(actual > maxVal) maxVal = actual;
    }
    return maxVal;
}

int main() {
    int longitud = 4;
    printf("Ganancia maxima corte varilla (recursivo) tam %d: %d\n", longitud, corteRecursivo(longitud));
    return 0;
}
```

#### Archivo: `13_corte_varilla_programacion_dinamica.cpp`
- **Ruta en carpeta:** `analisis_diseño_algoritmos/repositorio_analisis_diseno_algoritmos/Unidad_II_Estrategias_Deterministas/13_corte_varilla_programacion_dinamica.cpp`

```cpp
#include <iostream>
using namespace std;

int precios[9] = {0, 1, 5, 8, 9, 10, 17, 17, 20};

// corte de varilla con programacion dinamica bottom-up
int corteDP(int n) {
    int tabla[10];
    tabla[0] = 0;

    for(int j = 1; j <= n; j++) {
        int maxVal = -1;
        for(int i = 1; i <= j; i++) {
            if(precios[i] + tabla[j - i] > maxVal) {
                maxVal = precios[i] + tabla[j - i];
            }
        }
        tabla[j] = maxVal;
    }
    return tabla[n];
}

int main() {
    int tam = 8;
    cout << "Ganancia maxima corte varilla con DP para tam " << tam << ": " << corteDP(tam) << endl;
    return 0;
}
```

#### Archivo: `14_cadena_matrices_programacion_dinamica.c`
- **Ruta en carpeta:** `analisis_diseño_algoritmos/repositorio_analisis_diseno_algoritmos/Unidad_II_Estrategias_Deterministas/14_cadena_matrices_programacion_dinamica.c`

```c
#include <stdio.h>
#define INF 999999

int p[5] = {10, 20, 30, 40, 30}; // dimensiones de las 4 matrices
int m[5][5];

int main() {
    int n = 4; // 4 matrices

    for(int i = 1; i <= n; i++) m[i][i] = 0;

    for(int L = 2; L <= n; L++) {
        for(int i = 1; i <= n - L + 1; i++) {
            int j = i + L - 1;
            m[i][j] = INF;
            for(int k = i; k <= j - 1; k++) {
                int costo = m[i][k] + m[k + 1][j] + p[i - 1] * p[k] * p[j];
                if(costo < m[i][j]) m[i][j] = costo;
            }
        }
    }

    printf("Minimo costo de multiplicaciones de cadena de matrices: %d\n", m[1][n]);
    return 0;
}
```

#### Archivo: `15_mochila_01_programacion_dinamica.cpp`
- **Ruta en carpeta:** `analisis_diseño_algoritmos/repositorio_analisis_diseno_algoritmos/Unidad_II_Estrategias_Deterministas/15_mochila_01_programacion_dinamica.cpp`

```cpp
#include <iostream>
using namespace std;

int main() {
    int pesos[4] = {0, 2, 3, 4};
    int valores[4] = {0, 3, 4, 5};
    int cap = 5;
    int dp[4][6];

    for(int i = 0; i <= 3; i++) {
        for(int w = 0; w <= cap; w++) {
            if(i == 0 || w == 0) {
                dp[i][w] = 0;
            } else if(pesos[i] <= w) {
                int incluir = valores[i] + dp[i - 1][w - pesos[i]];
                int excluir = dp[i - 1][w];
                dp[i][w] = (incluir > excluir) ? incluir : excluir;
            } else {
                dp[i][w] = dp[i - 1][w];
            }
        }
    }

    cout << "Maximo valor en la mochila con DP: " << dp[3][cap] << endl;
    return 0;
}
```

#### Archivo: `16_subsecuencia_comun_mas_larga_dp.c`
- **Ruta en carpeta:** `analisis_diseño_algoritmos/repositorio_analisis_diseno_algoritmos/Unidad_II_Estrategias_Deterministas/16_subsecuencia_comun_mas_larga_dp.c`

```c
#include <stdio.h>
#include <string.h>

char X[10] = "AGGTAB";
char Y[10] = "GXTXAYB";
int dp[10][10];

int main() {
    int m = strlen(X);
    int n = strlen(Y);

    for(int i = 0; i <= m; i++) {
        for(int j = 0; j <= n; j++) {
            if(i == 0 || j == 0) dp[i][j] = 0;
            else if(X[i - 1] == Y[j - 1]) dp[i][j] = 1 + dp[i - 1][j - 1];
            else {
                int a = dp[i - 1][j];
                int b = dp[i][j - 1];
                dp[i][j] = (a > b) ? a : b;
            }
        }
    }

    printf("Longitud de la subsecuencia comun mas larga (LCS): %d\n", dp[m][n]);
    return 0;
}
```

#### Archivo: `17_floyd_warshall_caminos_cortos.cpp`
- **Ruta en carpeta:** `analisis_diseño_algoritmos/repositorio_analisis_diseno_algoritmos/Unidad_II_Estrategias_Deterministas/17_floyd_warshall_caminos_cortos.cpp`

```cpp
#include <iostream>
using namespace std;
#define INF 9999

int main() {
    int dist[4][4] = {
        {0, 5, INF, 10},
        {INF, 0, 3, INF},
        {INF, INF, 0, 1},
        {INF, INF, INF, 0}
    };

    // algoritmo de floyd warshall
    for(int k = 0; k < 4; k++) {
        for(int i = 0; i < 4; i++) {
            for(int j = 0; j < 4; j++) {
                if(dist[i][k] + dist[k][j] < dist[i][j]) {
                    dist[i][j] = dist[i][k] + dist[k][j];
                }
            }
        }
    }

    cout << "Matriz de distancias minimas entre todos los pares:" << endl;
    for(int i = 0; i < 4; i++) {
        for(int j = 0; j < 4; j++) {
            if(dist[i][j] == INF) cout << "INF ";
            else cout << dist[i][j] << " ";
        }
        cout << endl;
    }
    return 0;
}
```

#### Archivo: `18_seleccion_actividades_greedy.c`
- **Ruta en carpeta:** `analisis_diseño_algoritmos/repositorio_analisis_diseno_algoritmos/Unidad_II_Estrategias_Deterministas/18_seleccion_actividades_greedy.c`

```c
#include <stdio.h>

// las actividades ya vienen ordenadas por tiempo de fin
int inicio[6] = {1, 3, 0, 5, 8, 5};
int fin[6]    = {2, 4, 6, 7, 9, 9};

int main() {
    int n = 6;
    printf("Actividades seleccionadas (greedy):\n");

    int i = 0;
    printf("Actividad %d (inicio %d, fin %d)\n", i, inicio[i], fin[i]);

    for(int j = 1; j < n; j++) {
        if(inicio[j] >= fin[i]) {
            printf("Actividad %d (inicio %d, fin %d)\n", j, inicio[j], fin[j]);
            i = j;
        }
    }
    return 0;
}
```

#### Archivo: `19_cambio_monedas_greedy.cpp`
- **Ruta en carpeta:** `analisis_diseño_algoritmos/repositorio_analisis_diseno_algoritmos/Unidad_II_Estrategias_Deterministas/19_cambio_monedas_greedy.cpp`

```cpp
#include <iostream>
using namespace std;

int main() {
    int monedas[5] = {20, 10, 5, 2, 1}; // ordenadas de mayor a menor
    int cambio = 47;
    int totalMonedas = 0;

    cout << "Cambio para $" << cambio << ":" << endl;
    for(int i = 0; i < 5; i++) {
        while(cambio >= monedas[i]) {
            cambio -= monedas[i];
            totalMonedas++;
            cout << "Moneda de $" << monedas[i] << endl;
        }
    }
    cout << "Total de monedas usadas: " << totalMonedas << endl;
    return 0;
}
```

### Carpeta: Unidad_IV_Teoria_Complejidad

#### Archivo: `26_verificador_polinomial_clique.c`
- **Ruta en carpeta:** `analisis_diseño_algoritmos/repositorio_analisis_diseno_algoritmos/Unidad_IV_Teoria_Complejidad/26_verificador_polinomial_clique.c`

```c
#include <stdio.h>

// verificador polinomial para saber si un certificado es una Clique
int grafo[4][4] = {
    {0, 1, 1, 1},
    {1, 0, 1, 0},
    {1, 1, 0, 1},
    {1, 0, 1, 0}
};

int main() {
    int candidatos[3] = {0, 1, 2}; // certificado a verificar de tamano 3
    int tam = 3;
    int esValido = 1;

    for(int i = 0; i < tam; i++) {
        for(int j = i + 1; j < tam; j++) {
            int u = candidatos[i];
            int v = candidatos[j];
            if(grafo[u][v] == 0) {
                esValido = 0;
                break;
            }
        }
    }

    if(esValido) printf("Certificado verificado en O(k^2): Es una Clique valida\n");
    else printf("No es una Clique\n");
    return 0;
}
```

#### Archivo: `27_verificador_polinomial_subset_sum.cpp`
- **Ruta en carpeta:** `analisis_diseño_algoritmos/repositorio_analisis_diseno_algoritmos/Unidad_IV_Teoria_Complejidad/27_verificador_polinomial_subset_sum.cpp`

```cpp
#include <iostream>
using namespace std;

// problema de la suma de subconjuntos: verificador en tiempo lineal O(k)
int main() {
    int objetivo = 25;
    int certificado[3] = {5, 12, 8}; // subconjunto propuesto
    int tam = 3;
    int suma = 0;

    for(int i = 0; i < tam; i++) {
        suma += certificado[i];
    }

    if(suma == objetivo) {
        cout << "Certificado correcto para Subset-Sum! La suma dio: " << suma << endl;
    } else {
        cout << "Certificado incorrecto" << endl;
    }
    return 0;
}
```

#### Archivo: `28_clique_fuerza_bruta_exponencial.c`
- **Ruta en carpeta:** `analisis_diseño_algoritmos/repositorio_analisis_diseno_algoritmos/Unidad_IV_Teoria_Complejidad/28_clique_fuerza_bruta_exponencial.c`

```c
#include <stdio.h>

int grafo[4][4] = {
    {0, 1, 1, 0},
    {1, 0, 1, 1},
    {1, 1, 0, 1},
    {0, 1, 1, 0}
};

// prueba todas las combinaciones 2^n por fuerza bruta
int main() {
    int n = 4;
    int maxClique = 0;

    for(int mascara = 1; mascara < (1 << n); mascara++) {
        int esClique = 1;
        int tamActual = 0;

        for(int i = 0; i < n; i++) {
            if(mascara & (1 << i)) {
                tamActual++;
                for(int j = i + 1; j < n; j++) {
                    if((mascara & (1 << j)) && grafo[i][j] == 0) {
                        esClique = 0;
                        break;
                    }
                }
            }
        }
        if(esClique && tamActual > maxClique) {
            maxClique = tamActual;
        }
    }

    printf("Tamano de la Clique Maxima por fuerza bruta O(2^n): %d\n", maxClique);
    return 0;
}
```

#### Archivo: `29_vertex_cover_aproximacion.cpp`
- **Ruta en carpeta:** `analisis_diseño_algoritmos/repositorio_analisis_diseno_algoritmos/Unidad_IV_Teoria_Complejidad/29_vertex_cover_aproximacion.cpp`

```cpp
#include <iostream>
using namespace std;

// algoritmo 2-aproximacion para Cobertura de Vertices
int main() {
    int aristas[4][2] = {{0, 1}, {1, 2}, {2, 3}, {0, 2}};
    int numAristas = 4;
    bool cubierto[4] = {false, false, false, false};

    cout << "Vertices seleccionados para el Vertex Cover aproximado:" << endl;
    for(int i = 0; i < numAristas; i++) {
        int u = aristas[i][0];
        int v = aristas[i][1];

        // si ningun extremo esta cubierto, tomamos ambos
        if(!cubierto[u] && !cubierto[v]) {
            cubierto[u] = true;
            cubierto[v] = true;
            cout << "Vertice " << u << " y Vertice " << v << endl;
        }
    }
    return 0;
}
```

#### Archivo: `30_tsp_aproximacion_vecino_cercano.c`
- **Ruta en carpeta:** `analisis_diseño_algoritmos/repositorio_analisis_diseno_algoritmos/Unidad_IV_Teoria_Complejidad/30_tsp_aproximacion_vecino_cercano.c`

```c
#include <stdio.h>
#define INF 9999

int distancia[4][4] = {
    {0, 10, 15, 20},
    {10, 0, 35, 25},
    {15, 35, 0, 30},
    {20, 25, 30, 0}
};

int visitado[4] = {0};

int main() {
    int ciudadActual = 0;
    int costoTotal = 0;
    visitado[ciudadActual] = 1;

    printf("Ruta aproximada TSP (Vecino Mas Cercano):\n");
    printf("%d -> ", ciudadActual);

    for(int paso = 0; paso < 3; paso++) {
        int mejorDist = INF;
        int proxima = -1;

        for(int j = 0; j < 4; j++) {
            if(!visitado[j] && distancia[ciudadActual][j] < mejorDist) {
                mejorDist = distancia[ciudadActual][j];
                proxima = j;
            }
        }
        visitado[proxima] = 1;
        costoTotal += mejorDist;
        ciudadActual = proxima;
        printf("%d -> ", ciudadActual);
    }

    // volvemos al inicio
    costoTotal += distancia[ciudadActual][0];
    printf("0\n");
    printf("Costo total aproximado del tour: %d\n", costoTotal);
    return 0;
}
```

#### Archivo: `31_mochila_branch_and_bound.cpp`
- **Ruta en carpeta:** `analisis_diseño_algoritmos/repositorio_analisis_diseno_algoritmos/Unidad_IV_Teoria_Complejidad/31_mochila_branch_and_bound.cpp`

```cpp
#include <iostream>
using namespace std;

int pesos[3] = {2, 3, 4};
int valores[3] = {3, 4, 5};
int capacidad = 5;
int mejorValor = 0;

// poda por ramificacion y acotamiento (branch and bound)
void branchAndBound(int idx, int pesoActual, int valorActual) {
    if(pesoActual > capacidad) return; // poda si se pasa del peso

    if(valorActual > mejorValor) {
        mejorValor = valorActual;
    }

    if(idx == 3) return;

    // rama 1: incluir objeto
    branchAndBound(idx + 1, pesoActual + pesos[idx], valorActual + valores[idx]);
    // rama 2: excluir objeto
    branchAndBound(idx + 1, pesoActual, valorActual);
}

int main() {
    branchAndBound(0, 0, 0);
    cout << "Mejor valor encontrado con Branch and Bound: " << mejorValor << endl;
    return 0;
}
```

### Carpeta: Unidad_I_Contextualizacion_Notaciones

#### Archivo: `01_medicion_tiempo_temporal.c`
- **Ruta en carpeta:** `analisis_diseño_algoritmos/repositorio_analisis_diseno_algoritmos/Unidad_I_Contextualizacion_Notaciones/01_medicion_tiempo_temporal.c`

```c
#include <stdio.h>
#include <time.h>

int main() {
    clock_t inicio, fin;
    double tiempoTotal;
    long long suma = 0;
    long long n = 10000000;

    // medimos cuanto tarda en correr el ciclo
    inicio = clock();
    for(long long i = 0; i < n; i++) {
        suma += i;
    }
    fin = clock();

    tiempoTotal = (double)(fin - inicio) / CLOCKS_PER_SEC;
    printf("Suma: %lld\n", suma);
    printf("Tiempo de ejecucion: %f segundos\n", tiempoTotal);
    return 0;
}
```

#### Archivo: `02_complejidad_espacial_memoria.cpp`
- **Ruta en carpeta:** `analisis_diseño_algoritmos/repositorio_analisis_diseno_algoritmos/Unidad_I_Contextualizacion_Notaciones/02_complejidad_espacial_memoria.cpp`

```cpp
#include <iostream>
using namespace std;

// vemos cuanta memoria ocupa un arreglo estatico vs uno dinamico
int main() {
    int tam = 5;
    int estatico[5] = {1, 2, 3, 4, 5}; // memoria en el stack
    int *dinamico = new int[tam];      // memoria en el heap

    for(int i = 0; i < tam; i++) {
        dinamico[i] = estatico[i] * 10;
    }

    cout << "Bytes del arreglo estatico: " << sizeof(estatico) << endl;
    cout << "Bytes del puntero dinamico: " << sizeof(dinamico) << endl;

    for(int j = 0; j < tam; j++) {
        cout << dinamico[j] << " ";
    }
    cout << endl;
    delete[] dinamico;
    return 0;
}
```

#### Archivo: `03_conteo_operaciones_asintotico.c`
- **Ruta en carpeta:** `analisis_diseño_algoritmos/repositorio_analisis_diseno_algoritmos/Unidad_I_Contextualizacion_Notaciones/03_conteo_operaciones_asintotico.c`

```c
#include <stdio.h>

int main() {
    int n = 5;
    int contadorLineal = 0;
    int contadorCuadratico = 0;

    // conteo de pasos para O(n)
    for(int i = 0; i < n; i++) {
        contadorLineal++;
    }

    // conteo de pasos para O(n^2)
    for(int i = 0; i < n; i++) {
        for(int j = 0; j < n; j++) {
            contadorCuadratico++;
        }
    }

    printf("Para n = %d:\n", n);
    printf("Operaciones en O(n): %d\n", contadorLineal);
    printf("Operaciones en O(n^2): %d\n", contadorCuadratico);
    return 0;
}
```

#### Archivo: `04_comparacion_crecimientos_asintoticos.cpp`
- **Ruta en carpeta:** `analisis_diseño_algoritmos/repositorio_analisis_diseno_algoritmos/Unidad_I_Contextualizacion_Notaciones/04_comparacion_crecimientos_asintoticos.cpp`

```cpp
#include <iostream>
#include <cmath>
using namespace std;

// comparamos como crecen las funciones tipicas de orden
int main() {
    int valoresN[4] = {2, 4, 8, 16};

    cout << "n\tLog2(n)\tn\tn^2\t2^n" << endl;
    for(int i = 0; i < 4; i++) {
        int n = valoresN[i];
        cout << n << "\t" 
             << log2(n) << "\t" 
             << n << "\t" 
             << n * n << "\t" 
             << pow(2, n) << endl;
    }
    return 0;
}
```

#### Archivo: `05_complejidad_cubica_matrices.c`
- **Ruta en carpeta:** `analisis_diseño_algoritmos/repositorio_analisis_diseno_algoritmos/Unidad_I_Contextualizacion_Notaciones/05_complejidad_cubica_matrices.c`

```c
#include <stdio.h>

int main() {
    int A[2][2] = {{1, 2}, {3, 4}};
    int B[2][2] = {{5, 6}, {7, 8}};
    int C[2][2] = {{0, 0}, {0, 0}};
    int n = 2;
    int operaciones = 0;

    // multiplicacion tradicional de matrices O(n^3)
    for(int i = 0; i < n; i++) {
        for(int j = 0; j < n; j++) {
            for(int k = 0; k < n; k++) {
                C[i][j] += A[i][k] * B[k][j];
                operaciones++;
            }
        }
    }

    printf("Matriz resultante:\n");
    for(int i = 0; i < n; i++) {
        for(int j = 0; j < n; j++) {
            printf("%d ", C[i][j]);
        }
        printf("\n");
    }
    printf("Total de multiplicaciones O(n^3): %d\n", operaciones);
    return 0;
}
```

---

## Materia: FUNDAMENTOS PROGRAMACIÓN

### Carpeta: Unidad_III_Memoria_Dinamica_Archivos

#### Archivo: `arreglo_dinamico_malloc.c`
- **Ruta en carpeta:** `fundamentos_programación/repositorio_fundamentos/Unidad_III_Memoria_Dinamica_Archivos/arreglo_dinamico_malloc.c`

```c
#include <stdio.h>
#include <stdlib.h>

int main() {
    int tam;
    int *vector;
    
    printf("Cuantos enteros vas a guardar?: ");
    scanf("%d", &tam);
    
    vector = (int*) malloc(tam * sizeof(int));
    
    for(int i = 0; i < tam; i++) {
        vector[i] = (i + 1) * 10;
        printf("vector[%d] = %d\n", i, vector[i]);
    }
    
    return 0;
}
```

#### Archivo: `calificaciones_memoria_dinamica_new_delete.cpp`
- **Ruta en carpeta:** `fundamentos_programación/repositorio_fundamentos/Unidad_III_Memoria_Dinamica_Archivos/calificaciones_memoria_dinamica_new_delete.cpp`

```cpp
#include <iostream>
using namespace std;

int main() {
    int n;
    cout << "Cuantas calificaciones son?: ";
    cin >> n;
    
    float *califs = new float[n];
    
    for(int i = 0; i < n; i++) {
        cout << "Calificacion " << i + 1 << ": ";
        cin >> califs[i];
    }
    
    cout << "Notas registradas correctamente" << endl;
    delete[] califs;
    return 0;
}
```

#### Archivo: `escritura_archivo_texto_fprintf.c`
- **Ruta en carpeta:** `fundamentos_programación/repositorio_fundamentos/Unidad_III_Memoria_Dinamica_Archivos/escritura_archivo_texto_fprintf.c`

```c
#include <stdio.h>

int main() {
    FILE *arch = fopen("alumnos.txt", "w");
    
    if(arch == NULL) {
        printf("No se pudo crear el archivo\n");
        return 1;
    }
    
    fprintf(arch, "Registro de Alumnos\n");
    fprintf(arch, "Rodrigo 9.5\n");
    fprintf(arch, "Mariana 8.0\n");
    
    fclose(arch);
    printf("Archivo guardado con exito\n");
    return 0;
}
```

#### Archivo: `guardar_leer_struct_archivo_binario.c`
- **Ruta en carpeta:** `fundamentos_programación/repositorio_fundamentos/Unidad_III_Memoria_Dinamica_Archivos/guardar_leer_struct_archivo_binario.c`

```c
#include <stdio.h>

struct Jugador {
    char nick[20];
    int puntaje;
};

int main() {
    struct Jugador j1 = {"PlayerOne", 9999};
    struct Jugador leido;
    
    FILE *f1 = fopen("partida.dat", "wb");
    fwrite(&j1, sizeof(struct Jugador), 1, f1);
    fclose(f1);
    printf("Guardado en binario\n");
    
    FILE *f2 = fopen("partida.dat", "rb");
    fread(&leido, sizeof(struct Jugador), 1, f2);
    fclose(f2);
    
    printf("Leido del binario: Jugador=%s, Score=%d\n", leido.nick, leido.puntaje);
    return 0;
}
```

#### Archivo: `lectura_archivo_texto_fgets.cpp`
- **Ruta en carpeta:** `fundamentos_programación/repositorio_fundamentos/Unidad_III_Memoria_Dinamica_Archivos/lectura_archivo_texto_fgets.cpp`

```cpp
#include <iostream>
#include <stdio.h>
using namespace std;

int main() {
    FILE *archivo;
    char bufer[100];
    
    archivo = fopen("alumnos.txt", "r");
    
    if(archivo != NULL) {
        cout << "Leyendo archivo:" << endl;
        while(fgets(bufer, 100, archivo) != NULL) {
            cout << bufer;
        }
        fclose(archivo);
    } else {
        cout << "Error: no existe el archivo alumnos.txt" << endl;
    }
    return 0;
}
```

#### Archivo: `memoria_dinamica_calloc_realloc.c`
- **Ruta en carpeta:** `fundamentos_programación/repositorio_fundamentos/Unidad_III_Memoria_Dinamica_Archivos/memoria_dinamica_calloc_realloc.c`

```c
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
```

### Carpeta: Unidad_II_Apuntadores_Estructuras_Funciones

#### Archivo: `apuntador_a_estructura_operador_flecha.c`
- **Ruta en carpeta:** `fundamentos_programación/repositorio_fundamentos/Unidad_II_Apuntadores_Estructuras_Funciones/apuntador_a_estructura_operador_flecha.c`

```c
#include <stdio.h>

struct Coordenada {
    int x;
    int y;
};

int main() {
    struct Coordenada punto = {12, 24};
    struct Coordenada *ptr = &punto;
    
    printf("Coordenada original: (%d, %d)\n", ptr->x, ptr->y);
    
    ptr->x = 50;
    ptr->y = 100;
    printf("Coordenada modificada: (%d, %d)\n", punto.x, punto.y);
    return 0;
}
```

#### Archivo: `catalogo_productos_arreglo_estructuras.cpp`
- **Ruta en carpeta:** `fundamentos_programación/repositorio_fundamentos/Unidad_II_Apuntadores_Estructuras_Funciones/catalogo_productos_arreglo_estructuras.cpp`

```cpp
#include <iostream>
using namespace std;

struct Producto {
    char nombre[20];
    float precio;
    int stock;
};

int main() {
    struct Producto tienda[3];
    
    for(int i = 0; i < 3; i++) {
        cout << "Producto " << i + 1 << " nombre: ";
        cin >> tienda[i].nombre;
        cout << "Precio: ";
        cin >> tienda[i].precio;
        cout << "Stock: ";
        cin >> tienda[i].stock;
    }
    
    cout << "\n--- LISTA REGISTRADA ---" << endl;
    for(int i = 0; i < 3; i++) {
        cout << tienda[i].nombre << " cuesta $" << tienda[i].precio << " (Quedan: " << tienda[i].stock << ")" << endl;
    }
    return 0;
}
```

#### Archivo: `factorial_iterativo_for.c`
- **Ruta en carpeta:** `fundamentos_programación/repositorio_fundamentos/Unidad_II_Apuntadores_Estructuras_Funciones/factorial_iterativo_for.c`

```c
#include <stdio.h>

int factorialIterativo(int n) {
    int res = 1;
    for(int i = 1; i <= n; i++) {
        res = res * i;
    }
    return res;
}

int main() {
    int num;
    printf("Dame el numero: ");
    scanf("%d", &num);
    printf("Factorial de %d es: %d\n", num, factorialIterativo(num));
    return 0;
}
```

#### Archivo: `factorial_iterativo_while.cpp`
- **Ruta en carpeta:** `fundamentos_programación/repositorio_fundamentos/Unidad_II_Apuntadores_Estructuras_Funciones/factorial_iterativo_while.cpp`

```cpp
#include <iostream>
using namespace std;

int factorialWhile(int n) {
    int mult = 1;
    while(n > 1) {
        mult *= n;
        n--;
    }
    return mult;
}

int main() {
    int valor;
    cout << "Numero a calcular: ";
    cin >> valor;
    cout << "Resultado: " << factorialWhile(valor) << endl;
    return 0;
}
```

#### Archivo: `factorial_recursivo.c`
- **Ruta en carpeta:** `fundamentos_programación/repositorio_fundamentos/Unidad_II_Apuntadores_Estructuras_Funciones/factorial_recursivo.c`

```c
#include <stdio.h>

int factorialRecursivo(int n) {
    if(n == 0 || n == 1) {
        return 1;
    }
    return n * factorialRecursivo(n - 1);
}

int main() {
    int num;
    printf("Ingresa valor: ");
    scanf("%d", &num);
    printf("El factorial recursivo es: %d\n", factorialRecursivo(num));
    return 0;
}
```

#### Archivo: `intercambio_swap_apuntadores.c`
- **Ruta en carpeta:** `fundamentos_programación/repositorio_fundamentos/Unidad_II_Apuntadores_Estructuras_Funciones/intercambio_swap_apuntadores.c`

```c
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
```

#### Archivo: `paso_por_referencia_alias.cpp`
- **Ruta en carpeta:** `fundamentos_programación/repositorio_fundamentos/Unidad_II_Apuntadores_Estructuras_Funciones/paso_por_referencia_alias.cpp`

```cpp
#include <iostream>
using namespace std;

void duplicar(int &numero) {
    numero = numero * 2;
}

int main() {
    int n = 7;
    cout << "Antes: " << n << endl;
    duplicar(n);
    cout << "Despues: " << n << endl;
    return 0;
}
```

#### Archivo: `recorrido_aritmetica_apuntadores.c`
- **Ruta en carpeta:** `fundamentos_programación/repositorio_fundamentos/Unidad_II_Apuntadores_Estructuras_Funciones/recorrido_aritmetica_apuntadores.c`

```c
#include <stdio.h>

int main() {
    int datos[5] = {10, 25, 30, 45, 50};
    int *p = datos;
    
    for(int i = 0; i < 5; i++) {
        printf("Posicion %d: valor %d en direccion %p\n", i, *(p + i), (p + i));
    }
    return 0;
}
```

#### Archivo: `registro_alumno_estructura.c`
- **Ruta en carpeta:** `fundamentos_programación/repositorio_fundamentos/Unidad_II_Apuntadores_Estructuras_Funciones/registro_alumno_estructura.c`

```c
#include <stdio.h>

struct Alumno {
    char nombre[30];
    int boleta;
    float promedio;
};

int main() {
    struct Alumno a1;
    
    printf("Nombre: ");
    scanf("%s", a1.nombre);
    printf("Boleta: ");
    scanf("%d", &a1.boleta);
    printf("Promedio: ");
    scanf("%f", &a1.promedio);
    
    printf("\nDatos capturados:\n");
    printf("Nombre: %s | Boleta: %d | Promedio: %.2f\n", a1.nombre, a1.boleta, a1.promedio);
    return 0;
}
```

### Carpeta: Unidad_I_Programacion_Estructurada

#### Archivo: `busqueda_lineal_arreglo.c`
- **Ruta en carpeta:** `fundamentos_programación/repositorio_fundamentos/Unidad_I_Programacion_Estructurada/busqueda_lineal_arreglo.c`

```c
#include <stdio.h>

int main() {
    int arr[100];
    int n, buscar, encontrado = 0;
    
    printf("Cuantos datos vas a meter?: ");
    scanf("%d", &n);
    
    for(int i = 0; i < n; i++) {
        printf("Dato [%d]: ", i);
        scanf("%d", &arr[i]);
    }
    
    printf("Que numero buscas?: ");
    scanf("%d", &buscar);
    
    for(int i = 0; i < n; i++) {
        if(arr[i] == buscar) {
            printf("Si esta en la posicion %d\n", i);
            encontrado = 1;
            break;
        }
    }
    
    if(encontrado == 0) {
        printf("No se encontro el numero\n");
    }
    return 0;
}
```

#### Archivo: `invertir_cadena_manual.cpp`
- **Ruta en carpeta:** `fundamentos_programación/repositorio_fundamentos/Unidad_I_Programacion_Estructurada/invertir_cadena_manual.cpp`

```cpp
#include <iostream>
#include <string.h>
using namespace std;

int main() {
    char texto[50];
    char invertido[50];
    
    cout << "Escribe una palabra: ";
    cin >> texto;
    
    int tam = strlen(texto);
    int aux = 0;
    
    for(int i = tam - 1; i >= 0; i--) {
        invertido[aux] = texto[i];
        aux++;
    }
    invertido[aux] = '\0';
    
    cout << "Palabra al reves: " << invertido << endl;
    return 0;
}
```

#### Archivo: `suma_matrices_2x2.c`
- **Ruta en carpeta:** `fundamentos_programación/repositorio_fundamentos/Unidad_I_Programacion_Estructurada/suma_matrices_2x2.c`

```c
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
```

#### Archivo: `sumatoria_1_a_N_do_while_menu.c`
- **Ruta en carpeta:** `fundamentos_programación/repositorio_fundamentos/Unidad_I_Programacion_Estructurada/sumatoria_1_a_N_do_while_menu.c`

```c
#include <stdio.h>

int main() {
    int opc, num, total;
    
    do {
        total = 0;
        printf("\n1. Calcular suma\n2. Salir\nOpcion: ");
        scanf("%d", &opc);
        
        if(opc == 1) {
            printf("Ingresa n: ");
            scanf("%d", &num);
            int j = 1;
            do {
                total += j;
                j++;
            } while(j <= num);
            printf("La suma dio: %d\n", total);
        }
    } while(opc != 2);
    
    return 0;
}
```

#### Archivo: `sumatoria_1_a_N_for.c`
- **Ruta en carpeta:** `fundamentos_programación/repositorio_fundamentos/Unidad_I_Programacion_Estructurada/sumatoria_1_a_N_for.c`

```c
#include <stdio.h>
#include <stdlib.h>

int n, suma = 0; // variables para la operacion

int main() {
    printf("Hasta que numero quieres sumar?: ");
    scanf("%d", &n);
    
    // sumamos todo con el for
    for(int i = 1; i <= n; i++) {
        suma = suma + i;
    }
    
    printf("El resultado de la suma es: %d\n", suma);
    system("pause"); // para que no se cierre la consola
    return 0;
}
```

#### Archivo: `sumatoria_1_a_N_while.cpp`
- **Ruta en carpeta:** `fundamentos_programación/repositorio_fundamentos/Unidad_I_Programacion_Estructurada/sumatoria_1_a_N_while.cpp`

```cpp
#include <iostream>
using namespace std;

int main() {
    int limite;
    int acum = 0;
    int contador = 1;
    
    cout << "Ingresa el limite: ";
    cin >> limite;
    
    // ciclo while hasta llegar al tope
    while(contador <= limite) {
        acum += contador;
        contador++;
    }
    
    cout << "Total acumulado: " << acum << endl;
    return 0;
}
```

---

## Materia: PARADIGMAS PROGRAMACIÓN

### Carpeta: Unidad_III_Lenguajes_Multiparadigma_Uso_Especifico

#### Archivo: `31_patron_observador_notificaciones.cpp`
- **Ruta en carpeta:** `paradigmas_programación/repositorio_paradigmas_programacion/Unidad_III_Lenguajes_Multiparadigma_Uso_Especifico/31_patron_observador_notificaciones.cpp`

```cpp
#include <iostream>
#include <vector>
#include <string>
using namespace std;

class IOyente {
public:
    virtual void actualizar(const string& mensaje) = 0;
};

class CanalNoticias {
private:
    vector<IOyente*> suscriptores;
public:
    void suscribir(IOyente* o) { suscriptores.push_back(o); }
    void publicar(const string& noticia) {
        cout << "\n[Canal]: Publicando nueva noticia..." << endl;
        for(auto s : suscriptores) s->actualizar(noticia);
    }
};

class UsuarioApp : public IOyente {
public:
    string nombre;
    UsuarioApp(string n) : nombre(n) {}
    void actualizar(const string& msg) override {
        cout << nombre << " recibio la notificacion: " << msg << endl;
    }
};

int main() {
    CanalNoticias canal;
    UsuarioApp u1("Elena"), u2("Roberto");
    canal.suscribir(&u1);
    canal.suscribir(&u2);

    canal.publicar("Convocatoria abierta para el IPN 2026");
    return 0;
}
```

#### Archivo: `32_patron_mvc_estudiante.cpp`
- **Ruta en carpeta:** `paradigmas_programación/repositorio_paradigmas_programacion/Unidad_III_Lenguajes_Multiparadigma_Uso_Especifico/32_patron_mvc_estudiante.cpp`

```cpp
#include <iostream>
#include <string>
using namespace std;

// MODELO: datos y logica
class ModeloAlumno {
public:
    string matricula;
    string nombre;
};

// VISTA: representacion visual
class VistaAlumno {
public:
    void mostrarDetalles(string id, string nom) {
        cout << "=== VISTA DEL ALUMNO ===" << endl;
        cout << "Matricula: " << id << " | Nombre: " << nom << endl;
    }
};

// CONTROLADOR: puente entre modelo y vista
class ControladorAlumno {
private:
    ModeloAlumno modelo;
    VistaAlumno vista;
public:
    ControladorAlumno(ModeloAlumno m, VistaAlumno v) : modelo(m), vista(v) {}
    void setNombre(string n) { modelo.nombre = n; }
    void actualizarVista() { vista.mostrarDetalles(modelo.matricula, modelo.nombre); }
};

int main() {
    ModeloAlumno m{"2026630001", "Andrea Ramos"};
    VistaAlumno v;
    ControladorAlumno c(m, v);
    c.actualizarVista();
    c.setNombre("Andrea Ramos Perez");
    c.actualizarVista();
    return 0;
}
```

#### Archivo: `33_gui_simulacion_eventos_boton.cpp`
- **Ruta en carpeta:** `paradigmas_programación/repositorio_paradigmas_programacion/Unidad_III_Lenguajes_Multiparadigma_Uso_Especifico/33_gui_simulacion_eventos_boton.cpp`

```cpp
#include <iostream>
#include <functional>
#include <string>
using namespace std;

class Boton {
public:
    string etiqueta;
    function<void()> alHacerClic; // manejador del evento de clic

    Boton(string txt) : etiqueta(txt) {}

    void clic() {
        cout << "Detectando clic en boton [" << etiqueta << "]..." << endl;
        if(alHacerClic) alHacerClic();
    }
};

int main() {
    Boton btnGuardar("Guardar Proyecto");

    // asignamos el listener / callback al evento
    btnGuardar.alHacerClic = []() {
        cout << "Evento procesado: Datos guardados satisfactoriamente en disco." << endl;
    };

    btnGuardar.clic();
    return 0;
}
```

#### Archivo: `34_servicio_rest_simulacion_endpoints.cpp`
- **Ruta en carpeta:** `paradigmas_programación/repositorio_paradigmas_programacion/Unidad_III_Lenguajes_Multiparadigma_Uso_Especifico/34_servicio_rest_simulacion_endpoints.cpp`

```cpp
#include <iostream>
#include <string>
using namespace std;

// simulacion de endpoints de arquitectura orientada a servicios (SOA / REST)
class ServicioUsuarios {
public:
    void despacharPeticion(string metodo, string ruta) {
        if(metodo == "GET" && ruta == "/api/usuarios") {
            cout << "HTTP 200 OK -> [{\"id\": 1, \"nombre\": \"admin\"}]" << endl;
        } else if(metodo == "POST" && ruta == "/api/usuarios") {
            cout << "HTTP 201 Created -> {\"mensaje\": \"Usuario creado\"}" << endl;
        } else {
            cout << "HTTP 404 Not Found -> Endpoint desconocido" << endl;
        }
    }
};

int main() {
    ServicioUsuarios api;
    api.despacharPeticion("GET", "/api/usuarios");
    api.despacharPeticion("POST", "/api/usuarios");
    api.despacharPeticion("DELETE", "/api/datos");
    return 0;
}
```

#### Archivo: `35_microservicio_registro_usuarios.cpp`
- **Ruta en carpeta:** `paradigmas_programación/repositorio_paradigmas_programacion/Unidad_III_Lenguajes_Multiparadigma_Uso_Especifico/35_microservicio_registro_usuarios.cpp`

```cpp
#include <iostream>
#include <string>
using namespace std;

struct PeticionMicroservicio {
    string email;
    int rolId;
};

class MicroservicioAutenticacion {
public:
    string procesarRegistro(PeticionMicroservicio req) {
        if(req.email.find("@") == string::npos) {
            return "{\"status\": 400, \"error\": \"Email invalido\"}";
        }
        return "{\"status\": 200, \"token\": \"jwt.auth.token.2026\"}";
    }
};

int main() {
    MicroservicioAutenticacion authService;
    PeticionMicroservicio p1{"estudiante_ipn.mx", 1};
    PeticionMicroservicio p2{"estudiante@ipn.mx", 1};

    cout << "Respuesta 1: " << authService.procesarRegistro(p1) << endl;
    cout << "Respuesta 2: " << authService.procesarRegistro(p2) << endl;
    return 0;
}
```

#### Archivo: `36_lenguaje_datos_simulacion_sql.cpp`
- **Ruta en carpeta:** `paradigmas_programación/repositorio_paradigmas_programacion/Unidad_III_Lenguajes_Multiparadigma_Uso_Especifico/36_lenguaje_datos_simulacion_sql.cpp`

```cpp
#include <iostream>
#include <vector>
#include <string>
using namespace std;

struct RegistroTabla {
    int id;
    string producto;
    double precio;
};

// lenguaje de uso especifico (DSL): emulacion de consultas SELECT * WHERE
int main() {
    vector<RegistroTabla> tablaProductos = {
        {1, "Teclado", 450.0},
        {2, "Monitor", 3200.0},
        {3, "Mouse", 250.0},
        {4, "Laptop", 15800.0}
    };

    cout << "SELECT * FROM Productos WHERE precio > 500.0;" << endl;
    for(const auto& fila : tablaProductos) {
        if(fila.precio > 500.0) {
            cout << "ID: " << fila.id << " | " << fila.producto << " | $" << fila.precio << endl;
        }
    }
    return 0;
}
```

#### Archivo: `37_computo_cientifico_algebra_vectorial.cpp`
- **Ruta en carpeta:** `paradigmas_programación/repositorio_paradigmas_programacion/Unidad_III_Lenguajes_Multiparadigma_Uso_Especifico/37_computo_cientifico_algebra_vectorial.cpp`

```cpp
#include <iostream>
#include <vector>
#include <cmath>
using namespace std;

// computo cientifico: calculo de producto punto y norma euclidiana
double productoPunto(const vector<double>& u, const vector<double>& v) {
    double res = 0.0;
    for(size_t i = 0; i < u.size(); i++) res += u[i] * v[i];
    return res;
}

double normaVector(const vector<double>& v) {
    return sqrt(productoPunto(v, v));
}

int main() {
    vector<double> v1 = {3.0, 4.0, 0.0};
    vector<double> v2 = {1.0, 2.0, 2.0};

    cout << "Producto punto v1 . v2: " << productoPunto(v1, v2) << endl;
    cout << "Norma ||v1||: " << normaVector(v1) << endl;
    return 0;
}
```

#### Archivo: `38_ciencia_datos_media_desviacion.cpp`
- **Ruta en carpeta:** `paradigmas_programación/repositorio_paradigmas_programacion/Unidad_III_Lenguajes_Multiparadigma_Uso_Especifico/38_ciencia_datos_media_desviacion.cpp`

```cpp
#include <iostream>
#include <vector>
#include <cmath>
using namespace std;

int main() {
    vector<double> dataset = {14.2, 13.8, 15.1, 14.9, 13.5, 16.0, 14.5};
    double suma = 0.0;
    for(double x : dataset) suma += x;
    double media = suma / dataset.size();

    double sumaDiferencias = 0.0;
    for(double x : dataset) {
        sumaDiferencias += pow(x - media, 2);
    }
    double desviacionEstandar = sqrt(sumaDiferencias / dataset.size());

    cout << "Registros analizados: " << dataset.size() << endl;
    cout << "Media muestral: " << media << endl;
    cout << "Desviacion estandar: " << desviacionEstandar << endl;
    return 0;
}
```

#### Archivo: `39_concurrencia_hilos_std_thread.cpp`
- **Ruta en carpeta:** `paradigmas_programación/repositorio_paradigmas_programacion/Unidad_III_Lenguajes_Multiparadigma_Uso_Especifico/39_concurrencia_hilos_std_thread.cpp`

```cpp
#include <iostream>
#include <thread>
using namespace std;

void tareaConcurrente(int idHilo) {
    cout << "Hilo de ejecucion #" << idHilo << " trabajando en paralelo." << endl;
}

int main() {
    thread t1(tareaConcurrente, 1);
    thread t2(tareaConcurrente, 2);

    cout << "El hilo principal main sigue respondiendo..." << endl;

    t1.join(); // esperamos a que terminen
    t2.join();

    cout << "Ambos hilos finalizaron correctamente." << endl;
    return 0;
}
```

#### Archivo: `40_programacion_asincrona_future_async.cpp`
- **Ruta en carpeta:** `paradigmas_programación/repositorio_paradigmas_programacion/Unidad_III_Lenguajes_Multiparadigma_Uso_Especifico/40_programacion_asincrona_future_async.cpp`

```cpp
#include <iostream>
#include <future>
#include <chrono>
using namespace std;

int tareaAsincrona() {
    // simulamos una espera de computo asincrono
    return 2026 * 2;
}

int main() {
    cout << "Lanzando tarea asincrona con std::async..." << endl;
    future<int> resultadoFuturo = async(launch::async, tareaAsincrona);

    cout << "Haciendo otras actividades mientras la tarea corre..." << endl;

    int valorObtenido = resultadoFuturo.get(); // bloquea solo hasta obtener el resultado
    cout << "Resultado recuperado de la promesa asincrona: " << valorObtenido << endl;
    return 0;
}
```

### Carpeta: Unidad_II_Programacion_Orientada_a_Objetos

#### Archivo: `15_clase_objeto_atributos_metodos.cpp`
- **Ruta en carpeta:** `paradigmas_programación/repositorio_paradigmas_programacion/Unidad_II_Programacion_Orientada_a_Objetos/15_clase_objeto_atributos_metodos.cpp`

```cpp
#include <iostream>
#include <string>
using namespace std;

class Robot {
public:
    string nombre;
    int bateria;

    void presentarse() {
        cout << "Hola, soy el robot " << nombre << " y tengo " << bateria << "% de bateria." << endl;
    }

    void cargarBateria() {
        bateria = 100;
        cout << nombre << " fue cargado al 100%." << endl;
    }
};

int main() {
    Robot r1;
    r1.nombre = "Wall-E";
    r1.bateria = 45;
    r1.presentarse();
    r1.cargarBateria();
    return 0;
}
```

#### Archivo: `16_constructor_destructor_ciclo_vida.cpp`
- **Ruta en carpeta:** `paradigmas_programación/repositorio_paradigmas_programacion/Unidad_II_Programacion_Orientada_a_Objetos/16_constructor_destructor_ciclo_vida.cpp`

```cpp
#include <iostream>
#include <string>
using namespace std;

class ArchivoTemporal {
public:
    string nombreArchivo;

    // constructor
    ArchivoTemporal(string nombre) {
        nombreArchivo = nombre;
        cout << "Creando recurso temporal: " << nombreArchivo << endl;
    }

    // destructor
    ~ArchivoTemporal() {
        cout << "Destruyendo recurso y liberando: " << nombreArchivo << endl;
    }
};

int main() {
    cout << "Inicio del bloque main" << endl;
    {
        ArchivoTemporal temp("datos_sesion.tmp");
    } // aqui se destruye automaticamente
    cout << "Fin del bloque main" << endl;
    return 0;
}
```

#### Archivo: `17_encapsulamiento_modificadores_acceso.cpp`
- **Ruta en carpeta:** `paradigmas_programación/repositorio_paradigmas_programacion/Unidad_II_Programacion_Orientada_a_Objetos/17_encapsulamiento_modificadores_acceso.cpp`

```cpp
#include <iostream>
#include <string>
using namespace std;

class CuentaBancaria {
private:
    double saldo; // protegido contra modificaciones directas

public:
    string titular;

    CuentaBancaria(string t, double sInicial) {
        titular = t;
        saldo = (sInicial >= 0) ? sInicial : 0;
    }

    void depositar(double monto) {
        if(monto > 0) saldo += monto;
    }

    double obtenerSaldo() const {
        return saldo;
    }
};

int main() {
    CuentaBancaria cuenta("Carlos Lopez", 500.0);
    cuenta.depositar(250.0);
    cout << "Titular: " << cuenta.titular << " | Saldo actual: $" << cuenta.obtenerSaldo() << endl;
    return 0;
}
```

#### Archivo: `18_asociacion_clases_profesor_curso.cpp`
- **Ruta en carpeta:** `paradigmas_programación/repositorio_paradigmas_programacion/Unidad_II_Programacion_Orientada_a_Objetos/18_asociacion_clases_profesor_curso.cpp`

```cpp
#include <iostream>
#include <string>
using namespace std;

class Curso; // declaracion adelantada

class Profesor {
public:
    string nombre;
    Profesor(string n) : nombre(n) {}
};

class Curso {
public:
    string titulo;
    Profesor* docente; // asociacion debil por referencia

    Curso(string t, Profesor* p) : titulo(t), docente(p) {}

    void mostrarInfo() {
        cout << "Curso: " << titulo << " impartido por el Prof. " << docente->nombre << endl;
    }
};

int main() {
    Profesor prof("Dr. Garcia");
    Curso materia("Inteligencia Artificial", &prof);
    materia.mostrarInfo();
    return 0;
}
```

#### Archivo: `19_agregacion_computadora_perifericos.cpp`
- **Ruta en carpeta:** `paradigmas_programación/repositorio_paradigmas_programacion/Unidad_II_Programacion_Orientada_a_Objetos/19_agregacion_computadora_perifericos.cpp`

```cpp
#include <iostream>
#include <string>
#include <vector>
using namespace std;

class Periferico {
public:
    string tipo;
    Periferico(string t) : tipo(t) {}
};

class Computadora {
public:
    string modelo;
    vector<Periferico*> componentes; // agregacion: existen independientemente

    Computadora(string m) : modelo(m) {}

    void conectarPeriferico(Periferico* p) {
        componentes.push_back(p);
    }

    void listar() {
        cout << "Computadora " << modelo << " tiene conectados:" << endl;
        for(auto item : componentes) cout << "- " << item->tipo << endl;
    }
};

int main() {
    Periferico teclado("Teclado Mecanico");
    Periferico raton("Mouse Inalambrico");

    Computadora pc("Workstation AI");
    pc.conectarPeriferico(&teclado);
    pc.conectarPeriferico(&raton);
    pc.listar();
    return 0;
}
```

#### Archivo: `20_composicion_automovil_motor.cpp`
- **Ruta en carpeta:** `paradigmas_programación/repositorio_paradigmas_programacion/Unidad_II_Programacion_Orientada_a_Objetos/20_composicion_automovil_motor.cpp`

```cpp
#include <iostream>
#include <string>
using namespace std;

class Motor {
public:
    int potenciaCV;
    Motor(int p) : potenciaCV(p) {
        cout << "Motor de " << potenciaCV << " CV ensamblado." << endl;
    }
    ~Motor() {
        cout << "Motor destruido junto con el vehiculo." << endl;
    }
};

class Automovil {
private:
    Motor motor; // composicion estricta: vive y muere con la clase padre
public:
    string marca;
    Automovil(string m, int cv) : marca(m), motor(cv) {
        cout << "Automovil " << marca << " fabricado." << endl;
    }
};

int main() {
    {
        Automovil auto1("Tesla", 450);
    }
    return 0;
}
```

#### Archivo: `21_herencia_simple_empleado_gerente.cpp`
- **Ruta en carpeta:** `paradigmas_programación/repositorio_paradigmas_programacion/Unidad_II_Programacion_Orientada_a_Objetos/21_herencia_simple_empleado_gerente.cpp`

```cpp
#include <iostream>
#include <string>
using namespace std;

class Empleado {
protected:
    string nombre;
    double salarioBase;
public:
    Empleado(string n, double s) : nombre(n), salarioBase(s) {}

    void mostrarDatos() {
        cout << "Empleado: " << nombre << " | Salario: $" << salarioBase << endl;
    }
};

class Gerente : public Empleado {
private:
    double bono;
public:
    Gerente(string n, double s, double b) : Empleado(n, s), bono(b) {}

    void mostrarSueldoTotal() {
        cout << "Gerente: " << nombre << " | Sueldo con bono: $" << (salarioBase + bono) << endl;
    }
};

int main() {
    Gerente g1("Mariana Sanchez", 35000, 8000);
    g1.mostrarDatos();
    g1.mostrarSueldoTotal();
    return 0;
}
```

#### Archivo: `22_herencia_multiple_anfibio.cpp`
- **Ruta en carpeta:** `paradigmas_programación/repositorio_paradigmas_programacion/Unidad_II_Programacion_Orientada_a_Objetos/22_herencia_multiple_anfibio.cpp`

```cpp
#include <iostream>
using namespace std;

class VehiculoTerrestre {
public:
    void rodar() {
        cout << "Desplazandose con ruedas sobre tierra firme." << endl;
    }
};

class VehiculoAcuatico {
public:
    void navegar() {
        cout << "Navegando con helices a traves del agua." << endl;
    }
};

// herencia multiple heredando de dos clases distintas
class Anfibio : public VehiculoTerrestre, public VehiculoAcuatico {
public:
    void modoOperacion() {
        cout << "Modo anfibio activado:" << endl;
        rodar();
        navegar();
    }
};

int main() {
    Anfibio tanqueAnfibio;
    tanqueAnfibio.modoOperacion();
    return 0;
}
```

#### Archivo: `23_sobreescritura_metodos_virtual.cpp`
- **Ruta en carpeta:** `paradigmas_programación/repositorio_paradigmas_programacion/Unidad_II_Programacion_Orientada_a_Objetos/23_sobreescritura_metodos_virtual.cpp`

```cpp
#include <iostream>
using namespace std;

class Animal {
public:
    virtual void hacerSonido() {
        cout << "Sonido generico de un animal..." << endl;
    }
};

class Perro : public Animal {
public:
    void hacerSonido() override {
        cout << "Guau guau!" << endl;
    }
};

class Gato : public Animal {
public:
    void hacerSonido() override {
        cout << "Miau miau!" << endl;
    }
};

int main() {
    Animal* a1 = new Perro();
    Animal* a2 = new Gato();

    a1->hacerSonido();
    a2->hacerSonido();

    delete a1;
    delete a2;
    return 0;
}
```

#### Archivo: `24_clase_abstracta_figuras.cpp`
- **Ruta en carpeta:** `paradigmas_programación/repositorio_paradigmas_programacion/Unidad_II_Programacion_Orientada_a_Objetos/24_clase_abstracta_figuras.cpp`

```cpp
#include <iostream>
using namespace std;

// clase abstracta pura: no puede instanciarse directamente
class FiguraGeometrica {
public:
    virtual double calcularArea() = 0; // metodo virtual puro
    virtual void imprimir() = 0;
};

class Rectangulo : public FiguraGeometrica {
private:
    double ancho, alto;
public:
    Rectangulo(double a, double h) : ancho(a), alto(h) {}
    double calcularArea() override { return ancho * alto; }
    void imprimir() override { cout << "Rectangulo con area: " << calcularArea() << endl; }
};

int main() {
    FiguraGeometrica* fig = new Rectangulo(4.0, 5.0);
    fig->imprimir();
    delete fig;
    return 0;
}
```

#### Archivo: `25_interfaz_imprimible_serializable.cpp`
- **Ruta en carpeta:** `paradigmas_programación/repositorio_paradigmas_programacion/Unidad_II_Programacion_Orientada_a_Objetos/25_interfaz_imprimible_serializable.cpp`

```cpp
#include <iostream>
#include <string>
using namespace std;

// interfaces puras usando clases abstractas
class IImprimible {
public:
    virtual void imprimir() = 0;
};

class IJSONSerializable {
public:
    virtual string aJSON() = 0;
};

class Sensor : public IImprimible, public IJSONSerializable {
public:
    string tipo;
    double valor;
    Sensor(string t, double v) : tipo(t), valor(v) {}

    void imprimir() override {
        cout << "Sensor [" << tipo << "] lectura: " << valor << endl;
    }

    string aJSON() override {
        return "{\"tipo\": \"" + tipo + "\", \"valor\": " + to_string(valor) + "}";
    }
};

int main() {
    Sensor termometro("Temperatura", 24.5);
    termometro.imprimir();
    cout << "Serializado: " << termometro.aJSON() << endl;
    return 0;
}
```

#### Archivo: `26_polimorfismo_apuntador_clase_base.cpp`
- **Ruta en carpeta:** `paradigmas_programación/repositorio_paradigmas_programacion/Unidad_II_Programacion_Orientada_a_Objetos/26_polimorfismo_apuntador_clase_base.cpp`

```cpp
#include <iostream>
#include <vector>
using namespace std;

class Instrumento {
public:
    virtual void tocar() = 0;
};

class Guitarra : public Instrumento {
public:
    void tocar() override { cout << "Tocar acordes de guitarra." << endl; }
};

class Piano : public Instrumento {
public:
    void tocar() override { cout << "Tocar teclas de piano." << endl; }
};

int main() {
    vector<Instrumento*> orquesta;
    orquesta.push_back(new Guitarra());
    orquesta.push_back(new Piano());

    cout << "Concierto polimorfico:" << endl;
    for(auto inst : orquesta) {
        inst->tocar();
        delete inst;
    }
    return 0;
}
```

#### Archivo: `27_excepcion_basica_division_cero.cpp`
- **Ruta en carpeta:** `paradigmas_programación/repositorio_paradigmas_programacion/Unidad_II_Programacion_Orientada_a_Objetos/27_excepcion_basica_division_cero.cpp`

```cpp
#include <iostream>
#include <stdexcept>
using namespace std;

double dividir(double a, double b) {
    if(b == 0.0) {
        throw runtime_error("Error matematico: intento de division por cero");
    }
    return a / b;
}

int main() {
    try {
        cout << "10 / 2 = " << dividir(10, 2) << endl;
        cout << "10 / 0 = " << dividir(10, 0) << endl;
    } catch(const exception& e) {
        cout << "Excepcion capturada en el bloque catch: " << e.what() << endl;
    }
    return 0;
}
```

#### Archivo: `28_excepcion_personalizada_heredada.cpp`
- **Ruta en carpeta:** `paradigmas_programación/repositorio_paradigmas_programacion/Unidad_II_Programacion_Orientada_a_Objetos/28_excepcion_personalizada_heredada.cpp`

```cpp
#include <iostream>
#include <exception>
#include <string>
using namespace std;

class SaldoInsuficienteException : public exception {
private:
    string mensaje;
public:
    SaldoInsuficienteException(double requerido, double actual) {
        mensaje = "Saldo insuficiente: requieres $" + to_string(requerido) + 
                  " pero solo tienes $" + to_string(actual);
    }
    const char* what() const noexcept override {
        return mensaje.c_str();
    }
};

void retirar(double saldo, double monto) {
    if(monto > saldo) {
        throw SaldoInsuficienteException(monto, saldo);
    }
    cout << "Retiro de $" << monto << " exitoso." << endl;
}

int main() {
    try {
        retirar(200.0, 500.0);
    } catch(const SaldoInsuficienteException& e) {
        cout << "Excepcion personalizada capturada: " << e.what() << endl;
    }
    return 0;
}
```

#### Archivo: `29_excepciones_encadenadas_rethrow.cpp`
- **Ruta en carpeta:** `paradigmas_programación/repositorio_paradigmas_programacion/Unidad_II_Programacion_Orientada_a_Objetos/29_excepciones_encadenadas_rethrow.cpp`

```cpp
#include <iostream>
#include <stdexcept>
using namespace std;

void servicioInterno() {
    try {
        throw runtime_error("Fallo de conexion en capa baja de red");
    } catch(...) {
        cout << "Registrando error en bitacora interna..." << endl;
        throw; // rethrow relanzando la excepcion
    }
}

int main() {
    try {
        servicioInterno();
    } catch(const exception& e) {
        cout << "Excepcion relanzada atrapada en main: " << e.what() << endl;
    }
    return 0;
}
```

#### Archivo: `30_plantilla_clase_contenedor_generico.cpp`
- **Ruta en carpeta:** `paradigmas_programación/repositorio_paradigmas_programacion/Unidad_II_Programacion_Orientada_a_Objetos/30_plantilla_clase_contenedor_generico.cpp`

```cpp
#include <iostream>
#include <string>
using namespace std;

template <typename T>
class Caja {
private:
    T contenido;
public:
    void guardar(T valor) { contenido = valor; }
    T abrir() { return contenido; }
};

int main() {
    Caja<int> cajaEnteros;
    cajaEnteros.guardar(1024);
    cout << "Contenido entero: " << cajaEnteros.abrir() << endl;

    Caja<string> cajaCadenas;
    cajaCadenas.guardar("Modelo de Red Neuronal");
    cout << "Contenido texto: " << cajaCadenas.abrir() << endl;
    return 0;
}
```

### Carpeta: Unidad_I_Introduccion_y_Paradigmas

#### Archivo: `01_imperativo_suma_arreglo_iterativo.c`
- **Ruta en carpeta:** `paradigmas_programación/repositorio_paradigmas_programacion/Unidad_I_Introduccion_y_Paradigmas/01_imperativo_suma_arreglo_iterativo.c`

```c
#include <stdio.h>

// estilo imperativo: le decimos a la maquina paso a paso que hacer
int main() {
    int datos[5] = {10, 20, 30, 40, 50};
    int suma = 0;
    
    // modificamos el estado de la variable suma en cada vuelta
    for(int i = 0; i < 5; i++) {
        suma = suma + datos[i];
    }
    
    printf("Suma estilo imperativo: %d\n", suma);
    return 0;
}
```

#### Archivo: `02_declarativo_suma_arreglo_stl.cpp`
- **Ruta en carpeta:** `paradigmas_programación/repositorio_paradigmas_programacion/Unidad_I_Introduccion_y_Paradigmas/02_declarativo_suma_arreglo_stl.cpp`

```cpp
#include <iostream>
#include <vector>
#include <numeric>
using namespace std;

// estilo declarativo: decimos que queremos obtener sin ciclos manuales
int main() {
    vector<int> datos = {10, 20, 30, 40, 50};
    
    // usamos accumulate para expresar la suma directamente
    int suma = accumulate(datos.begin(), datos.end(), 0);
    
    cout << "Suma estilo declarativo: " << suma << endl;
    return 0;
}
```

#### Archivo: `03_funcion_pura_potencia.c`
- **Ruta en carpeta:** `paradigmas_programación/repositorio_paradigmas_programacion/Unidad_I_Introduccion_y_Paradigmas/03_funcion_pura_potencia.c`

```c
#include <stdio.h>

// funcion pura: no altera variables globales ni tiene efectos secundarios
int potenciaPura(int base, int exponente) {
    if(exponente == 0) return 1;
    return base * potenciaPura(base, exponente - 1);
}

int main() {
    int b = 3, e = 4;
    printf("%d elevado a %d es: %d\n", b, e, potenciaPura(b, e));
    printf("Si la volvemos a llamar da lo mismo: %d\n", potenciaPura(b, e));
    return 0;
}
```

#### Archivo: `04_funcion_orden_superior_mapeo.cpp`
- **Ruta en carpeta:** `paradigmas_programación/repositorio_paradigmas_programacion/Unidad_I_Introduccion_y_Paradigmas/04_funcion_orden_superior_mapeo.cpp`

```cpp
#include <iostream>
#include <vector>
#include <functional>
using namespace std;

// funcion de orden superior: recibe otra funcion como argumento
void mapear(const vector<int>& entrada, function<int(int)> operacion) {
    for(int x : entrada) {
        cout << operacion(x) << " ";
    }
    cout << endl;
}

int doble(int n) { return n * 2; }
int cuadrado(int n) { return n * n; }

int main() {
    vector<int> nums = {1, 2, 3, 4, 5};
    cout << "Dobles: ";
    mapear(nums, doble);
    cout << "Cuadrados: ";
    mapear(nums, cuadrado);
    return 0;
}
```

#### Archivo: `05_expresion_lambda_captura.cpp`
- **Ruta en carpeta:** `paradigmas_programación/repositorio_paradigmas_programacion/Unidad_I_Introduccion_y_Paradigmas/05_expresion_lambda_captura.cpp`

```cpp
#include <iostream>
#include <vector>
#include <algorithm>
using namespace std;

int main() {
    vector<int> lista = {5, 12, 8, 25, 3, 30};
    int limite = 10;
    int contador = 0;

    // expresion lambda con captura por valor y referencia
    auto esMayor = [limite, &contador](int num) {
        if(num > limite) {
            contador++;
            return true;
        }
        return false;
    };

    cout << "Numeros mayores que " << limite << ": ";
    for(int x : lista) {
        if(esMayor(x)) cout << x << " ";
    }
    cout << "\nTotal de numeros encontrados: " << contador << endl;
    return 0;
}
```

#### Archivo: `06_currificacion_aritmetica_funciones.cpp`
- **Ruta en carpeta:** `paradigmas_programación/repositorio_paradigmas_programacion/Unidad_I_Introduccion_y_Paradigmas/06_currificacion_aritmetica_funciones.cpp`

```cpp
#include <iostream>
#include <functional>
using namespace std;

// currificacion: funcion que devuelve otra funcion
function<int(int)> multiplicador(int factor) {
    return [factor](int x) {
        return factor * x;
    };
}

int main() {
    auto triplicar = multiplicador(3);
    auto quintuplicar = multiplicador(5);

    cout << "Triplicar 7: " << triplicar(7) << endl;
    cout << "Quintuplicar 7: " << quintuplicar(7) << endl;
    return 0;
}
```

#### Archivo: `07_composicion_funciones.cpp`
- **Ruta en carpeta:** `paradigmas_programación/repositorio_paradigmas_programacion/Unidad_I_Introduccion_y_Paradigmas/07_composicion_funciones.cpp`

```cpp
#include <iostream>
#include <functional>
using namespace std;

// composicion matematica: f(g(x))
function<int(int)> componer(function<int(int)> f, function<int(int)> g) {
    return [f, g](int x) {
        return f(g(x));
    };
}

int sumarCinco(int a) { return a + 5; }
int porDos(int b) { return b * 2; }

int main() {
    auto sumarYMultiplicar = componer(porDos, sumarCinco); // (x + 5) * 2
    int valor = 10;
    cout << "Resultado de componer f(g(10)): " << sumarYMultiplicar(valor) << endl;
    return 0;
}
```

#### Archivo: `08_evaluacion_perezosa_lazy.cpp`
- **Ruta en carpeta:** `paradigmas_programación/repositorio_paradigmas_programacion/Unidad_I_Introduccion_y_Paradigmas/08_evaluacion_perezosa_lazy.cpp`

```cpp
#include <iostream>
#include <functional>
using namespace std;

// simulacion de lazy evaluation: el calculo pesado solo se ejecuta si se necesita
int operacionPesada() {
    cout << "[Ejecutando calculo costoso en la CPU...]" << endl;
    return 42 * 100;
}

void evaluar(bool condicion, function<int()> calculo) {
    if(condicion) {
        cout << "Condicion verdadera, resultado: " << calculo() << endl;
    } else {
        cout << "Condicion falsa, no se gasto tiempo calculando." << endl;
    }
}

int main() {
    evaluar(false, operacionPesada);
    evaluar(true, operacionPesada);
    return 0;
}
```

#### Archivo: `09_recursion_sobre_listas_funcional.cpp`
- **Ruta en carpeta:** `paradigmas_programación/repositorio_paradigmas_programacion/Unidad_I_Introduccion_y_Paradigmas/09_recursion_sobre_listas_funcional.cpp`

```cpp
#include <iostream>
#include <vector>
using namespace std;

// procesamiento recursivo de lista sin usar for ni while
int sumaListaRec(const vector<int>& v, int indice) {
    if(indice == v.size()) return 0; // caso base
    return v[indice] + sumaListaRec(v, indice + 1); // paso recursivo
}

int main() {
    vector<int> nums = {4, 8, 15, 16, 23, 42};
    cout << "Suma recursiva pura de la lista: " << sumaListaRec(nums, 0) << endl;
    return 0;
}
```

#### Archivo: `10_polimorfismo_funcional_plantillas.cpp`
- **Ruta en carpeta:** `paradigmas_programación/repositorio_paradigmas_programacion/Unidad_I_Introduccion_y_Paradigmas/10_polimorfismo_funcional_plantillas.cpp`

```cpp
#include <iostream>
#include <string>
using namespace std;

// funcion polimorfica que opera con cualquier tipo de dato
template <typename T>
T duplicarContenido(T valor) {
    return valor + valor;
}

int main() {
    cout << "Entero duplicado: " << duplicarContenido(25) << endl;
    cout << "Flotante duplicado: " << duplicarContenido(3.14) << endl;
    cout << "Cadena duplicada: " << duplicarContenido(string("Paradigmas_")) << endl;
    return 0;
}
```

#### Archivo: `11_logico_base_hechos_consultas.cpp`
- **Ruta en carpeta:** `paradigmas_programación/repositorio_paradigmas_programacion/Unidad_I_Introduccion_y_Paradigmas/11_logico_base_hechos_consultas.cpp`

```cpp
#include <iostream>
#include <vector>
#include <string>
using namespace std;

// hechos de base de conocimiento: leGusta(Persona, Cosa)
struct Hecho {
    string persona;
    string cosa;
};

vector<Hecho> baseHechos = {
    {"juan", "pizza"},
    {"maria", "tacos"},
    {"juan", "helado"},
    {"pedro", "pizza"}
};

// consulta logica: verificar si el hecho existe
bool consultar(string p, string c) {
    for(const auto& h : baseHechos) {
        if(h.persona == p && h.cosa == c) return true;
    }
    return false;
}

int main() {
    cout << "Le gusta a juan la pizza?: " << (consultar("juan", "pizza") ? "SI" : "NO") << endl;
    cout << "Le gusta a maria el helado?: " << (consultar("maria", "helado") ? "SI" : "NO") << endl;
    return 0;
}
```

#### Archivo: `12_logico_reglas_inferencia_familia.cpp`
- **Ruta en carpeta:** `paradigmas_programación/repositorio_paradigmas_programacion/Unidad_I_Introduccion_y_Paradigmas/12_logico_reglas_inferencia_familia.cpp`

```cpp
#include <iostream>
#include <vector>
#include <string>
using namespace std;

struct Progenitor {
    string padre;
    string hijo;
};

vector<Progenitor> familia = {
    {"carlos", "ana"},
    {"carlos", "luis"},
    {"luis", "mateo"}
};

// regla logica: X e Y son hermanos si comparten progenitor y son distintos
bool sonHermanos(string a, string b) {
    if(a == b) return false;
    for(auto p1 : familia) {
        if(p1.hijo == a) {
            for(auto p2 : familia) {
                if(p2.hijo == b && p1.padre == p2.padre) return true;
            }
        }
    }
    return false;
}

int main() {
    cout << "Ana y Luis son hermanos?: " << (sonHermanos("ana", "luis") ? "SI" : "NO") << endl;
    cout << "Ana y Mateo son hermanos?: " << (sonHermanos("ana", "mateo") ? "SI" : "NO") << endl;
    return 0;
}
```

#### Archivo: `13_logico_regla_recursiva_ancestro.cpp`
- **Ruta en carpeta:** `paradigmas_programación/repositorio_paradigmas_programacion/Unidad_I_Introduccion_y_Paradigmas/13_logico_regla_recursiva_ancestro.cpp`

```cpp
#include <iostream>
#include <vector>
#include <string>
using namespace std;

struct Relacion {
    string padre;
    string hijo;
};

vector<Relacion> arbol = {
    {"manuel", "jorge"},
    {"jorge", "alberto"},
    {"alberto", "sofia"}
};

// regla recursiva: ancestro(A, B) :- padre(A, B)
// ancestro(A, B) :- padre(A, Z), ancestro(Z, B)
bool esAncestro(string a, string b) {
    for(auto r : arbol) {
        if(r.padre == a && r.hijo == b) return true;
        if(r.padre == a) {
            if(esAncestro(r.hijo, b)) return true;
        }
    }
    return false;
}

int main() {
    cout << "Manuel es ancestro de Sofia?: " << (esAncestro("manuel", "sofia") ? "SI" : "NO") << endl;
    cout << "Alberto es ancestro de Manuel?: " << (esAncestro("alberto", "manuel") ? "SI" : "NO") << endl;
    return 0;
}
```

#### Archivo: `14_logico_calculo_predicados_cuantificadores.cpp`
- **Ruta en carpeta:** `paradigmas_programación/repositorio_paradigmas_programacion/Unidad_I_Introduccion_y_Paradigmas/14_logico_calculo_predicados_cuantificadores.cpp`

```cpp
#include <iostream>
#include <vector>
#include <algorithm>
using namespace std;

int main() {
    vector<int> edades = {20, 22, 19, 25, 30};

    // predicado P(x): x >= 18
    auto esMayorDeEdad = [](int e) { return e >= 18; };

    // cuantificador universal: Para todo x en edades, P(x)
    bool todosMayores = all_of(edades.begin(), edades.end(), esMayorDeEdad);

    // predicado Q(x): x >= 30
    auto tieneTreinta = [](int e) { return e >= 30; };

    // cuantificador existencial: Existe x en edades tal que Q(x)
    bool existeTreinta = any_of(edades.begin(), edades.end(), tieneTreinta);

    cout << "Para todo x: Son todos mayores de edad?: " << (todosMayores ? "VERDADERO" : "FALSO") << endl;
    cout << "Existe x: Hay alguien de al menos 30 anios?: " << (existeTreinta ? "VERDADERO" : "FALSO") << endl;
    return 0;
}
```

---

