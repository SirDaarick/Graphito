# Notas de integración de CorreccionesTTI.docx

Ningún cambio se descartó por completo. Abajo: qué se adaptó, qué queda pendiente de tu decisión y las inconsistencias previas del documento que las correcciones dejaron al descubierto. LaTeX no se pudo compilar aquí (no hay `pdflatex`); solo se verificó balance de llaves y entornos.

## Adaptaciones hechas (no es copia literal)

| Corrección | Archivo | Adaptación y motivo |
|---|---|---|
| 3.1 Texto bajo Figura 4.1 | `propuesta_de_solucion.tex` | Se usa `\ref` a la figura en lugar de "Figura 4.1" fija. |
| 4.1.2 Normalización | `propuesta_de_solucion.tex` | El texto original decía que el canal estilométrico conserva "indentación, saltos de línea, comentarios". La implementación (Cap. 7, Sec. de normalización simétrica) elimina comentarios y normaliza espacios. Se reescribió ese párrafo para no contradecirla y se refiere a esa sección. |
| Representación de caracteres CharCNN | `propuesta_de_solucion.tex` | No existía el párrafo a reemplazar (4.1.4.2 no explica one-hot ni filtros). Se agregó como subsubsección nueva "Codificación de entrada y capacidad computacional". "Deberán documentarse" se cambió por referencia al Cap. 8 (hiperparámetros). |
| Fusión / 769 dim / zero-padding / desbalance entre canales | `propuesta_de_solucion.tex`, `diseño.tex` | Se agregó una frase que enlaza con el Cap. 8: la fusión con pesos manuales (ROC-AUC 0.874) fue peor que el Canal B solo y el sistema final usa dos canales separados. Se quitó solo la frase del zero-padding de la viñeta original (ahora se discute en la subsubsección nueva). El resto del texto es tal cual. |
| 5.8.x Métricas operativas | `analisis.tex` | Se añadieron además dos filas a la tabla resumen de métricas. |
| A1 y RN | `analisis.tex` | "RN-XX" quedó como RN-07 y A1 la referencia. El texto del límite posterior a la lista se movió debajo de las reglas. |
| Actores 5.2 | `analisis.tex` | Se añadió una frase final aclarando que el LLM es servicio externo, no usuario. |
| Ventaja de Graphito | `generalidades.tex` | Se agregó referencia a la sección de validación con docentes (`subsec:validacion_docentes`). |
| Cierre de conclusiones | `conclusiones.tex` | El último párrafo ("Durante TT II se deberá profundizar...") ya no aplica: la tesis tiene resultados. Se reformuló como trabajo futuro. "El resultado esperado" pasó a "El resultado". |
| Costos | `diseño.tex` | "6.5.1 Viabilidad" duplicaba numeración; quedó como última subsección de la nueva sección. Las "Tabla 6.X" son `\ref` a etiquetas reales. |

## Pendientes tuyos

1. **Costos (Sec. "Estimación de costos del proyecto", `diseño.tex`)**: todas las celdas `[Completar]` y los importes de la frase final. No se incluyó el texto "Importante para llenar las tablas" porque es una indicación para ti, no contenido de tesis: no pongas $100/hora por defecto; si no hubo pago registra horas y valoración $0 o N/A, o usa una tarifa con fuente verificable.
2. **Figura BPMN (`ModeloBPMN.png`)**: el texto nuevo dice que la compuerta distingue variantes aceptadas / en revisión / descartadas. Verifica que el diagrama lo muestre, o ajusta la figura.
3. **RN-07 (límite de 5 variantes)**: el backend actual no implementa generación de variantes por LLM (no hay referencias a "variant" en `backend/app`). Si el docente pregunta, es un requisito de diseño, no una funcionalidad entregada.
4. **Ubicación del A1 / viabilidad**: si prefieres "Viabilidad económica" como sección aparte, es mover la última `\subsection`.

## Inconsistencias previas del documento (no introducidas por estos cambios)

- `analisis.tex`: el corpus se describe 50 % humano / 50 % IA con N = 20,000; `conclusiones.tex` y Cap. 7 hablan de 42,389 muestras (40,936 humanas, 1,453 sintéticas). El texto nuevo de desbalance quedó consistente con ambos, pero la tabla de Cap. 5 está desactualizada.
- `conclusiones.tex` reporta exactitud 92.4 % / F1 92.4 %; `modelado.tex` reporta CharCNN v2 con F1 0.884. Parecen cifras del protocolo anterior con fuga.
- `propuesta_de_solucion.tex` (Canal B, "Preservación de código raw" con comentarios) contradice la normalización simétrica del Cap. 7.
- `diseño.tex` Fase IV de Komorebi menciona el vector de 769 dimensiones y LoRA; `modelado.tex` indica que el sistema final no usa fusión ni adaptador.
