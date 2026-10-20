# Experimento leave-one-LLM-out para CharCNN v2

## Diseño preregistrado

**Pregunta.** ¿CharCNN generaliza a un generador de IA que nunca vio, o aprende un estilo propio de cada generador?

**Condiciones.** Los humanos son siempre el split completo. El código de IA de los demás generadores
(con a lo sumo 2 archivos cada uno) se excluye del entrenamiento, de la selección en val y de las
métricas principales.

- **R. Referencia** (sin entrenar): puntajes de test del modelo desplegado (`20261011-015734`), desglosados por
  generador: humanos de test contra IA de deepseek y contra IA de qwen3.
- **D.** Entrenamiento y val con IA solo de deepseek. El generador retenido no influye en la parada temprana ni en la
  calibración. Se evalúa en test contra deepseek (visto) y qwen3 (no visto).
- **Q.** Simétrica a D: entrenamiento y val solo con qwen3.
- **D-matched.** Como D, pero la IA de deepseek en train se submuestrea por `dup_group`, estratificada por
  `assignment`, hasta el MISMO número de grupos únicos que qwen3 tiene en train. Separa "generador no visto"
  de "menos datos".
- **Semillas.** 3 por condición entrenada (42, 7, 123): 9 entrenamientos.

**Métricas** (test, solo representantes de `dup_group`). Para cada subconjunto de IA (visto / no visto) contra
TODOS los humanos de test: ROC-AUC, PR-AUC y recall en el umbral `fpr_0.01` ajustado en val por la propia corrida;
además el FPR humano en ese umbral. Se reporta media ± desviación estándar (ddof=1) entre semillas. El PR-AUC
depende de la prevalencia de cada subconjunto, por lo que no es comparable entre generadores de distinto tamaño.

**Contraste primario.** Por condición, (visto - no visto) en recall y en ROC-AUC, sobre las medias entre semillas.

**Interpretación preregistrada.**

- *Generaliza*: en D-matched Y en Q, la caída de ROC-AUC es < 0.02 Y la caída de recall es < 0.10.
- *Dependiente del generador*: la condición D-matched y la Q superan cada una al menos una de esas cotas.
- *Mixto*: cualquier otro caso (una sola de las dos condiciones supera alguna cota).

(Operacionalización de la regla "alguna caída supera la cota": se exige que ocurra en ambas condiciones para
"dependiente"; si ocurre solo en una, es "mixto".)

**Limitaciones declaradas.** Solo hay dos generadores sustanciales; deepseek y qwen3 se solicitaron con prompts
idénticos, de modo que el estilo del prompt queda constante; el experimento mide transferencia solo entre estos dos
generadores; los humanos de test provienen del mismo curso que los de entrenamiento; no se calculó IC bootstrap.

## Resultados

### R. Referencia (modelo desplegado, entrenado con todos los generadores)

| Generador | n IA | ROC-AUC | PR-AUC | Recall@fpr_0.01 | FPR humano |
|---|---|---|---|---|---|
| deepseek-chat | 227 | 0.992 | 0.941 | 0.881 | 0.0095 |
| qwen3 | 100 | 0.997 | 0.930 | 0.900 | 0.0095 |

Umbral `fpr_0.01` del modelo desplegado: 0.1715. Un solo modelo, sin semillas.

### Condiciones entrenadas (media ± desviación estándar entre semillas)

| Condición | Subconjunto | Generador | ROC-AUC | PR-AUC | Recall@fpr_0.01 | FPR humano |
|---|---|---|---|---|---|---|
| D: entrenado con deepseek | visto | deepseek-chat | 0.988 ± 0.003 | 0.925 ± 0.012 | 0.869 ± 0.007 | 0.009 ± 0.002 |
| D: entrenado con deepseek | no visto | qwen3 | 0.993 ± 0.002 | 0.862 ± 0.025 | 0.847 ± 0.015 | 0.009 ± 0.002 |
| D-matched: deepseek (mismo tamaño que qwen3) | visto | deepseek-chat | 0.987 ± 0.003 | 0.913 ± 0.009 | 0.830 ± 0.018 | 0.009 ± 0.002 |
| D-matched: deepseek (mismo tamaño que qwen3) | no visto | qwen3 | 0.988 ± 0.004 | 0.807 ± 0.007 | 0.753 ± 0.015 | 0.009 ± 0.002 |
| Q: entrenado con qwen3 | visto | qwen3 | 0.998 ± 0.001 | 0.938 ± 0.008 | 0.940 ± 0.017 | 0.010 ± 0.001 |
| Q: entrenado con qwen3 | no visto | deepseek-chat | 0.985 ± 0.001 | 0.874 ± 0.006 | 0.790 ± 0.014 | 0.010 ± 0.001 |

### Contraste primario (visto − no visto, medias entre semillas)

| Condición | Caída ROC-AUC | Caída recall | Semillas |
|---|---|---|---|
| D: entrenado con deepseek | -0.005 | 0.023 | 3 |
| D-matched: deepseek (mismo tamaño que qwen3) | -0.002 | 0.076 | 3 |
| Q: entrenado con qwen3 | 0.013 | 0.150 | 3 |

### Datos de entrenamiento por condición (primera semilla)

- D: entrenado con deepseek: train después = `{"files_by_model": {"deepseek-chat": 632}, "groups_by_model": {"deepseek-chat": 632}, "n_human": 10688}`; val después = `{"files_by_model": {"deepseek-chat": 144}, "groups_by_model": {"deepseek-chat": 144}, "n_human": 2868}`
- D-matched: deepseek (mismo tamaño que qwen3): train después = `{"files_by_model": {"deepseek-chat": 240}, "groups_by_model": {"deepseek-chat": 240}, "n_human": 10688}`; val después = `{"files_by_model": {"deepseek-chat": 144}, "groups_by_model": {"deepseek-chat": 144}, "n_human": 2868}`
- Q: entrenado con qwen3: train después = `{"files_by_model": {"qwen3": 240}, "groups_by_model": {"qwen3": 240}, "n_human": 10688}`; val después = `{"files_by_model": {"qwen3": 63}, "groups_by_model": {"qwen3": 63}, "n_human": 2868}`

## Veredicto preregistrado

**mixto**

- D-matched: deepseek (mismo tamaño que qwen3): caída ROC-AUC -0.002 (cota 0.02), caída recall 0.076 (cota 0.1); supera cotas: no
- Q: entrenado con qwen3: caída ROC-AUC 0.013 (cota 0.02), caída recall 0.150 (cota 0.1); supera cotas: sí

## Limitaciones

- Solo dos generadores sustanciales (deepseek y qwen3); los demás tienen a lo sumo 2 archivos por split.
- deepseek y qwen3 recibieron prompts idénticos: el estilo del prompt queda constante, por lo que no se evalúa sensibilidad al prompt.
- Solo mide transferencia entre estos dos generadores; no permite concluir sobre otros LLM.
- Los humanos de test son del mismo curso que los de entrenamiento.
- Con 100 archivos de qwen3 en test, cada archivo equivale a 0.01 de recall, y la desviación estándar entre 3 semillas es una estimación pobre de la varianza.
- No se calculó IC bootstrap.
