# Plan: curva de aprendizaje de CharCNN según la cantidad de código de IA

**Pregunta:** ¿el desempeño de CharCNN seguiría mejorando con más código generado por IA, o ya se
saturó con las muestras disponibles?

**Para qué sirve en la tesis:** justificar con evidencia el tamaño final de la clase sintética
(capítulo de Ingeniería de datos, Adquisición) en lugar de la cifra de la planeación (20,000 códigos).

**Alcance:** solo se reentrena CharCNN v2 con subconjuntos de los datos de entrenamiento. No se generan
códigos nuevos, no se tocan los artefactos desplegados (`models/deploy/`) ni `models/char_cnn/best_model.pth`.

---

## 0. Datos (verificados el 13 de octubre de 2026)

Entradas no excluidas de `data/splits/split_v1.json.gz`:

| Split | Humanos | IA |
|---|---|---|
| train | 24,810 | **897** |
| val | 6,808 | 225 |
| test | 9,318 | 331 |

Corrida de referencia: `runs/char_cnn/20261011-015734` (38 épocas de ~6 s; época elegida: 30).
Cada corrida completa tarda unos 5 minutos con evaluación, lo que permite muchos puntos y semillas.

---

## 1. Diseño (pre-registro)

### 1.1 Qué se varía
- **Variable:** número de códigos de IA en **train**.
- **Fracciones (12 puntos):** 5, 10, 15, 20, 30, 40, 50, 60, 70, 80, 90 y 100 % de los 897 (≈45 a 897 códigos).
- **Humanos:** se mantienen completos (24,810). Así la curva mide solo el efecto de la clase escasa.
- **Semillas:** 5 por fracción (42, 7, 123, 2024, 31337) → **60 corridas**, unas 5 horas.

### 1.2 Cómo se toman los subconjuntos
- **Por `dup_group`**, no por archivo, para que dos copias no queden separadas.
- **Estratificado por tarea:** cada fracción conserva la proporción de tareas del total.
- **Anidados por semilla:** con la misma semilla, el subconjunto del 10 % está contenido en el del
  20 %, el del 20 % en el del 30 %, etc. Esto hace la curva más suave, porque cada punto solo *agrega*
  datos al anterior.
- Implementación: por semilla, se fija una permutación aleatoria de los grupos dentro de cada tarea y
  se toma el prefijo correspondiente a cada fracción.

### 1.3 Qué se mide
Solo sobre **val completo** (6,808 humanos + 225 IA), **nunca sobre test**: la curva sirve para tomar
una decisión (cuántos datos generar), y las decisiones no se toman con test.

| Métrica | Papel |
|---|---|
| **PR-AUC (val)** | **Principal.** Es la adecuada para clases desbalanceadas. |
| ROC-AUC (val) | Secundaria |
| F1, precisión y recall con el umbral `fpr_0.01` ajustado en val | Secundaria; se aclara que el umbral se ajusta en el mismo conjunto |
| Época seleccionada | Diagnóstico |

### 1.4 Criterio de saturación (escrito antes de ejecutar)
La curva se considera **saturada** si se cumplen ambas condiciones:
1. la mejora media de PR-AUC entre el 50 % y el 100 % es **menor que 0.01**; y
2. esa mejora es **menor que la desviación estándar entre semillas** en el punto del 100 %.

Si no se cumple, se reporta como **"aún no saturada"**, y se escribe que más datos podrían haber
ayudado. También es un resultado válido.

### 1.5 Extrapolación (opcional, con cautela)
- Se ajusta la ley de potencias `y(n) = a − b · n^(−c)` a la PR-AUC media, con `scipy.optimize.curve_fit`.
- Se reporta el valor **extrapolado** en 10,000 y 20,000 códigos de IA, con su intervalo, calculado
  ajustando la curva en cada remuestreo bootstrap de las semillas.
- Se marca siempre como **estimación**: extrapolar ~20 veces fuera del rango observado es incierto.

---

## 2. Implementación

### 2.1 Cambios
| Archivo | Cambio |
|---|---|
| `models/char_cnn/v2/subsample.py` (nuevo) | Función `subsample_ai_train(entries, fraction, seed)`: por `dup_group`, estratificada por tarea y anidada |
| `models/char_cnn/v2/train.py` | Dos argumentos nuevos: `--train-ai-fraction` (por defecto 1.0) y `--subsample-seed`. Se aplican después de cargar el manifest y solo sobre train/IA. Se registran en `config.json`, junto con el número de muestras resultantes |
| `scripts/learning_curve_charcnn.py` (nuevo) | Ejecuta la cuadrícula fracción × semilla, salta las corridas ya terminadas (para reanudar), junta los resultados y genera las gráficas |
| `tests/test_charcnn_subsample.py` (nuevo) | Pruebas (2.2) |

- Las corridas se escriben en `runs/char_cnn_lc/<timestamp>/f<fracción>_s<semilla>/`, nunca en
  `runs/char_cnn/` ni en `models/deploy/`.
- Para ahorrar tiempo y espacio, cada corrida guarda solo `config.json`, `metrics_val.json` e
  `history.csv`; no se guarda el checkpoint, salvo con `--keep-checkpoints`.

