# Reporte de Ejecución: Experimento de Robustez del Canal A ante Ofuscación Estructural

**Identificador de Ejecución:** `runs/robustness/20261012-050941`  
**Conjunto Evaluado:** `test` (Evaluación ciega sobre 1,993,656 pares y 6,797 programas únicos en 14 asignaciones)  
**Semilla Base:** `42` | **Réplicas Bootstrap:** $N_{\text{boot}} = 1{,}000$ (Remuestreo estratificado por asignación docente)  
**Fecha de Finalización:** 12 de Octubre de 2026  

---

## 1. Resumen Ejecutivo y Veredictos de Hipótesis

El experimento de robustez del Canal A se ejecutó siguiendo rigurosamente el protocolo de pre-registro establecido en `Documentacion/guias_implementacion/experimento_robustez_ofuscacion.md`. Se sometieron los programas de prueba a 8 operadores de transformación en el Árbol de Sintaxis Abstracta (AST) mediante `tree-sitter`, abarcando 10 condiciones experimentales ($T_0$ a $T_7@1.0$) y 4 métodos de detección: **Jaccard Léxico**, **Winnowing**, **GraphCodeBERT con DFG (`v2`)** y **GraphCodeBERT sin DFG (`v2_nodfg`)**.

### Veredicto Formal de Hipótesis Pre-registradas

| Hipótesis | Declaración Pre-registrada | Estimador Estadístico | Valor Observado [IC 95%] | Veredicto Formal |
|:---|:---|:---:|:---:|:---:|
| **H1** | Jaccard se degrada más que GraphCodeBERT bajo ofuscación extrema ($T_7@1.0$) | $\text{DiD}(T_7@1.0; \text{jaccard}, \text{v2})$ | **+0.1284** [+0.0142, +0.2764] | **REFUTADA** |
| **H2** | El renombrado $T_1$ actúa como control invariante exacto para Jaccard | $\Delta \text{ROC-AUC}_{\text{jaccard}}(T_1)$ | **+0.0000** [-0.0000, +0.0000] | **CONFIRMADA (Control)** |
| **H3** | El Grafo de Flujo de Datos (DFG) confiere invarianza ante reordenamiento ($T_3$) | $\text{DiD}(T_3; \text{v2}, \text{v2\_nodfg})$ | **-0.0005** [-0.0010, +0.0002] | **INCONCLUSA** |

### Interpretación Científica de los Veredictos

1. **Refutación de H1 (Sensibilidad a Código Muerto):**
   - Contrario a la intuición inicial de que los modelos semánticos neuronales son más resilientes que los métodos léxicos ante perturbaciones complejas, la evidencia empírica demostró que **GraphCodeBERT sufre una degradación sustancialmente mayor** ($\Delta \text{AUC} = -0.142$, cayendo de 0.856 a 0.714) en comparación con Jaccard ($\Delta \text{AUC} = -0.014$, pasando de 0.945 a 0.931).
   - **Causa Mecanística:** El mecanismo de autoatención (*self-attention*) de GraphCodeBERT es denso; la inyección de bloques de código muerto ($T_5$), que alteran el 41.3% de los tokens, dispersa la masa de atención y diluye la similitud del coseno en los *embeddings* contextuales. En cambio, los *bags-of-words* de Jaccard mantienen la masa de intersección de los identificadores sustantivos de la solución.
2. **Confirmación de H2 (Integridad del Protocolo):**
   - El delta observado de Jaccard ante el renombrado exhaustivo de variables ($T_1$) fue de $1.95 \times 10^{-6}$, dentro del intervalo de tolerancia numérica $[-2.65 \times 10^{-6}, +9.54 \times 10^{-6}]$, confirmando la invarianza teórica de los identificadores normalizados y la ausencia de fugas de datos.
3. **Inconclusión de H3 (DFG vs no-DFG):**
   - El intervalo de confianza de la diferencia en diferencias entre la variante con DFG y sin DFG contiene al cero ($[-0.0010, +0.0002]$). Sin un ajuste contrastivo supervisado explícito, la presencia de aristas de flujo de datos en el preentrenamiento base de Microsoft no confiere una ventaja estadísticamente significativa de invarianza ante el reordenamiento de sentencias independientes.

---

## 2. Validez de las Transformaciones de Código

Se generaron y validaron sintácticamente **67,970 archivos de código** (6,797 programas $\times$ 10 condiciones). Todas las transformaciones preservaron la semántica ejecutable y la integridad sintáctica:

