# Figuras y tablas del experimento con CodeNet para la tesis

Todas las cifras salen de los artefactos de `runs/contrastivo_codenet/` (copia de los resultados de las fases F0–F4) y
de `runs/contrastivo_codenet/derived/` (datos calculados una vez a partir de los datos crudos). Las figuras se
escriben en `Documentacion/Documento/figuras/` y las tablas en `Documentacion/Documento/tablas/`. El diseño y las
decisiones de cada fase están en `odd/tasks/contrastivo-codenet-f0.md` … `f4.md`.

## Cómo regenerarlas

```bash
python scripts/generate_codenet_figures.py                        # las 18 figuras y las 6 tablas
python scripts/generate_codenet_figures.py --only resultado_e2    # una sola
python scripts/derive_codenet_figure_data.py                      # solo si cambian los datos crudos o el adaptador (GPU)
```

Las tablas son entornos `table[H]` completos para usar con `\input{tablas/tabla_xxx.tex}`. **No se pudieron compilar
aquí** (no hay LaTeX en esta máquina): conviene compilar la tesis y revisar que no haya errores ni desbordes.

## Datos de CodeNet

| Archivo | Qué muestra | Dónde encaja | Pie sugerido |
|---|---|---|---|
| `codenet_particiones.png` + `tabla_codenet_particiones.tex` | Programas Accepted y Wrong Answer por partición (790 / 99 / 99 problemas) | Ingeniería de datos | «Programas de CodeNet (C++) conservados por partición; la división es por problema, nunca por envío.» |
| `codenet_exclusiones.png` | Programas descartados por motivo; casi todos por no caber en una ventana de 512 tokens | Ingeniería de datos | «Motivos de exclusión de los programas de CodeNet. Escala logarítmica.» |
| `codenet_longitud_comparada.png` | Líneas por programa: CodeNet conservado (mediana 26) frente a ESCOM (mediana 104) | Ingeniería de datos y limitaciones | «Los programas de CodeNet usados son unas cuatro veces más cortos que los de ESCOM.» |
| `codenet_esquema_triplete.png` | Esquema de la tripleta: ancla, positivo, negativo difícil y negativos del lote | Modelado | «Tripleta de entrenamiento contrastivo.» (esquema, sin datos) |
| `coseno_zero_shot.png` y `coseno_entrenado.png` | Distribución del coseno entre programas del mismo problema y de problemas distintos, antes y después | Modelado y resultados | «Similitud coseno en la validación de CodeNet. Misma escala en ambas figuras.» Usarlas lado a lado. |
| `proyeccion_zero_shot.png` y `proyeccion_entrenado.png` | t-SNE de seis problemas de validación, con Accepted y Wrong Answer | Modelado | «Proyección t-SNE de seis problemas de validación.» Los ejes no tienen significado. |

## Entrenamiento y ablación

| Archivo | Qué muestra | Pie sugerido |
|---|---|---|
| `entrenamiento_perdida.png` | Pérdida InfoNCE de las cuatro corridas | «La pérdida de A es menor porque compite contra menos candidatos; no es comparable con la de B.» |
| `entrenamiento_val_auc.png` | AUC correcta vs. incorrecta dentro del problema en la validación de CodeNet | «Criterio con el que se eligió la configuración B.» |
| `entrenamiento_val_map.png` | MAP@R entre problemas en la validación de CodeNet | «Separación entre problemas; A supera a B, pero no es el objetivo del sistema.» |
| `ablacion_val_auc.png` y `ablacion_e2.png` + `tabla_ablacion.tex` | Efecto de usar Wrong Answer como negativos: mejora en CodeNet, intervalos traslapados en ESCOM | «B gana en CodeNet; en ESCOM las diferencias están dentro del ruido.» |
| `tabla_hiperparametros.tex` | Configuración del ajuste | «Configuración del ajuste contrastivo de GraphCodeBERT.» |

## Resultados en ESCOM

| Archivo | Qué muestra | Pie sugerido |
|---|---|---|
| `resultado_e1.png` | MAP@R del agrupamiento por tarea (E1) con IC95 % | «Ningún método neuronal supera a Jaccard en E1.» |
| `resultado_e2.png` | AUC macro de E2 con IC95 % | «Los intervalos incluyen al zero-shot y a Jaccard.» |
| `resultado_e2_por_tarea.png` | AUC de cada una de las 14 tareas de E2 | «Resultados por tarea: el comportamiento es heterogéneo.» |
| `resultado_robustez_auc.png` | AUC por transformación (T0–T7) | «Jaccard se mantiene casi constante; el modelo sin entrenar cae con T5 y T7.» |
| `resultado_robustez_did.png` | Diferencia de degradación del ajustado frente al no entrenado, con IC95 % | «El ajustado se degrada menos con código muerto y con la combinación total.» |
| `tabla_resultados_e1_e2.tex`, `tabla_robustez_auc.tex`, `tabla_veredictos.tex` | Cifras exactas y veredictos de H1–H3 | — |

## Advertencias para escribir el texto

1. **Dominio distinto.** CodeNet conservado es mucho más corto que ESCOM (figura de longitudes); el filtro de una sola
   ventana lo provoca. Es una limitación del experimento y conviene decirlo.
2. **La mejora del coseno es de CodeNet.** Las distribuciones de coseno (0.96 → 0.27 entre problemas distintos) se
   midieron en la validación de CodeNet. No se midieron en ESCOM.
3. **MAP@R y E1 miden separar problemas**, no la tarea del docente, que compara dentro de un problema. El AUC dentro del
   problema es la medida alineada con el uso; en ESCOM la tarea equivalente es E2.
4. **E2 tiene 14 tareas**: los intervalos son anchos, H1 es *no concluyente* y no se debe escribir como mejora. Las
   referencias de E2 son entregas aprobadas de alumnos, no soluciones del docente.
5. **Jaccard sigue siendo mejor** que cualquier método neuronal en robustez, E1 y E2 en este corpus.
6. **Una desviación declarada:** los contrastes de robustez se calcularon con una versión exacta y más rápida del
   bootstrap (idéntica bit a bit a la original en datos reales); está en `odd/tasks/contrastivo-codenet-f4.md`.
