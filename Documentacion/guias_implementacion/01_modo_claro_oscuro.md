# Guía de Implementación 01: Modo Claro / Oscuro (Design Tokens & Ergonomía)

## 1. Fundamentos & Filosofía de Arquitectura
En una aplicación profesional, el cambio de tema **no se resuelve parchando clases condicionales `dark:` arbitrarias** en cada componente. Ese enfoque produce una deuda técnica insostenible, duplicación de código y un mantenimiento caótico.

La base sólida consiste en una **arquitectura basada en Design Tokens Semánticos**:
1. La aplicación define variables CSS semánticas (`--bg-primary`, `--surface-card`, `--text-main`, `--text-muted`, `--border-subtle`).
2. Tailwind CSS se configura para consumir dichas variables en lugar de colores rígidos (`#0B0F17`, `#ffffff`).
3. El estado del tema (`light` | `dark` | `system`) se centraliza en un Store/Context de React que sincroniza la clase `.dark` en el elemento raíz `<html>` y persiste la preferencia en `localStorage`.

---

## 2. Impacto en el Sistema
* **Frontend:**
  * Modificación de variables CSS en `frontend/src/index.css`.
  * Configuración del tema en `frontend/tailwind.config.js` (habilitar `darkMode: 'class'`).
  * Creación del hook/context `useTheme` en `frontend/src/lib/theme.tsx`.
  * Componente atómico `ThemeToggle.tsx` en el Header/Navbar.
* **Backend:** Sin impacto directo (a menos que se desee sincronizar preferencias de usuario en base de datos; para esta etapa, `localStorage` es la convención estándar).

---

## 3. Especificación Técnica Detallada

### 3.1. Definición de Variables CSS (`frontend/src/index.css`)
```css
@tailwind base;
@tailwind components;
@tailwind utilities;

:root {
  /* Tokens de Luz (Light Mode) */
  --bg-app: #f8fafc;
  --bg-surface: #ffffff;
  --bg-surface-elevated: #f1f5f9;
  --text-primary: #0f172a;
  --text-secondary: #475569;
  --text-muted: #94a3b8;
  --border-subtle: #e2e8f0;
  --border-strong: #cbd5e1;
  --accent-primary: #06b6d4; /* Cyan Graphito */
  --accent-focus: #0891b2;
}

.dark {
  /* Tokens de Oscuridad (Dark Mode) */
  --bg-app: #07090e;
  --bg-surface: #0b0f17;
  --bg-surface-elevated: #111827;
  --text-primary: #f8fafc;
  --text-secondary: #cbd5e1;
  --text-muted: #64748b;
  --border-subtle: #1e293b;
  --border-strong: #334155;
  --accent-primary: #22d3ee;
  --accent-focus: #06b6d4;
}

body {
  background-color: var(--bg-app);
  color: var(--text-primary);
  transition: background-color 0.2s ease, color 0.2s ease;
}
```

### 3.2. Configuración de Tailwind (`frontend/tailwind.config.js`)
```javascript
/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        app: 'var(--bg-app)',
        surface: {
          DEFAULT: 'var(--bg-surface)',
          elevated: 'var(--bg-surface-elevated)',
        },
        content: {
          primary: 'var(--text-primary)',
          secondary: 'var(--text-secondary)',
          muted: 'var(--text-muted)',
        },
        line: {
          subtle: 'var(--border-subtle)',
          strong: 'var(--border-strong)',
        }
      },
    },
  },
  plugins: [],
};
```

### 3.3. Contexto y Hook de Tema (`frontend/src/lib/theme.tsx`)
```typescript
import { createContext, useContext, useEffect, useState, ReactNode } from "react";

type Theme = "light" | "dark" | "system";

interface ThemeContextType {
  theme: Theme;
  resolvedTheme: "light" | "dark";
  setTheme: (theme: Theme) => void;
}

const ThemeContext = createContext<ThemeContextType | undefined>(undefined);

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<Theme>(() => {
    return (localStorage.getItem("graphito-theme") as Theme) || "system";
  });

  const [resolvedTheme, setResolvedTheme] = useState<"light" | "dark">("dark");

  useEffect(() => {
    const root = document.documentElement;
    const mediaQuery = window.matchMedia("(prefers-color-scheme: dark)");

    const applyTheme = () => {
      const active = theme === "system" ? (mediaQuery.matches ? "dark" : "light") : theme;
      setResolvedTheme(active);
      if (active === "dark") {
        root.classList.add("dark");
      } else {
        root.classList.remove("dark");
      }
    };

    applyTheme();
    mediaQuery.addEventListener("change", applyTheme);
    return () => mediaQuery.removeEventListener("change", applyTheme);
  }, [theme]);

  const setTheme = (newTheme: Theme) => {
    localStorage.setItem("graphito-theme", newTheme);
    setThemeState(newTheme);
  };

  return (
    <ThemeContext.Provider value={{ theme, resolvedTheme, setTheme }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme() {
  const context = useContext(ThemeContext);
  if (!context) throw new Error("useTheme debe usarse dentro de ThemeProvider");
  return context;
}
```

---

## 4. Riesgos y Anti-Patrones a Evitar
* ❌ **Anti-patrón:** Forzar colores duros con `bg-white` o `bg-black` en componentes hijos. Destruye la adaptabilidad.
* ❌ **Flash of Incorrect Theme (FOIT):** Si el script no evalúa `localStorage` antes del primer render de React, la pantalla puede parpadear en blanco antes de volverse oscura. Se previene con un pequeño script inline en `<head>` de `index.html`.
* ⚠️ **Contraste de Código:** Los bloques de código fuente (`<pre>` o editores) requieren temas propios (`monaco-dark` vs `monaco-light`). Sincronizar el editor con el tema global es mandatorio.

---

## 5. Criterios de Aceptación y Pruebas
1. Al conmutar entre `Claro`, `Oscuro` y `Sistema`, toda la interfaz (Navbar, Biblioteca, Modales, Tablas) responde sin recargar la página.
2. La preferencia sobrevive a un refresco forzado (`F5`).
3. El contraste en modo claro cumple con la norma WCAG AA (mínimo 4.5:1 para textos regulares).
