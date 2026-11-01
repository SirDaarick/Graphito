# Problema de ejemplo para la prueba con docentes

Generado con `python scripts/build_demo_problem.py` (tarea `A2017_Z4_Z1`, semilla 11) a partir del
conjunto de prueba del `golden_set` (código de estudiantes de la Universidad de Sarajevo y código
generado por IA). Es reproducible: la misma semilla produce los mismos archivos.

## Qué se da a los docentes

- `referencia.c`
- `entregas/entrega_01.c` a `entrega_13.c`

**No** se entrega `clave_privada.csv`: dice qué es cada archivo.

## Composición (13 entregas)

| Clase | n | Qué es |
|---|---|---|
| `original` | 5 | Estudiantes que resolvieron la tarea por su cuenta |
| `copy` | 3 | Estudiantes de un grupo de copia confirmado **entre ellos**, no de la referencia |
| `ai` | 3 | Código generado por modelos de IA |
| `derivada_*` | 2 | La propia referencia con identificadores renombrados (una además sin comentarios) |

Los archivos se eligieron al azar con la semilla fija, no por su resultado.

## Resultado de Graphito sobre este conjunto (modo real, probado el 31/10/2026)

| Clase | Etiqueta recibida |
|---|---|
| `derivada_*` (2) | Similitud alta con la referencia: 2 de 2 |
| `ai` (3) | Estilo atípico: 3 de 3 |
| `original` (5) | Sin alertas: 4 de 5; una falsa alerta de estilo (probabilidad 0.32 frente al umbral 0.1715) |
| `copy` (3) | Sin alertas: 3 de 3 |

Las copias entre estudiantes no se detectan porque Graphito compara cada entrega con la
**referencia**, no entre entregas. Es una limitación del diseño actual y conviene declararla.

## Respuesta esperada a la tarea ("¿qué 3 revisar primero?")

Las dos derivadas y, después, las de IA. Una respuesta distinta no es un error: la tarea mide
cómo se usa el reporte, no si se acierta.
