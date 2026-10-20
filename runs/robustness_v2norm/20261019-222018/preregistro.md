# Preregistro: robustez de v2 con renombrado canónico (`v2_norm`)

Redactado y confirmado en git antes de calcular cualquier puntaje de `v2_norm`.

## Pregunta

¿El renombrado canónico de identificadores elimina la vulnerabilidad de v2 al renombrado (T1) y qué cuesta bajo otras transformaciones?

## Diseño

- **Datos:** partición `test` de `split_v1` (sha256 del JSON descomprimido `e835362d2e7a4153ef97204d4b30e769759a0f8f54f7db67b9e1fb2639e5238f`), mismos pares que la corrida `runs/robustness/20261012-050941`.
- **Métodos:** `v2`, `v2_norm`, `jaccard` (referencia).
- **Condiciones:** T0, T1, T5, T7@1.0. Misma implementación de transformaciones (`models/robustness/transforms.py`), semilla base 42 y derivación de semilla por archivo idéntica a la corrida previa.
- **v2_norm:** se aplica la transformación primero; luego `canonicalize_code` (`models/logic_eval/canonical.py`) a AMBOS lados del par (original y transformado); luego se incrusta con el mismo embebedor v2 (pooling mean) y se mide coseno.
- **Métrica:** ROC-AUC, vista `all`, IC95% por bootstrap percentil estratificado por asignación (`paired_bootstrap`), n_boot = 1000 en todos los contrastes y condiciones (si el tiempo lo impide se declara).
- **Verificación de reproducción (compuerta):** ROC-AUC de v2 y jaccard en T0 y T1 debe coincidir con la corrida previa (v2 0,856 / 0,683; jaccard 0,945 / 0,945) con tolerancia ±0,002. Si no se reproduce, se detiene el experimento y se informa.

## Contraste primario

Δ = [AUC_v2_norm(T1) − AUC_v2_norm(T0)] − [AUC_v2(T1) − AUC_v2(T0)], con IC95% por bootstrap pareado. Mide cuánto de la caída de v2 por renombrado elimina v2_norm. Si v2_norm fuera invariante al renombrado, Δ ≈ −(caída de v2) ≈ +0,17.

## Hipótesis

- **H1:** la caída propia de v2_norm en T1, d = AUC_v2_norm(T1) − AUC_v2_norm(T0), cumple |d| < 0,01, porque el renombrado consistente es un no-op tras la canonicalización. (Aclaración de operacionalización: el enunciado original escribe "|Δ| < 0,01" para la caída de v2_norm; el contraste primario Δ definido arriba es otra cantidad y se informa por separado. H1 se evalúa sobre d, con su IC95%.)
- **H2:** |AUC_v2_norm(T0) − AUC_v2(T0)| < 0,02 (sin costo relevante en código sin transformar).
- **H3 (exploratoria):** diferencia de nivel AUC_v2_norm − AUC_v2 en T5 y T7@1.0, sin expectativa previa.

## Verificación de sanidad

Sobre 200 segundos archivos de pares positivos muestreados con semilla 42 se informa la fracción con canonicalize(T1(b)) == canonicalize(b) byte a byte, y se explican las discrepancias.

## Alcance y limitaciones declaradas de antemano

- No se recalcula la TPR a umbral desplegado para v2_norm: no existe umbral calibrado de v2_norm.
- Solo T0, T1, T5, T7@1.0.
- La caché de embeddings de la corrida previa se reutiliza (clave por sha256 del contenido); el texto canonicalizado es un contenido nuevo y se incrusta con el mismo embebedor.


## ADDENDUM (antes de calcular cualquier puntaje; el texto anterior no se modifica)

- **T1 de la corrida previa:** la implementación iteraba un conjunto de cadenas (`names_in_func - shadowed`), por lo que su salida dependía de PYTHONHASHSEED. Los textos T1 de `runs/robustness/20261012-050941` son una realización no reproducible (1/100 archivos coinciden por sha256; T0, T5 y T7@1.0 coinciden 100/100).
- **Corrección:** T1 ahora es determinista (`sorted(...)`), commit `fix(robustness): make T1 identifier renaming deterministic`. T0, T5 y T7@1.0 no cambian (sha256 idénticos a la corrida previa en la muestra de 100 archivos).
- **Consecuencia:** v2 y jaccard en T1 se vuelven a medir en esta corrida; el valor previo de v2 en T1 (0,683) se informa como referencia histórica, no como objetivo de reproducción.
- **Compuerta de reproducción (revisada):** aplica a T0 (v2 0,856; jaccard 0,945; tolerancia ±0,002) y a T5 y T7@1.0 de v2 y jaccard, cuyos textos transformados son idénticos a los previos. Si T0 no reproduce, se detiene el experimento.
- **H1 (reafirmada tal como se operacionalizó):** la caída propia de v2_norm en T1, d = AUC_v2_norm(T1) − AUC_v2_norm(T0), cumple |d| < 0,01, evaluada sobre d con su IC95%. El contraste primario Δ = [AUC_v2_norm(T1) − AUC_v2_norm(T0)] − [AUC_v2(T1) − AUC_v2(T0)] se informa por separado. H2 y H3 sin cambios.
