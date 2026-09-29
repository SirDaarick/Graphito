import { createContext, useContext, useEffect, useState, ReactNode } from "react";

export type Theme = "light" | "dark" | "system";

interface ThemeContextType {
    theme: Theme;
    resolvedTheme: "light" | "dark";
    isDark: boolean;
    setTheme: (theme: Theme) => void;
    toggleTheme: () => void;
}

const ThemeContext = createContext<ThemeContextType | undefined>(undefined);

const STORAGE_KEY = "graphito_theme";

export function ThemeProvider({ children }: { children: ReactNode }) {
    const [theme, setThemeState] = useState<Theme>(() => {
        const saved = localStorage.getItem(STORAGE_KEY) as Theme | null;
        return saved || "dark";
    });

    const [resolvedTheme, setResolvedTheme] = useState<"light" | "dark">("dark");

    useEffect(() => {
        const root = document.documentElement;
        const mediaQuery = window.matchMedia("(prefers-color-scheme: dark)");

        const computeAndApply = () => {
            let active: "light" | "dark";
            if (theme === "system") {
                active = mediaQuery.matches ? "dark" : "light";
            } else {
                active = theme;
            }

            setResolvedTheme(active);
            if (active === "dark") {
                root.classList.add("dark");
            } else {
                root.classList.remove("dark");
            }
        };

        computeAndApply();

        const listener = () => {
            if (theme === "system") {
                computeAndApply();
            }
        };

        mediaQuery.addEventListener("change", listener);
        return () => mediaQuery.removeEventListener("change", listener);
    }, [theme]);

    const setTheme = (newTheme: Theme) => {
        localStorage.setItem(STORAGE_KEY, newTheme);
        setThemeState(newTheme);
    };

    const toggleTheme = () => {
        const next = resolvedTheme === "dark" ? "light" : "dark";
        setTheme(next);
    };

    const isDark = resolvedTheme === "dark";

    return (
        <ThemeContext.Provider value={{ theme, resolvedTheme, isDark, setTheme, toggleTheme }}>
            {children}
        </ThemeContext.Provider>
    );
}

export function useTheme() {
    const context = useContext(ThemeContext);
    if (!context) {
        throw new Error("useTheme debe utilizarse dentro de un ThemeProvider");
    }
    return context;
}
