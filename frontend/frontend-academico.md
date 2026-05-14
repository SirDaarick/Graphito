# Documentación del Frontend — Graphito

## 1. Introducción

El frontend de **Graphito** constituye la capa de presentación de un sistema de detección de similitud de código fuente, orientado al ámbito académico-investigativo. Su propósito es proveer una interfaz web interactiva que permita a investigadores y docentes del Instituto Politécnico Nacional (ESCOM-IPN) gestionar códigos de referencia, ejecutar comparaciones de integridad bimodal y visualizar reportes forenses con análisis estilométrico, semántico e interpretación asistida por inteligencia artificial.

La aplicación se implementó como una **Single Page Application (SPA)** desarrollada con las siguientes tecnologías:

| Tecnología | Versión | Rol |
|------------|---------|-----|
| React | 19.2.4 | Biblioteca de componentes UI con renderizado declarativo |
| TypeScript | — | Tipado estático para seguridad en tiempo de compilación |
| Vite | 8.0.4 | Bundler y servidor de desarrollo con HMR |
| Tailwind CSS | 3.4.17 | Framework de estilos utilitarios con tema personalizado |
| GSAP | 3.12.5 | Animaciones de alto rendimiento para transiciones modales |
| Lucide React | 1.8.0 | Biblioteca de íconos SVG consistentes |
| clsx + tailwind-merge | 2.1.1 / 3.5.0 | Utilidad `cn()` para composición condicional de clases |

La arquitectura interna sigue una estructura plana con tres capas: **páginas** (`src/pages/`), **componentes reutilizables** (`src/components/layout/` y `src/components/ui/`), y una **utilidad de clases** (`src/lib/utils.js`). El enrutamiento entre vistas se maneja mediante estado local en `App.tsx` con tres modos: `login`, `register` y `app`.

---

## 2. Descripción del Diseño

El sistema de diseño de Graphito se fundamenta en una estética **oscura con acentos de vidrio esmerilado (_glassmorphism_)** y resplandores animados, buscando evocar precisión tecnológica y rigor analítico. La documentación completa del sistema de diseño se encuentra en [`design.md`](./design.md). A continuación se sintetizan sus principios rectores.

### 2.1 Paleta de Colores

El tema oscuro emplea una paleta de cuatro capas de profundidad visual:

- **Fondo principal**: `#0f172a` (Slate-900), sobre el cual flotan orbes animados de luz azul-violeta.
- **Superficies elevadas**: `#1e293b` para tarjetas, `#1a2031` con opacidad y desenfoque para tarjetas _glass_.
- **Acento primario**: Gradiente `#3b82f6 → #a78bfa` (azul → violeta) aplicado en botones CTA, texto del logo y anillos de progreso.
- **Semántica de riesgo**: Rojo (`#ef4444`) para similitud alta (>70%), ámbar (`#f59e0b`) para similitud media (30-70%) y azul (`#3b82f6`) para similitud baja (<30%).

### 2.2 Tipografía

Se definieron dos familias tipográficas complementarias:

- **'Plus Jakarta Sans'** (`font-display`): utilizada en títulos, encabezados y el logotipo, con pesos que van desde `bold` hasta `black` y tracking reducido (`tracking-tight`).
- **'Inter'** (`font-body`): empleada en cuerpo de texto, formularios y datos, con pesos `medium` y `semibold`.

La escala tipográfica abarca desde `text-[10px]` (labels en mayúsculas con tracking expandido) hasta `text-4xl` (36px, para el logo en la pantalla de autenticación). Los valores numéricos de porcentaje de similitud se muestran en fuente monoespaciada (`font-mono`) para facilitar la lectura de datos tabulares.

### 2.3 Filosofía Visual

El diseño persigue tres objetivos:
1. **Profundidad**: Mediante capas de fondo (orbes animados), superficies intermedias (tarjetas glass) y contenido interactivo en primer plano.
2. **Feedback**: Cada interacción del usuario recibe respuesta visual inmediata — escalado (`active:scale-95`), resplandor en hover, anillos de focus visibles y animaciones de entrada con _overshoot_.
3. **Jerarquía semántica**: Los colores de riesgo guían la interpretación de resultados sin necesidad de leer valores numéricos.

---

## 3. Descripción de Componentes

Los componentes se organizan en dos directorios: `layout/` para componentes estructurales y `ui/` para elementos atómicos reutilizables.

### 3.1 Header (`src/components/layout/Header.tsx`)

Barra de navegación superior fija que contiene:
- **Logotipo**: Imagen PNG + texto "Graphito" con relleno de gradiente azul-violeta mediante `bg-clip-text`.
- **Navegación**: Enlaces a Biblioteca (activo, con subrayado azul), Historial y Configuración.
- **Notificaciones**: Ícono de campana (`Bell` de Lucide) con indicador rojo de alerta no leída.
- **Perfil de usuario**: Avatar circular con inicial, nombre, rol institucional e indicador verde de conexión activa.
- **Botón CTA**: `GradientButton` para "Nuevo código" que dispara el modal de referencia.

