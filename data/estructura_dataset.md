# Estructura del Dataset

El dataset se encuentra en la carpeta `data/raw/IEEE_plagiarism/`. Este conjunto de datos proviene de un cursos de programsción en C/C++ y contiene código fuente de estudiantes, rastros de uso del IDE y ground truth de plagio.

## Directorio General

```
IEEE_plagiarism/
├── readme.txt              # Documentación original del dataset
├── ground-truth-anon.txt  # Ground truth completo (plagio estático + dinámico)
├── ground-truth-static-anon.txt  # Ground truth basado en similitud de código
├── ground-truth-dynamic-anon.txt # Ground truth basado en defensa oral
├── src/                   # Códigos fuente de los estudiantes
│   ├── A2016/
│   ├── A2017/
│   ├── B2016/
│   └── B2017/
└── stats/                # Rastros de uso del IDE
    ├── A2016/
    ├── A2017/
    ├── B2016/
    └── B2017/
```

## 1. Códigos Fuente (`src/`)

Contiene los programas resubmits de los estudiantes organizados por curso y asignación.

### Estructura

```
src/{curso}/{asignignación}/
```

- **Cursos**: A2016, A2017, B2016, B2017
- **Asignaciones**: Z1, Z2, Z3, ..., T1, T2, ... (16-22 por curso)
- **Archivos**: Archivos C o C++ nombrados como `student{id}` (anonimizado)

### Ejemplo de ruta

```
src/A2016/Z1/main.c  →  Código del estudiante 2956 para la asignación Z1 del curso A2016
```

## 2. Rastros del IDE (`stats/`)

Contiene archivos JSON con el registro de actividad del estudiante en el IDE.

### Estructura del archivo JSON

Cada archivo `{student_id}.json` contiene un objeto donde las claves son rutas dentro de las carpetas del curso.

```json
{
  "A2016": {
    "total_time": 220597,
    "builds": 0,
    "builds_succeeded": 0,
    "testings": 0,
    "last_test_results": "",
    "events": [...],
    "last_revision": 1,
    "entries": ["A2016/Z1", "A2016/T1", ...]
  },
  "A2016/Z1": {
    "total_time": 3078,
    "builds": 12,
    "builds_succeeded": 25,
    "testings": 7,
    "last_test_results": "10/10",
    "events": [...],
    "last_revision": 5622,
    "entries": ["main.c", "test.c"]
  }
}
```

### Campos principales

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `total_time` | int | Tiempo estimado trabajando en la carpeta (segundos) |
| `builds` | int | Número de intentos de compilación |
| `builds_succeeded` | int | Número de compilaciones exitosas |
| `testings` | int | Número de ejecuciones de tests |
| `last_test_results` | string | Formato "X/Y" (tests exitosa/total) |
| `events` | array | Array de eventos de cambio |
| `entries` | array | Lista de archivos/carpetas en el directorio |

### Eventos (`events`)

Cada evento tiene la siguiente estructura:

```json
{
  "time": 1486134666,
  "text": "created|deleted|rename|created_folder|compiled|compiled_successfully|modified",
  "filename": "main.c",
  "old_filename": "old.c",
  "old_filepath": "/path/to/old.c",
  "content": "...",       // Para created/rename
  "output": "...",        // Para compiled (output del compilador)
  "diff": [...]          // Para modified (cambios línea por línea)
}
```

### Tipos de eventos

- `created`: Archivo creado
- `deleted`: Archivo eliminado
- `rename`: Archivo renombrado
- `created_folder`: Carpeta creada
- `compiled`: Compilación attempted
- `compiled_successfully`: Compilación exitosa
- `modified`: Modificación de líneas

## 3. Ground Truth (`ground-truth-*.txt`)

Lista de estudiantes considerados culpables de plagio.

### Formato del archivo

```
- {curso}/{asignignación}/{tarea}
student{id1}
student{id2},student{id3},student{id4}
student{id5}
```

- Cada asignación tiene líneas con estudiantes o grupos de estudiantes separados por coma
- Los grupos indican que esos estudiantes se plagiaron mutuamente

### Archivos

| Archivo | Descripción |
|---------|-------------|
| `ground-truth-anon.txt` | Plagio completo (estáico + dinámico) |
| `ground-truth-static-anon.txt` | Solo similitud de código |
| `ground-truth-dynamic-anon.txt` | Solo falla en defensa oral |

### Ejemplo

```
- A2016/Z1/Z1
student2956
student7386,student5378,student9538
student6018
```

- student2956 plagió solo
- student7386, student5378, student9538 se plagiarón mutuamente
- student6018 plagió solo

## 4. Metadatos del Dataset

- **Cursos**: 4 cursos académicos (A2016, A2017, B2016, B2017)
- **Lenguaje**: C/C++
- **Anonimización**: Nombres de estudiantes reemplazados por `student{id}`
- **Formato de trazzo**: JSON
- **Total de estudiantes**: ~100-150 por curso
- **Asignaciones por curso**: 16-22