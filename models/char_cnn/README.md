# CharCNN — Canal Estilométrico de Graphito

Clasificador binario basado en [Zhang et al. 2015](https://arxiv.org/abs/1509.01626) que detecta código C/C++ generado por LLMs analizando patrones de escritura a nivel de caracteres.

## Arquitectura

```
Código raw → Embedding (256d) → 6× Conv1D + MaxPool → Flatten → FC(1024) → FC(1024) → [humano | sintético]
                                                                                   └→ Embedding de autoría (1024d)
```

| Capa | Kernel | Filtros | Pool | Salida |
|---|---|---|---|---|
| Embedding | — | — | — | `(B, 256, 2048)` |
| Conv1 + ReLU | 7 | 256 | 3 | `(B, 256, 680)` |
| Conv2 + ReLU | 7 | 256 | 3 | `(B, 256, 224)` |
| Conv3 + ReLU | 3 | 256 | — | `(B, 256, 222)` |
| Conv4 + ReLU | 3 | 256 | — | `(B, 256, 220)` |
| Conv5 + ReLU | 3 | 256 | — | `(B, 256, 218)` |
| Conv6 + ReLU | 3 | 256 | 3 | `(B, 256, 72)` |
| Flatten | — | — | — | `(B, 18432)` |
| FC1 + ReLU + Dropout(0.5) | — | — | — | `(B, 1024)` |
| FC2 + ReLU + Dropout(0.5) | — | — | — | `(B, 1024)` |
| FC3 | — | — | — | `(B, 2)` |

**Total: 21.6M parámetros.**

## Preprocesamiento

1. El código fuente se preserva **raw** (indentación, comentarios, acentos, caracteres especiales).
2. Se mapea carácter por carácter a índices usando un alfabeto de **122 símbolos** que cubre C/C++, español y bosnio/serbio/croata.
3. Secuencias fijas de **2048 caracteres** (truncado o padding).

## Dataset

- **Label 0 (humano):** `data/raw/src/` — 43,792 archivos de estudiantes reales.
- **Label 1 (sintético):** `data/output/` — código generado por LLMs (3 perfiles: descuidado, aplicado, kompaktan).

`prepare_dataset.py` balancea por subproblema (`curso/asignacion/subproblema`) tomando igual cantidad de muestras humanas y sintéticas, con split 70/15/15.

## Entrenamiento

- **Loss:** CrossEntropy
- **Optimizador:** Adam (lr=0.001, weight_decay=1e-4)
- **Scheduler:** ReduceLROnPlateau (factor=0.5, paciencia=3)
- **Early stopping:** 7 epochs sin mejora en val_loss
- **Regularización:** Dropout 0.5 entre capas FC
- **Métricas:** accuracy, precision, recall, F1

## Inferencia

`CharCNNInference` expone dos modos:

```python
engine = CharCNNInference("modelos/weights/char_cnn_best.pth")

# Desde archivo
result = engine.predict(Path("entrega.c"))
# → {prediction: "humano"|"sintético", confidence, prob_humano, prob_sintetico, embedding}

# Desde texto
result = engine.predict_text("int main() { ... }")
```

El **embedding de autoría** (1024-dim) es el vector que se usa en la fusión bimodal con GraphCodeBERT.

## Uso

```bash
source .venv/bin/activate

# Preparar dataset
PYTHONPATH=. python models/char_cnn/prepare_dataset.py --max-samples 200

# Entrenar
PYTHONPATH=. python models/char_cnn/train.py --epochs 50 --batch-size 128

# Inferir
PYTHONPATH=. python models/char_cnn/inference.py modelos/weights/char_cnn_best.pth archivo.c
```

## Integración con Graphito (Canal B)

En el sistema completo, CharCNN actúa como **Canal Estilométrico**:

1. Recibe código raw del estudiante (preprocesado por `Preprocesador` con preservación de formato).
2. Produce `prob_sintetico` (escalar) y `embedding` (vector 1024d).
3. La **fusión bimodal** concatena el embedding semántico de GraphCodeBERT con el embedding de autoría de CharCNN.
4. La similitud del coseno asimétrica penaliza automáticamente vectores con carga sintética alta.