### 3.2 AuthCard (`src/components/layout/AuthCard.tsx`)

Contenedor _glass_ reutilizado en autenticación y modales. Se construye con:
- Fondo semitransparente `#1a2031/65` con `backdrop-blur-xl` para el efecto de vidrio.
- Borde sutil `#2b3346/40`.
- Esquinas redondeadas de 40px (`rounded-[2.5rem]`).
- Sombra profunda `shadow-2xl` para separación visual del fondo animado.

### 3.3 ReferenceCard (`src/components/layout/ReferenceCard.tsx`)

Tarjeta de código de referencia que despliega:
- **Título y categoría**: Badge coloreado según tipo (Grafos = cian, Teoría = violeta, etc.).
- **Descripción**: Extracto del propósito del código de referencia.
- **Metadatos**: Fecha de actualización y número de comparaciones activas, con íconos de `Calendar` y `GitCompare`.
- **Acordeón de comparaciones**: Se expande/colapsa con transición `grid-rows-[0fr] → [1fr]` (300ms), mostrando análisis recientes con porcentaje de similitud coloreado semánticamente (rojo/ámbar/azul).
- **Botón "Comparar"**: `GradientButton` para iniciar un nuevo análisis contra esta referencia.

### 3.4 SearchBar (`src/components/layout/SearchBar.tsx`)

Barra de búsqueda con:
- Campo de texto con ícono `Search` posicionado a la izquierda, borde `graphito-border` y anillo de focus `graphito-blue/10`.
- Botones de "Filtrar" y "Ordenar" con íconos de `SlidersHorizontal` y `ArrowUpDown`, estilo outline con hover azul.

### 3.5 MouseGlowBackground (`src/components/layout/MouseGlowBackground.tsx`)

Fondo animado de alto impacto visual implementado con `requestAnimationFrame` a 60 fps:
- **Tres orbes de luz** de 800-1400px con `radial-gradient` y `blur-[80px]`.
- **Órbita continua**: Rotación a 0.025 rad/s con formación triangular (0°, 120°, 240°).
- **Interacción con cursor**: Los orbes son atraídos hacia la posición del mouse (intensidad 45%, radio de influencia 600px) mediante interpolación lineal (_lerp_).
- **Oscilación cromática**: El color de cada orbe interpola senoidalmente entre azul `rgb(59,130,246)` y violeta `rgb(167,139,250)` con fase y velocidad independientes.
- **Pulsación de escala**: Cada orbe respira con amplitud ±10% a frecuencia propia.

### 3.6 GradientButton (`src/components/ui/GradientButton.tsx`)

Botón de llamado a la acción (CTA) que constituye el elemento interactivo principal:
- **Gradiente de fondo**: `linear-gradient(to bottom, #3b82f6, #a78bfa)` con tamaño `100% 200%`; en hover se desplaza a `bg-bottom` (500ms ease-in-out).
- **Resplandor (glow)**: `box-shadow` azul por defecto que transiciona a violeta más intenso en hover.
- **Efecto shimmer**: Pseudo-elemento `::before` con gradiente blanco translúcido que recorre la superficie horizontalmente en 700ms durante hover.
- **Feedback táctil**: `active:scale-95`.
- **Accesibilidad**: `focus-visible:ring-2` con offset, `disabled:opacity-50`.

### 3.7 PaginationControls (`src/components/ui/PaginationControls.tsx`)

Control de paginación para la vista de biblioteca:
- Indicador textual del rango mostrado (ej. "Mostrando 1-10 de 25 referencias").
- Botones de navegación anterior/siguiente con estado `disabled` en extremos.
- Números de página con botón circular; la página activa recibe fondo azul, resplandor `shadow-[0_0_15px_rgba(59,130,246,0.4)]` y escala 110%.

---

## 4. Descripción de Pantallas

### 4.1 Login (`src/pages/Login.tsx`)

Pantalla de autenticación con dos métodos de ingreso:
- **Google OAuth**: Botón blanco con el ícono de Google (SVG inline multicolor) y texto "Continuar con Google".
- **Credenciales**: Formulario con campos de email (ícono `AtSign`) y contraseña (ícono `Lock`, toggle de visibilidad con `Eye`/`EyeOff`), botón submit con gradiente, y enlace "¿Olvidaste tu contraseña?" en violeta.
- **Navegación**: Enlace "Crear cuenta" que redirige a la vista de registro.
- **Decoración**: Badge institucional "Graphito ESCOM IPN" fijo en la parte inferior con indicador de actividad.

### 4.2 Register (`src/pages/Register.tsx`)

Pantalla de creación de cuenta con formulario extendido:
- **Campos**: Nombre completo, email, contraseña y confirmación de contraseña.
- **Medidor de fortaleza**: Cuatro segmentos de barra con colores (naranja = media) y texto descriptivo.
- **Indicador de coincidencia**: Ícono `Check` verde junto al campo de confirmación cuando las contraseñas coinciden.
- **Términos**: Checkbox de aceptación con enlaces subrayados a Términos de uso y Política de privacidad.
- **Alternativa**: Botón "Registrarse con Google" con estilo outline.

