# Graphito Design System

Sistema de diseño oscuro para una herramienta de detección de plagio de código. La filosofía visual combina un fondo profundo de pizarra con acentos azul-violeta en gradiente, vidrio esmerilado (_glassmorphism_) y resplandores animados que evocan precisión tecnológica y análisis forense.

## Paleta de Colores

### Colores Base
```yaml
# Fondos
bg-primary:    "#0f172a"   # graphito-dark   — Fondo principal de la app
bg-card:       "#1e293b"   # graphito-card   — Fondo de tarjetas y superficies elevadas
bg-input:      "#121827"   # Fondo de inputs y áreas de carga
bg-overlay:    "#0f1522"   # Fondo de modales y reportes

# Bordes
border-default: "#334155"  # graphito-border — Bordes sutiles estándar
border-strong:  "#2b3346"  # Bordes más definidos para inputs y separadores

# Acento principal
accent-blue:   "#3b82f6"   # graphito-blue   — Azul primario (CTA, enlaces activos, focus)
accent-violet: "#a78bfa"   # graphito-violet  — Violeta del gradiente y acentos secundarios

# Semánticos (riesgo de similitud)
risk-high:     "#ef4444"   # Rojo — Similitud > 70%
risk-medium:   "#f59e0b"   # Ámbar — Similitud 30–70%
risk-low:      "#3b82f6"   # Azul — Similitud < 30%

# Estados
success:       "#059669"   # Esmeralda — Validación correcta, checkmarks
success-bg:    "#059669/10" # Fondo translúcido de éxito

# Texto
text-primary:  "#FFFFFF"   # Títulos y texto principal
text-secondary:"#CBD5E1"   # slate-300 — Texto descriptivo
text-muted:    "#94A3B8"   # slate-400 — Labels y detalles
text-disabled: "#64748B"   # slate-500 — Placeholders y texto inactivo
```

### Opacidades y Transparencias
- Tarjetas _glass_: `bg-[#1a2031]/65` con `backdrop-blur-xl`
- Inputs: `bg-[#121827]/30` o `/40`
- Backdrops modales: `bg-black/60` o `/80` con `backdrop-blur-sm` o `md`
- Áreas de código: `bg-[#121827]/50`
- Líneas decorativas: `border-[#2b3346]/40`

### Gradientes
```yaml
button-grad: "linear-gradient(to bottom, #3b82f6, #a78bfa)"
# Usado en botones CTA primarios con bg-[length:100%_200%] y hover:bg-bottom

text-grad: "gradient-to-r from-graphito-blue to-graphito-violet"
# Usado en el texto del logo con bg-clip-text text-transparent

icon-grad: "gradient-to-br from-graphito-blue to-graphito-violet"
# Usado en fondos de iconos destacados
```

## Tipografía

### Familias
| Rol | Familia | Variable Tailwind |
|-----|---------|-------------------|
| Títulos, encabezados, logo | 'Plus Jakarta Sans', sans-serif | `font-display` |
| Cuerpo, formularios, datos | 'Inter', sans-serif | `font-body` |
| Datos numéricos (porcentajes) | Monospace (sistema) | `font-mono` |

### Escala Tipográfica
| Nivel | Clase Tailwind | Tamaño | Peso | Uso |
|-------|---------------|--------|------|-----|
| H1 | `text-4xl` (36px) | 36px | `font-extrabold` | Logo en Login |
| H2 | `text-3xl` (30px) | 30px | `font-black` | Título de página (Biblioteca, Reporte) |
| H3 | `text-xl` (20px) | 20px | `font-bold` | Título de tarjeta |
| H4 | `text-lg` (18px) | 18px | `font-bold` | Subtítulos de sección |
| Body L | `text-[15px]` | 15px | `font-medium` | Texto en formularios, botones |
| Body | `text-sm` (14px) | 14px | `font-medium` / `font-semibold` | Texto descriptivo, navegación |
| Body S | `text-xs` (12px) | 12px | `font-medium` | Metadatos, detalles de comparación |
| Caption | `text-[11px]` | 11px | `font-medium` / `font-bold` | Información secundaria |
| Label | `text-[10px]` | 10px | `font-black` / `font-bold` / `uppercase tracking-widest` | Labels de formulario, badges, secciones |

