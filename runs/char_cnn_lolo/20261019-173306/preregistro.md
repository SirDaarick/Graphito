# Preregistro

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
