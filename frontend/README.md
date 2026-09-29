# 🖥️ Graphito Frontend — Guía de Arquitectura y Desarrollo

Interfaz de usuario web para **Graphito** (Sistema de Apoyo a la Decisión Docente para Integridad Académica en C/C++), desarrollada con **React 18**, **TypeScript**, **Vite** y **Tailwind CSS**.

---

## 🏛️ Principios y Patrones Arquitectónicos

1. **Clean UI & Component-Driven Design:** Separación estricta entre componentes de presentación (`components/ui`), estructuras de layout (`components/layout`), visores especializados (`components/code`) y vistas orquestadoras (`pages/`).
2. **Human-in-the-Loop (HITL) First:** Las interfaces no dictan sentencias absolutas; presentan telemetría forense comprensible, desglose bimodal (semántica DFG + estilometría CharCNN) y controles ergonómicos para la evaluación del docente.
3. **Alto Rendimiento en Código Diff:** El componente de comparación lado a lado utiliza un motor léxico determinista (`SynthwaveHighlighter.tsx`) sin sobrecarga de dependencias pesadas de runtime para asegurar 60 FPS durante el scroll bidireccional sincronizado.
4. **Resiliencia & Reactividad Local:** Sincronización desacoplada de decisiones y veredictos docentes (`verdicts.ts`) mediante un bus reactivo de eventos locales (`CustomEvent`) respaldado en `localStorage`.

---

## 📂 Estructura de Directorios

```plaintext
frontend/
├── src/
│   ├── assets/               # Recursos estáticos (logos, iconografía)
│   ├── components/           # Componentes modulares
│   │   ├── code/             # Visor Side-by-Side Diff y resaltador Synthwave '84
│   │   │   ├── SideBySideDiffViewer.tsx
│   │   │   └── SynthwaveHighlighter.tsx
│   │   ├── layout/           # Tarjetas de referencia, tarjetas contenedoras y wrappers
│   │   │   ├── AuthCard.tsx
│   │   │   └── ReferenceCard.tsx
│   │   └── ui/               # Botones, tooltips, modales y átomos reutilizables
│   ├── lib/                  # Clientes de API, utilidades y persistencia
│   │   ├── api.ts            # Cliente HTTP asíncrono para backend FastAPI
│   │   ├── utils.ts          # Ayudantes de clases con clsx y tailwind-merge
│   │   └── verdicts.ts       # Event bus reactivo de veredictos ("CONFORME" / "DUDA")
│   ├── pages/                # Vistas principales de la aplicación
│   │   ├── Biblioteca.tsx    # Gestión de problemas, referencias y entregas
│   │   ├── SimilarityReportModal.tsx # Visor pericial HUD y modo diff ultra-ancho
│   │   └── ...
│   ├── App.tsx               # Enrutamiento y árbol principal de la app
│   ├── main.tsx              # Punto de entrada Vite/React
│   └── index.css             # Configuración de Tailwind, scrollbars oscuros y estilos de impresión
├── design.md                 # Especificaciones del Sistema de Diseño (Design System)
├── package.json              # Dependencias y scripts npm
└── vite.config.ts            # Configuración de empaquetado Vite
```

---

## 🌟 Módulos Destacados

### 1. Visualizador Diff Side-by-Side (`SideBySideDiffViewer.tsx`)
- **Diseño Ultra-Ancho Dinámico:** Se expande hasta un 94%-98% del ancho de pantalla con soporte multirresolución (desde laptops 720p hasta monitores 1440p+).
- **Tema Synthwave '84:** Resaltado léxico de palabras clave, tipos estándar (`size_t`, `std::vector`), directivas de preprocesador (`#include`) y literales.
- **Scroll Sincronizado:** Desplazamiento bidireccional suave con banderas de bloqueo para prevenir bucles recursivos de eventos de scroll.
- **Comentarios del Docente:** Soporte para agregar notas asociadas a líneas específicas de código o conclusiones generales con renderizado interactivo.

### 2. Dashboard Pericial Minimalista (`SimilarityReportModal.tsx`)
- **Barra Hero HUD:** Lectura pericial instantánea en gran formato (`text-4xl` / `text-5xl`) para Similitud Global, Semántica DFG, Estilometría IA y Discrepancia Asimétrica.
- **Botones Icónicos Intuitivos:** Botones limpios sin texto redundante con tooltips flotantes animados y atajos de teclado (`A` para Conforme, `R` para Aclaración/Duda, `Esc` para Cerrar, `←` / `→` para navegar entregas).
- **Exportación & `@media print`:** Preparado para impresión directa en papel o PDF con código fuente numerado y notas pedagógicas.

### 3. Veredictos Reactivos en Lista de Tareas (`ReferenceCard.tsx`)
- Indicadores visuales en verde esmeralda (`Conforme`) y amarillo ámbar (`Duda`) que se actualizan de forma inmediata al evaluar una entrega en el modal.

---

## 🚀 Puesta en Marcha en Desarrollo

### Prerrequisitos
- Node.js 18+ o 20+
- npm o pnpm

### Comandos

```bash
# 1. Instalar dependencias
npm install

# 2. Iniciar servidor de desarrollo con HMR
npm run dev

# 3. Compilar para producción (validación de tipos y bundles)
npm run build

# 4. Previsualizar compilación de producción localmente
npm run preview
```