### Tracking (letter-spacing)
- Títulos: `tracking-tight` / `tracking-tighter`
- Labels y badges: `tracking-widest` / `tracking-[0.2em]`
- Texto general: default

## Espaciado

Basado en la escala de Tailwind (múltiplos de 4px).

| Token | Valor | Uso típico |
|-------|-------|------------|
| `gap-1` / `gap-1.5` | 4px / 6px | Separación mínima entre elementos inline |
| `gap-2` / `gap-2.5` | 8px / 10px | Íconos + texto, chips |
| `gap-3` | 12px | Elementos de formulario, badges |
| `gap-4` | 16px | Separación entre columnas, header items |
| `gap-6` | 24px | Separación entre secciones de tarjeta |
| `gap-8` | 32px | Columnas de layout en modales |
| `gap-10` | 40px | Navegación del header |
| `p-4` / `p-6` | 16px / 24px | Padding de tarjeta |
| `p-8` / `p-10` | 32px / 40px | Padding de modal |
| `px-6 py-4` | 24px / 16px | Padding del header |
| `mb-6` / `mb-8` | 24px / 32px | Margen inferior entre secciones |
| `mt-10` | 40px | Margen superior de paginación |
| `space-y-3` a `space-y-8` | 12px a 32px | Espaciado vertical en listas |

## Bordes y Formas

### Radio de Borde (border-radius)

| Elemento | Clase | Valor |
|----------|-------|-------|
| AuthCard | `rounded-[2.5rem]` | 40px |
| Modal / Reportes | `rounded-3xl` | 24px |
| Tarjetas (ReferenceCard) | `rounded-2xl` | 16px |
| Inputs principales (Login) | `rounded-2xl` | 16px |
| Inputs secundarios (Register) | `rounded-xl` | 12px |
| Botones | `rounded-xl` | 12px |
| Botones de acción | `rounded-full` | circular |
| Badges, chips, pills | `rounded-full` | circular |

