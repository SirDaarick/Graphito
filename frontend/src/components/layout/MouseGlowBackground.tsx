import { ReactNode } from "react";
import DotGrid from "../backgrounds/DotGrid";
import { useTheme } from "../../context/ThemeContext";

interface MouseGlowBackgroundProps {
    children: ReactNode;
}

export function MouseGlowBackground({ children }: MouseGlowBackgroundProps) {
    const { isDark } = useTheme();

    return (
        <div className="relative min-h-[100dvh] bg-slate-50 dark:bg-graphito-dark transition-colors duration-200 overflow-hidden font-body">
            {/* Fondo permanente interactivo de puntos WebGL2 React Bits */}
            <div className="fixed inset-0 z-0 pointer-events-none overflow-hidden">
                <DotGrid
                    dotSize={3.5}
                    gap={22}
                    baseColor={isDark ? "#1e293b" : "#cbd5e1"}
                    activeColor={isDark ? "#8b5cf6" : "#3b82f6"}
                    proximity={130}
                    shockRadius={320}
                    shockStrength={4}
                    glow={0}
                    fade={0.15}
                    shape="circle"
                />
            </div>

            {/* Contenido principal */}
            <div className="relative z-10 w-full min-h-[100dvh] flex flex-col">
                {children}
            </div>
        </div>
    );
}
