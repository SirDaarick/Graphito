import { useEffect, useRef, useState, ReactNode } from "react";

interface MouseGlowBackgroundProps {
    children: ReactNode;
}

export function MouseGlowBackground({ children }: MouseGlowBackgroundProps) {
    const mouseBlobRef = useRef<HTMLDivElement>(null);
    const [isTouch, setIsTouch] = useState(false);

    useEffect(() => {
        // Detectar si el dispositivo es táctil (tablet o móvil) o sin puntero fino
        const isTouchDevice =
            "ontouchstart" in window ||
            navigator.maxTouchPoints > 0 ||
            window.matchMedia("(pointer: coarse)").matches;

        setIsTouch(isTouchDevice);

        if (isTouchDevice) {
            // En tablets/móviles NO corremos ningún loop de animación JS ni listeners de mouse.
            // Los orbes flotan 100% mediante animaciones CSS optimizadas en el GPU compositor.
            return;
        }

        // En pantallas desktop con mouse físico, seguimos suavemente el cursor sin re-renderizar React
        let mouseX = window.innerWidth / 2;
        let mouseY = window.innerHeight / 2;
        let currentX = mouseX;
        let currentY = mouseY;
        let rafId: number;

        const handleMouseMove = (e: MouseEvent) => {
            mouseX = e.clientX;
            mouseY = e.clientY;
        };

        const updatePosition = () => {
            // Suavizado lerp sin provocar re-renders de React
            currentX += (mouseX - currentX) * 0.05;
            currentY += (mouseY - currentY) * 0.05;

            if (mouseBlobRef.current) {
                mouseBlobRef.current.style.transform = `translate3d(${currentX - 350}px, ${currentY - 350}px, 0)`;
            }

            rafId = requestAnimationFrame(updatePosition);
        };

        window.addEventListener("mousemove", handleMouseMove, { passive: true });
        rafId = requestAnimationFrame(updatePosition);

        return () => {
            window.removeEventListener("mousemove", handleMouseMove);
            cancelAnimationFrame(rafId);
        };
    }, []);

    return (
        <div className="relative min-h-[100dvh] bg-slate-50 dark:bg-graphito-dark transition-colors duration-200 overflow-hidden font-body">
            {/* Contenedores de los Resplandores (Glows) */}
            <div className="pointer-events-none fixed inset-0 z-0 overflow-hidden opacity-40 dark:opacity-80 transition-opacity duration-300">
                {/* Orbe 1: Superior izquierdo (Azul primario Graphito) */}
                <div
                    className="absolute -top-32 -left-32 w-[600px] h-[600px] rounded-full animate-glow-1 pointer-events-none"
                    style={{
                        background: "radial-gradient(circle, rgba(59, 130, 246, 0.22) 0%, rgba(59, 130, 246, 0.12) 25%, rgba(59, 130, 246, 0.04) 50%, transparent 70%)",
                        transform: "translateZ(0)",
                        backfaceVisibility: "hidden",
                    }}
                />

                {/* Orbe 2: Inferior derecho (Violeta Graphito) */}
                <div
                    className="absolute -bottom-32 -right-32 w-[650px] h-[650px] rounded-full animate-glow-2 pointer-events-none"
                    style={{
                        background: "radial-gradient(circle, rgba(167, 139, 250, 0.20) 0%, rgba(167, 139, 250, 0.10) 25%, rgba(167, 139, 250, 0.03) 50%, transparent 70%)",
                        transform: "translateZ(0)",
                        backfaceVisibility: "hidden",
                    }}
                />

                {/* Orbe 3: Centro-lateral flotante */}
                <div
                    className="absolute top-1/3 left-1/2 -translate-x-1/2 w-[550px] h-[550px] rounded-full animate-glow-3 pointer-events-none"
                    style={{
                        background: "radial-gradient(circle, rgba(99, 102, 241, 0.16) 0%, rgba(99, 102, 241, 0.08) 25%, rgba(99, 102, 241, 0.02) 50%, transparent 70%)",
                        transform: "translateZ(0)",
                        backfaceVisibility: "hidden",
                    }}
                />

                {/* Orbe interactivo: Solo activo en Desktop con mouse */}
                {!isTouch && (
                    <div
                        ref={mouseBlobRef}
                        className="absolute top-0 left-0 w-[700px] h-[700px] rounded-full transition-opacity duration-500 opacity-60 pointer-events-none"
                        style={{
                            background: "radial-gradient(circle, rgba(59, 130, 246, 0.18) 0%, rgba(167, 139, 250, 0.08) 30%, rgba(167, 139, 250, 0.02) 55%, transparent 70%)",
                            transform: "translate3d(-500px, -500px, 0)",
                            willChange: "transform",
                            backfaceVisibility: "hidden",
                        }}
                    />
                )}
            </div>

            {/* Contenido principal */}
            <div className="relative z-10 w-full min-h-[100dvh] flex flex-col">
                {children}
            </div>
        </div>
    );
}