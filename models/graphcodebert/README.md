# GraphCodeBERT — Canal Semántico de Graphito

Extracción de embeddings semánticos mediante `microsoft/graphcodebert-base` con atención guiada por Grafos de Flujo de Datos (DFG).

## Arquitectura

```
Código C/C++ → tree-sitter AST → DFG (def-use chains)
                                     ↓
               Tokenización BPE + Position IDs + DFG node embeddings
                                     ↓
               GraphCodeBERT (RoBERTa-base, 125M params, congelado)
                                     ↓
               Embedding semántico [CLS] (768-dim)
```

## DFG Extractor

`DFGExtractor` usa `tree-sitter-c` y `tree-sitter-cpp` para:

1. Parsear el AST del código fuente
2. Recorrer el AST recolectando tokens terminales
3. Identificar relaciones def-use:
   - `declaration` + `init_declarator` → definición de variable
   - `assignment_expression` → `computedFrom` (RHS vars → LHS var)
   - `update_expression` (`i++`, `++i`) → self-loop
   - `if_statement` / `for_statement` / `while_statement` → merge de ramas
   - `return_statement` → `comesFrom`
4. Producir `DFGResult` con `code_tokens`, `dfg_edges`, `index_to_code`

**Fallback**: si el parseo falla (código malformado), se usa modo texto sin DFG.

## GraphCodeBERT Inference

`GraphCodeBERTInference` construye el input graph-aware:

1. Tokeniza los `code_tokens` con el tokenizer BPE de RoBERTa
2. Para cada nodo DFG, calcula qué subtokens de código cubre
3. Construye `position_ids`: 2..n+1 para código, 0 para nodos DFG
4. Inyecta embeddings de nodos DFG como promedio de los embeddings de sus source tokens
5. Forward pass → extrae `[CLS]` embedding (768-dim)

**Salida**: diccionario con `embedding`, `language`, `dfg_node_count`, `used_graph`

## Integración con Canal B

```python
from models.graphcodebert.inference import GraphCodeBERTInference
from models.fusion import BimodalFusion

gcb = GraphCodeBERTInference()
fusion = BimodalFusion(gcb, charcnn_engine)

# Fuse student code
result = fusion.fuse(Path("entrega.c"))
# → FusionResult con fused_vector 1792-dim = [sem(768) | style(1024)]

# Compare against references
results = fusion.compare(student_path, reference_paths)
# → similitud asimétrica: penaliza código sintético en el denominador
```

## Dependencias

```
tree-sitter
tree-sitter-c
tree-sitter-cpp
transformers
torch
```

El modelo `microsoft/graphcodebert-base` (~500MB) se descarga automáticamente al primer uso y se cachea en `modelos/weights/`.

## Limitaciones

- GraphCodeBERT fue preentrenado en Python, Java, JS, Go, Ruby, PHP — **no en C/C++**. Los embeddings son cross-lingual zero-shot.
- DFG limitado a patrones sintácticos; no resuelve aliasing de punteros.
- Sequence length máximo: 514 posiciones (límite de RoBERTa-base).
- El modelo se usa en modo feature-extraction (congelado), sin fine-tuning.