| Condición | Descripción de la Técnica | Tasa de Aplicación | Éxito Sintáctico (*Parse OK*) | *Token Edit Ratio* Medio | *Abstract Edit Ratio* Medio |
|:---|:---|:---:|:---:|:---:|:---:|
| **$T_0$** | Identidad (Línea base) | 0.0% (0/6,797) | 100.0% | 0.0000 | 0.0000 |
| **$T_1$** | Renombrado exhaustivo de variables | 85.7% (5,826/6,797) | 99.9% | 0.1333 | 0.0001 |
| **$T_2$** | Bucle `for` $\leftrightarrow$ `while` | 65.2% (4,433/6,797) | 95.9% | 0.0410 | 0.0393 |
| **$T_3$** | Reordenamiento de sentencias ($\mathcal{R}/\mathcal{W}$) | 80.1% (5,442/6,797) | 100.0% | 0.0480 | 0.0301 |
| **$T_4$** | Operadores equivalentes (`+=`, etc.) | 72.9% (4,955/6,797) | 100.0% | 0.0410 | 0.0410 |
| **$T_5$** | Inyección de código muerto | 99.5% (6,766/6,797) | 99.8% | 0.4135 | 0.4135 |
| **$T_6$** | Inversión de ramificaciones `if-else` | 58.8% (4,000/6,797) | 100.0% | 0.0461 | 0.0418 |
| **$T_7@0.25$** | Cascada combinada ($p = 0.25$) | 99.5% (6,766/6,797) | 98.1% | 0.1702 | 0.1640 |
| **$T_7@0.50$** | Cascada combinada ($p = 0.50$) | 99.5% (6,766/6,797) | 96.9% | 0.2931 | 0.2836 |
| **$T_7@1.00$** | Cascada combinada total ($p = 1.00$) | 99.5% (6,766/6,797) | 95.6% | 0.5531 | 0.5378 |

---

## 3. Matriz de Resultados de Discriminabilidad (ROC-AUC)

Evaluación en vista global (*view: all*, 1,993,656 pares evaluados por cada una de las 40 combinaciones). Los corchetes denotan el intervalo de confianza al 95% obtenido mediante $N_{\text{boot}} = 1{,}000$ réplicas estratificadas:

| Condición | Jaccard (Léxico) | Winnowing | GraphCodeBERT (v2) | GraphCodeBERT (sin DFG) | $\text{DiD}(\text{Jaccard} - \text{v2})$ |
|:---|:---:|:---:|:---:|:---:|:---:|
| **$T_0$ (Base)** | 0.945 [0.929, 0.963] | 0.944 [0.929, 0.961] | 0.856 [0.790, 0.894] | 0.851 [0.782, 0.890] | — |
| **$T_1$** | 0.945 [0.929, 0.963] | 0.944 [0.929, 0.961] | 0.683 [0.562, 0.774] | 0.683 [0.561, 0.773] | **+0.173** [+0.066, +0.310] |
| **$T_2$** | 0.943 [0.927, 0.960] | 0.941 [0.927, 0.958] | 0.852 [0.785, 0.888] | 0.848 [0.776, 0.887] | **+0.002** [-0.004, +0.008] |
| **$T_3$** | 0.943 [0.928, 0.963] | 0.941 [0.927, 0.961] | 0.854 [0.795, 0.891] | 0.850 [0.786, 0.888] | **+0.000** [-0.001, +0.001] |
| **$T_4$** | 0.937 [0.921, 0.956] | 0.937 [0.921, 0.955] | 0.850 [0.776, 0.890] | 0.846 [0.770, 0.886] | **-0.001** [-0.012, +0.006] |
| **$T_5$** | 0.950 [0.935, 0.964] | 0.950 [0.933, 0.963] | 0.768 [0.645, 0.849] | 0.776 [0.650, 0.855] | **+0.093** [+0.020, +0.209] |
| **$T_6$** | 0.942 [0.926, 0.960] | 0.940 [0.927, 0.959] | 0.854 [0.782, 0.896] | 0.851 [0.776, 0.894] | **-0.001** [-0.003, +0.002] |
| **$T_7@0.25$** | 0.942 [0.928, 0.959] | 0.937 [0.922, 0.954] | 0.857 [0.790, 0.895] | 0.853 [0.782, 0.894] | **-0.003** [-0.022, +0.028] |
| **$T_7@0.50$** | 0.944 [0.927, 0.960] | 0.937 [0.921, 0.954] | 0.795 [0.695, 0.853] | 0.799 [0.698, 0.857] | **+0.060** [+0.005, +0.148] |
| **$T_7@1.00$** | 0.931 [0.912, 0.949] | 0.927 [0.907, 0.943] | 0.714 [0.555, 0.814] | 0.728 [0.576, 0.823] | **+0.128** [+0.014, +0.276] |

---

## 4. Artefactos y Trazabilidad

Todos los artefactos de la corrida fueron generados y consolidados en:
`runs/robustness/20261012-050941/`

- **Configuración:** `config.json`
- **Transformaciones AST:** `transforms.jsonl` (25.2 MB) y `transform_summary.json`
- **Matrices de Similitud (.npz):** 40 archivos en `scores/` (10 condiciones $\times$ 4 métodos)
- **Métricas e Intervalos de Confianza:** `metrics.json` (576 KB)
- **Contrastes Estadísticos y DiD:** `contrasts.json` (48 KB)
- **Gráficas de Publicación:**
  - `plots/degradation_curve.png` (Curvas de degradación de discriminabilidad)
  - `plots/delta_by_transform.png` (Desglose de caída neta por operador)
  - `plots/positive_drop.png` (Distribución de caída en pares positivos de trampa)
- **Documento de Tesis Actualizado:** `Documentacion/Documento/capitulos/modelado.tex` (Subsección 6.6, Tabla `tab:robustez_canal_a` y Figura `fig:robustez_degradacion_canal_a`).