### Bordes
- Tarjetas: `border border-graphito-border` (#334155)
- Inputs: `border border-[#2b3346]`
- Áreas de drop: `border-2 border-dashed border-[#2b3346]`
- Separadores: `border-t border-[#2b3346]/40`
- Hover: `hover:border-graphito-blue/30` o `hover:border-[#334155]`

## Sombras y Resplandores

| Elemento | Sombra | Propósito |
|----------|--------|-----------|
| GradientButton default | `shadow-[0_0_20px_rgba(59,130,246,0.2)]` | Glow azul sutil |
| GradientButton hover | `hover:shadow-[0_0_30px_rgba(167,139,250,0.4)]` | Glow violeta intenso |
| Tarjeta hover | `hover:shadow-lg hover:shadow-graphito-blue/5` | Elevación con acento azul |
| Submit button | `shadow-lg shadow-graphito-blue/20` | Glow en botón submit |
| Paginación activa | `shadow-[0_0_15px_rgba(59,130,246,0.4)] scale-110` | Glow + escala en página actual |
| AuthCard | `shadow-2xl` | Sombra profunda estándar |
| Background glows | `radial-gradient` con blur 80px | Orbes animados de fondo |

## Componentes

### GradientButton
Botón CTA primario con gradiente azul-violeta vertical.

- **Fondo**: `bg-button-grad` (gradiente linear `#3b82f6 → #a78bfa`)
- **Forma**: `rounded-xl`, `px-6 py-2.5`
- **Tipografía**: `font-display font-bold`, `tracking-tight`, texto blanco
- **Hover**: El gradiente se desplaza (`hover:bg-bottom`), el glow se intensifica y cambia a violeta
- **Active**: `active:scale-95`
- **Focus**: `focus-visible:ring-2 focus-visible:ring-graphito-blue focus-visible:ring-offset-2 focus-visible:ring-offset-[#0f1522]`
- **Disabled**: `disabled:opacity-50 disabled:cursor-not-allowed`
- **Shimmer**: Pseudo-elemento `before` con gradiente blanco translúcido que se desliza horizontalmente en hover (`translate-x-[-200%] → translate-x-[200%]`)
- **Transición**: `transition-all duration-500 ease-in-out`

### Botón Secundario (outline)
- **Fondo**: `bg-graphito-card` o `bg-[#2b3346]/60`
- **Borde**: `border border-graphito-border`
- **Texto**: `text-slate-400` → `hover:text-white`
- **Forma**: `rounded-xl`
- **Active**: `active:scale-95`

### Botón de Texto / Link
- **Default**: `text-slate-400`
- **Hover**: `hover:text-white`
- **Ejemplo**: "Cancelar" en modales, "¿Olvidaste tu contraseña?"

### AuthCard
Contenedor _glass_ para login y registro.

- **Fondo**: `bg-[#1a2031]/65`
- **Borde**: `border border-[#2b3346]/40`
- **Forma**: `rounded-[2.5rem]` (40px)
- **Sombra**: `shadow-2xl`
- **Blur**: `backdrop-blur-xl`
- **Padding**: `p-8 sm:p-10`
- **Ancho máximo**: `max-w-[420px]`

### ReferenceCard
Tarjeta de código de referencia con acordeón de comparaciones.

- **Fondo**: `bg-graphito-card`
- **Borde**: `border border-graphito-border`
- **Forma**: `rounded-2xl`
- **Hover**: `hover:shadow-lg hover:shadow-graphito-blue/5`
- **Padding**: `p-6`
- **Badges de categoría**: `px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-widest border`
  - Cian: `bg-graphito-blue/10 text-graphito-blue border-graphito-blue/20`
  - Violeta: `bg-graphito-violet/10 text-graphito-violet border-graphito-violet/20`
  - Ámbar: `bg-risk-medium/10 text-risk-medium border-risk-medium/20`
- **Acordeón**: Animación `grid-rows-[0fr]` → `grid-rows-[1fr]` con transición `duration-300`
- **Ítems de comparación**: `p-4 bg-graphito-dark/50 border border-graphito-border rounded-xl hover:border-graphito-blue/30`

### SearchBar
Barra de búsqueda con botones de filtro y orden.

- **Input**: `bg-graphito-dark border border-graphito-border rounded-xl`, icono Search a la izquierda
- **Focus**: `focus:border-graphito-blue/50 focus:ring-4 focus:ring-graphito-blue/10`
- **Botones de acción**: `bg-graphito-card border border-graphito-border rounded-xl`, icono + texto
- **Hover**: `hover:text-white hover:border-graphito-blue/30`

### PaginationControls
Control de paginación con números de página.

- **Layout**: `flex items-center justify-between mt-10`
- **Página activa**: `bg-graphito-blue text-white shadow-[0_0_15px_rgba(59,130,246,0.4)] scale-110 rounded-xl`
- **Página inactiva**: `text-slate-400 hover:text-white hover:bg-graphito-card`
- **Disabled**: `text-slate-600 cursor-not-allowed`
- **Botones prev/next**: `p-2.5 min-w-11 min-h-11 rounded-lg`

### Header
Barra de navegación superior.

- **Fondo**: `bg-graphito-dark border-b border-graphito-border`
- **Padding**: `px-6 py-4`
- **Logo**: Imagen PNG + texto con degradado `from-graphito-blue to-graphito-violet bg-clip-text text-transparent`
- **Nav activo**: `text-white border-b-2 border-graphito-blue pb-1`
- **Nav inactivo**: `text-slate-400 hover:text-white`
- **Notificaciones**: Punto rojo `bg-risk-high` sobre el ícono de campana
- **Avatar**: `w-10 h-10 rounded-full bg-graphito-card border border-graphito-border`, indicador verde de conexión

### MouseGlowBackground
Fondo animado con 3 orbes de luz que orbitan y reaccionan al mouse.

- **Orbes**: `radial-gradient(circle, rgba(59-167, 130-139, 246-250, 0.22) 0%, rgba(..., 0.08) 40%, transparent 80%)`
- **Blur**: `blur-[80px]`
- **Tamaño**: 800–1400px
- **Comportamiento**: Orbitan con rotación lenta (0.025 rad/s) y son atraídos hacia el cursor (intensidad 45%, radio de influencia 600px)
- **Interpolación**: Los colores oscilan entre azul y violeta mediante `Math.sin`

### Modales (NewReferenceModal, NewComparisonModal, SimilarityReportModal)

- **Backdrop**: `fixed inset-0 bg-black/60 backdrop-blur-sm` (o `/80` para reportes)
- **Entrada**: GSAP `opacity: 0→1, scale: 0.95→1, ease: back.out(1.2)` en 300-400ms
- **Salida**: GSAP `opacity: 1→0, scale: 1→0.95, ease: power2.in` en 300ms
- **Contenedor**: `AuthCard` con `p-0 overflow-hidden` como base
- **Header**: `px-8 py-6 border-b border-[#2b3346]/40`
- **Body**: `p-8` o `p-10` con `overflow-y-auto` para contenido scrolleable
- **Footer**: `px-8/10 py-6/8 border-t border-[#2b3346]/40 bg-black/10` (o `/40`)
- **Cierre**: Botón X en esquina superior, backdrop clickeable, botón Cancelar
- **Max-height**: `max-h-[90vh]` en reportes

### Progress Bars
Barras de progreso usadas en el reporte de similitud y registro.

- **Track**: `h-1.5 w-full bg-[#2b3346]/60 rounded-full overflow-hidden`
- **Fill**: `h-full rounded-full` con color semántico:
  - Azul: `bg-graphito-blue` (análisis semántico)
  - Violeta: `bg-graphito-violet` (análisis estilométrico)
- **Animación**: `transition-all duration-1000 ease-out` al abrir el reporte
- **Password strength**: Segmentos de `h-1.5 flex-1 rounded-full` con colores naranja/ámbar

### Anillos Circulares (Gauge)
Usado en el reporte de similitud para mostrar el porcentaje principal.

- **SVG**: Anillo con `strokeWidth="16"`, `strokeLinecap="round"`
- **Fondo**: `stroke="#2b3346"`
- **Foreground**: Gradiente SVG `#scoreGradient` (blue → violet)
- **Animación**: `strokeDashoffset` transiciona de `circumference` al valor calculado en `duration-1000 ease-out`
- **Texto central**: Porcentaje en `text-5xl font-black` + label ALTO/MEDIO/BAJO en color semántico
- **Tamaño**: `w-64 h-64` (radio=90)

### Inputs de Formulario

- **Fondo**: `bg-[#121827]/30` o `/40`
- **Borde**: `border border-[#2b3346]`
- **Forma**: `rounded-2xl` (Login) o `rounded-xl` (Register)
- **Padding**: `py-3.5 pl-12 pr-4` (con icono) o `py-3 px-4` (sin icono)
- **Focus**: `focus:outline-none focus:ring-2 focus:ring-graphito-blue/50 focus:border-graphito-blue`
- **Placeholder**: `placeholder:text-slate-500` o `placeholder:text-slate-600`
- **Tipografía**: `text-[15px]` o `text-sm`, `font-medium`
- **Password**: `tracking-widest font-mono` para ocultar longitud
- **Icono**: Posicionado absolutamente a la izquierda, cambia de color en focus (`group-focus-within:text-graphito-blue`)

### Checkbox Personalizado
- **Size**: `w-4 h-4` o `w-5 h-5`
- **Forma**: `rounded`
- **Borde**: `border-[#2b3346]`
- **Fondo**: `bg-[#121827]/50`
- **Color**: `text-graphito-blue`
- **Focus**: `focus:ring-2 focus:ring-graphito-blue/50`

## Estados de Interacción

### Hover
- Botones: glow intensificado, gradiente desplazado, brillo en bordes
- Tarjetas: shadow + borde azul translúcido
- Links de navegación: `text-slate-400 → text-white`
- Íconos en inputs: `text-slate-400 → text-graphito-blue` (vía `group-focus-within`)

### Focus
- **Anillo**: `focus-visible:ring-2 focus-visible:ring-graphito-blue/50` (o `ring-slate-400` en elementos no primarios)
- **Offset**: `focus-visible:ring-offset-2` con color del fondo del contenedor
- **Outline**: `focus-visible:outline-none` (se usa ring en su lugar)

### Active
- **Escala**: `active:scale-95` en todos los botones y elementos clickeables

### Disabled
- **Opacidad**: `disabled:opacity-50`
- **Cursor**: `disabled:cursor-not-allowed`
- **Sin escala**: `disabled:active:scale-100`

### Loading / Progress
- Indicador de progreso: texto "65% completado" en header del modal
- Barras de progreso: animación de width `duration-1000 ease-out`
- Typewriter: texto que aparece carácter por carácter vía `setInterval`

## Animaciones

### Librería
- **GSAP** (`gsap` + `@gsap/react`): Para animaciones de entrada/salida de modales

### Catálogo de Animaciones

| Elemento | Trigger | Animación | Duración | Easing |
|----------|---------|-----------|----------|--------|
| Modal enter | mount | opacity 0→1 + scale 0.95→1 | 400ms | `back.out(1.2)` |
| Modal leave | unmount | opacity 1→0 + scale 1→0.95 | 300ms | `power2.in` |
| Backdrop | mount | opacity 0→1 | 300ms | `power2.out` |
| Report modal enter | mount | opacity + scale + translateY(32px→0) | 400ms | `back.out(1.2)` |
| Report modal leave | unmount | opacity + scale + translateY(0→32px) | 300ms | `power2.in` |
| Progress bars | mount | width 0%→target% | 1000ms | `ease-out` |
| SVG gauge | mount | strokeDashoffset animado | 1000ms | `ease-out` |
| Typewriter text | visible | Caracteres progresivos | ~333 chars/s | — |
| Button shimmer | hover | `translateX(-200%→200%)` | 700ms | — |
| Button gradient | hover | `bg-bottom` transition | 500ms | `ease-in-out` |
| Accordion expand | click | `grid-rows-[0fr]→[1fr]` | 300ms | `ease-in-out` |
| Logo rotate | group hover | `rotate-6` | 300ms | — |
| Pagination active | state | `scale-110` | 300ms | — |
| Background orbs | continuous | Órbita (0.025 rad/s) + lerp al mouse | 60fps | — |
| Glow color shift | continuous | Oscilación senoidal blue↔violet | — | — |
| Icon hover | hover | `group-hover:scale-110` | — | — |
| Link hover | hover | `transition-colors` | — | — |
| Input focus | focus | `transition-all` en border + ring | — | — |

## Accesibilidad

- **Skip link**: Enlace oculto (`sr-only`) visible al focus para saltar al contenido principal (`#main-content`)
- **Focus visible**: Todos los elementos interactivos tienen `focus-visible:ring-2` con colores de alto contraste
- **Aria labels**: `aria-label` en botones sin texto visible (notificaciones, menú usuario, paginación)
- **Aria expanded**: `aria-expanded` en el acordeón de comparaciones
- **Aria current**: `aria-current="page"` en la página activa de paginación
- **Disabled states**: `disabled:opacity-50 disabled:cursor-not-allowed` en todos los botones
- **Roles semánticos**: `<header>`, `<main>`, `<nav>` con HTML5 semántico
- **Contraste**: Texto blanco sobre fondos oscuros (#0f172a) cumple ratio WCAG AAA
- **Reducción de movimiento**: No se implementa `prefers-reduced-motion` (pendiente)
- **Labels**: Todos los inputs tienen `<label>` asociado mediante `htmlFor`/`id`

## Layout

- **Ancho máximo de contenido**: `max-w-7xl` (1280px) centrado con `mx-auto`
- **Layout principal**: `flex flex-col min-h-screen`
- **Header**: Fixed/static en la parte superior, ancho completo
- **Sidebar**: No implementado actualmente
- **Página de autenticación**: Centrada vertical y horizontalmente con `flex-1 flex items-center justify-center`
- **Biblioteca**: `max-w-7xl mx-auto p-8 flex-1 w-full flex flex-col`
- **Modales**: `fixed inset-0 z-[100] flex items-center justify-center p-4`

## Íconos

- **Librería**: `lucide-react` (v1.8.0)
- **Tamaños comunes**: 12px, 14px, 16px, 18px, 20px, 24px, 32px
- **Color**: `text-slate-400` por defecto, `text-graphito-blue` o `text-graphito-violet` como acento
- **Íconos SVG custom**: Logo de Google, check personalizado (para checkbox)

## Convenciones de Código

- **Utility de clases**: `cn()` en `src/lib/utils.js` — combina `clsx` + `tailwind-merge`
- **Tailwind**: v3.4.17 con `postcss` + `autoprefixer`
- **Componentes**: React 19 con TypeScript, exportaciones nombradas
- **Animaciones**: GSAP v3.12.5 con hook `useGSAP` de `@gsap/react`
- **Estilos globales**: Solo `@tailwind base/components/utilities` en `index.css`