### 2.2 Pruebas primero (RED → GREEN)
- **Fracción 1.0:** devuelve exactamente las mismas entradas que hoy (la corrida real no cambia).
- **Por grupo:** ningún `dup_group` queda partido.
- **Anidado:** con la misma semilla, subconjunto(0.2) ⊂ subconjunto(0.3).
- **Estratificado:** cada tarea conserva al menos un grupo si tenía alguno (o se documenta la regla de redondeo).
- **Solo IA de train:** humanos, val y test quedan intactos.
- **Determinista:** misma semilla y misma fracción producen el mismo resultado.

### 2.3 CLI
```bash
python scripts/learning_curve_charcnn.py \
    --fractions 0.05,0.10,0.15,0.20,0.30,0.40,0.50,0.60,0.70,0.80,0.90,1.00 \
    --seeds 42,7,123,2024,31337 \
    --out runs/char_cnn_lc
```
- `--smoke`: 2 fracciones × 1 semilla con 2 épocas, para comprobar que todo funciona.
- `--resume <dir>`: continúa una corrida interrumpida.

---

## 3. Gráficas

Se guardan en `Documentacion/Documento/figuras/` a 300 dpi.

### C1. Curva de aprendizaje (figura principal)
- **Eje X:** número de códigos de IA en entrenamiento, en **escala logarítmica**. Así los puntos se
  reparten bien y la saturación se ve con claridad.
- **Eje Y:** PR-AUC en validación.
- La línea es la media de las 5 semillas; la **banda sombreada**, el intervalo (mínimo–máximo o ±1
  desviación estándar, indicando cuál); y se dibujan también los puntos de cada semilla, semitransparentes.
- Una **línea vertical** en 897 con la etiqueta "Tamaño final utilizado".
- Opcional: la extrapolación como **línea punteada** hasta 20,000, con su banda, y la etiqueta
  "Extrapolación (estimación)".

### C2. Panel de métricas
- Una cuadrícula de 2×2: PR-AUC, ROC-AUC, F1 y recall en función del número de códigos de IA, con el
  mismo formato que C1.

### C3. Mejora marginal (opcional)
- Barras con la ganancia media de PR-AUC de cada fracción respecto a la anterior. Debajo de cierto
  punto, la ganancia cae dentro del ruido entre semillas: eso se ve directamente.

---

## 4. Ejecución

```powershell
python -m pytest tests/test_charcnn_subsample.py -q
python scripts/learning_curve_charcnn.py --smoke --out runs/char_cnn_lc_smoke
Start-Process python -ArgumentList "-u","scripts/learning_curve_charcnn.py","--out","runs/char_cnn_lc" -RedirectStandardOutput lc.log -NoNewWindow
```

- Tiempo estimado: 60 corridas × ~5 min ≈ **5 horas** en la RTX 2060 SUPER. Conviene dejarlo corriendo de noche.
- Si se interrumpe: `--resume runs/char_cnn_lc/<timestamp>`.

---

## 5. Reporte

`runs/char_cnn_lc/<timestamp>/report.md` con:
- la tabla de fracción, número de códigos de IA, PR-AUC, ROC-AUC y F1 (media ± desviación) y la época media;
- el veredicto del criterio de saturación (1.4) tal como se pre-registró;
- la extrapolación, si se hizo, marcada como estimación;
- las limitaciones:
  - la curva se mide en **val**, que también se usa para elegir la época, por lo que es algo optimista; el sesgo es igual para todos los puntos y no afecta la forma de la curva;
  - más datos **del mismo generador** no corrigen los atajos del dataset; la generalización a otros LLMs es otra pregunta.

---

## 6. En la tesis

**Dónde:** capítulo de Ingeniería de datos, sección Adquisición, una subsección "Justificación del
tamaño de la clase sintética".

**Ejemplo de redacción (ajustar a los resultados reales):**
> "La planeación contemplaba 20,000 códigos (50 % IA). Para decidir si era necesario alcanzar esa cifra,
> se midió la curva de aprendizaje de CharCNN variando el número de códigos de IA de entrenamiento entre
> 45 y 897 (5 semillas por punto). La PR-AUC en validación se estabiliza a partir de ~N códigos (mejora
> < 0.01 entre el 50 % y el 100 %), por lo que generar más código del mismo tipo no se justificaba. La
> limitación principal del canal no es la cantidad de datos sino su diversidad (generadores y cursos)."

Además, **corregir las cifras** que hoy dicen 20,000 / 14,000 / 3,000 en `ingenieria_de_datos.tex:30`
y `modelado.tex:4, 89, 295`, usando la tabla de la sección 0.

---

## 7. Lista de verificación
- [ ] Pruebas de `subsample.py` (RED → GREEN)
- [ ] `--train-ai-fraction` y `--subsample-seed` en `train.py`; con fracción 1.0, el resultado es igual al actual
- [ ] Corrida `--smoke`
- [ ] Corrida completa (60)
- [ ] Gráficas C1 y C2 (C3 opcional)
- [ ] `report.md` con el veredicto de saturación
- [ ] Subsección en `ingenieria_de_datos.tex` y corrección de cifras