### 4.3 Biblioteca (`src/pages/Biblioteca.tsx`)

Pantalla principal post-autenticación que funciona como _dashboard_ del investigador:
- **Título**: "Mi Biblioteca" con subtítulo descriptivo.
- **Búsqueda y filtrado**: `SearchBar` con filtrado en tiempo real sobre título, descripción y categoría (resetea a página 1 al buscar).
- **Listado paginado**: 10 referencias por página, cada una renderizada con `ReferenceCard` que incluye su acordeón de comparaciones colapsable.
- **Datos de prueba**: 25 referencias mock generadas a partir de dos plantillas base (algoritmo de Dijkstra, análisis léxico de compiladores).
- **Paginación**: `PaginationControls` visible cuando hay más de 10 elementos.

### 4.4 NewReferenceModal (`src/pages/NewReferenceModal.tsx`)

Modal para agregar un nuevo código de referencia al sistema:
- **Columna izquierda**: Zona de _drag & drop_ para archivos `.c` o `.cpp` (máx. 5MB) con borde punteado e ícono `Upload`.
- **Columna derecha**: Campo de descripción con botón "Generar descripción con IA" (ícono `Sparkles`).
- **Sección de IA**: Toggle para activar generación de variaciones, campo de instrucciones para la IA, y control `+/-` de número de variaciones (1 a 10) con display numérico grande.
- **Footer**: Botón "Cancelar" + `GradientButton` "Agregar código de referencia".
- **Animación**: Entrada con GSAP (`opacity 0→1, scale 0.95→1, ease: back.out(1.2)`) y salida inversa con desmontaje diferido.

### 4.5 NewComparisonModal (`src/pages/NewComparisonModal.tsx`)

Modal para iniciar una nueva comparación de similitud:
- **Indicador de progreso**: "65% completado" en el header.
- **Zona de carga**: Área de drop con borde punteado y decoración de tarjetas apiladas difuminadas, soporte para `.zip`, `.js`, `.py`, `.java` (hasta 20MB).
- **Archivo validado**: Tarjeta de confirmación con ícono `CheckCircle2` verde, nombre del archivo, tamaño y estado de validación, más botón "Cambiar archivo".
- **Footer**: Botón "Cancelar" + `GradientButton` "Iniciar Análisis".

### 4.6 SimilarityReportModal (`src/pages/SimilarityReportModal.tsx`)

Modal de reporte completo, la pantalla más rica en interacción visual:
- **Navegación superior**: Botón "Volver a la biblioteca" con flecha.
- **Header**: Título "Reporte de similitud", nombre del proyecto, fecha y badge de estado "Análisis completado".
- **Indicador circular (gauge)**: Anillo SVG de 256×256px con gradiente `#scoreGradient`. El `strokeDashoffset` se anima de la circunferencia completa al valor del porcentaje de similitud (1000ms ease-out). En el centro se muestra el porcentaje en `text-5xl font-black` y la etiqueta ALTO/MEDIO/BAJO con color semántico.
- **Análisis estilométrico**: Tarjeta con barra de progreso violeta al 85% y _bullet points_ de hallazgos (nomenclatura de variables, estructura de comentarios).
- **Análisis semántico**: Tarjeta con barra de progreso azul al 62% y hallazgos de flujo algorítmico y manejo de excepciones.
- **Interpretación IA**: Bloque con ícono de `Sparkles` y texto generado progresivamente mediante efecto _typewriter_ (~3ms por carácter) con cursor parpadeante. El bloque incluye un resplandor decorativo en hover.
- **Footer**: Botón outline "Descargar reporte PDF" (ícono `Download`) + botón gradiente "Volver a la biblioteca" + ID de documento.

---

## 5. Conclusión

El frontend de Graphito implementa una interfaz de usuario moderna, cohesiva y funcional para la detección de similitud de código fuente en el entorno académico. El sistema de diseño oscuro con glassmorphism y resplandores animados establece una identidad visual distintiva que comunica precisión tecnológica, mientras que la paleta de colores semánticos facilita la interpretación inmediata de resultados de riesgo.

La arquitectura basada en componentes reutilizables (`AuthCard`, `GradientButton`, `ReferenceCard`) promueve la consistencia visual y la mantenibilidad del código. Las animaciones con GSAP proporcionan transiciones fluidas en modales, complementadas con micro-interacciones CSS (shimmer en botones, acordeones animados, glow en paginación) que enriquecen la experiencia de usuario sin comprometer el rendimiento.

En materia de accesibilidad, se implementaron prácticas recomendadas como _skip links_, anillos de focus visibles, atributos ARIA (`aria-label`, `aria-expanded`, `aria-current`) y etiquetas HTML semánticas, garantizando que la interfaz sea operable mediante teclado y lectores de pantalla.

El estado actual del frontend constituye una base sólida y escalable sobre la cual integrar el backend de comparación de código y el motor de inteligencia artificial para la generación de variaciones e interpretaciones de análisis.
