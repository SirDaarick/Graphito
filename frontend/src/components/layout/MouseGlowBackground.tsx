import { useEffect, useState, useRef, ReactNode } from "react";

interface Glow {
    id: number;
    x: number;
    y: number;
    baseX: number;
    baseY: number;
    size: number;
    colorPhase: number;
    colorSpeed: number;
    scalePhase: number;
    scaleSpeed: number;
    scaleAmplitude: number;
    angleOffset: number; // For diamond rotation
    orbitBaseRadius: number; // Base distance from center
    orbitPhase: number; // For radius pulsing
    orbitSpeed: number; // Frequency of radius variation
    currentScale?: number;
    currentColor1?: string;
    currentColor2?: string;
}

interface MouseGlowBackgroundProps {
    children: ReactNode;
}

export function MouseGlowBackground({ children }: MouseGlowBackgroundProps) {
    // Función para generar posiciones aleatorias distribuidas
    const generateInitialGlows = (): Glow[] => {
        return [0, 1, 2].map((i) => ({
            id: i + 1,
            x: 0,
            y: 0,
            baseX: 50,
            baseY: 50,
            size: 800 + Math.random() * 600,
            colorPhase: Math.random() * Math.PI * 2,
            colorSpeed: 0.1 + Math.random() * 0.2, // Cambio de color muy gradual
            scalePhase: Math.random() * Math.PI * 2,
            scaleSpeed: 0.04 + Math.random() * 0.08, // Mucho más lento (pulsación casi imperceptible)
            scaleAmplitude: 0.1 + Math.random() * 0.1,
            angleOffset: (i * Math.PI * 2) / 3, // 0, 120, 240 degrees (formación triangular para 3 puntos)
            orbitBaseRadius: 50 + Math.random() * 35, // Mucho más expansivos (entre 50% y 85% del viewport)
            orbitPhase: Math.random() * Math.PI * 2,
            orbitSpeed: 0.02 + Math.random() * 0.03, // Movimiento radial muy lento
        }));
    };

    const [_mousePosition, _setMousePosition] = useState({ x: 0, y: 0 });
    const [glows, setGlows] = useState<Glow[]>(generateInitialGlows);

    const requestRef = useRef<number>();
    const mouseRef = useRef({ x: 0, y: 0 });

    useEffect(() => {
        const handleMouseMove = (event: MouseEvent) => {
            mouseRef.current = { x: event.clientX, y: event.clientY };
        };

        window.addEventListener("mousemove", handleMouseMove);

        const animate = (time: number) => {
            const seconds = time * 0.001;
            const globalRotationSpeed = 0.025; // Rotación global extremadamente lenta

            // RGB Values from tailwind config
            const blueRGB = [59, 130, 246];
            const violetRGB = [167, 139, 250];

            setGlows((prevGlows) =>
                prevGlows.map((glow) => {
                    // Variar el radio de órbita dinámicamente de forma más amplia para que salgan de pantalla
                    const currentOrbitRadius = glow.orbitBaseRadius + Math.sin(seconds * glow.orbitSpeed + glow.orbitPhase) * 20;

                    // Calcular nueva posición base rotando (con radio variable)
                    const currentAngle = seconds * globalRotationSpeed + glow.angleOffset;
                    const bX_pct = 50 + Math.cos(currentAngle) * currentOrbitRadius;
                    const bY_pct = 50 + Math.sin(currentAngle) * currentOrbitRadius;

                    // Convertir porcentajes base a píxeles
                    const bX = (bX_pct / 100) * window.innerWidth;
                    const bY = (bY_pct / 100) * window.innerHeight;

                    // Aumentamos el radio de influencia y la intensidad de atracción hacia el mouse
                    const influenceRadius = 600;
                    const attractIntensity = 0.45; // 45% de atracción hacia el mouse

                    // Dirección desde la base hacia el mouse
                    const dx = mouseRef.current.x - bX;
                    const dy = mouseRef.current.y - bY;
                    const distance = Math.sqrt(dx * dx + dy * dy);

                    // Punto objetivo relativo a la base
                    let targetX = bX;
                    let targetY = bY;

                    if (distance > 0) {
                        const moveRatio = Math.min(distance, influenceRadius) / distance;
                        targetX = bX + dx * moveRatio * attractIntensity;
                        targetY = bY + dy * moveRatio * attractIntensity;
                    }

                    // Suavizado (Lerp) para el movimiento
                    const newX = glow.x + (targetX - glow.x) * 0.02;
                    const newY = glow.y + (targetY - glow.y) * 0.02;

                    // Update scale based on time using sine wave
                    const currentScale = 1 + Math.sin(seconds * glow.scaleSpeed + glow.scalePhase) * glow.scaleAmplitude;

                    // Color interpolation logic
                    const colorT = (Math.sin(seconds * glow.colorSpeed + glow.colorPhase) + 1) / 2;
                    const r = Math.round(blueRGB[0] * (1 - colorT) + violetRGB[0] * colorT);
                    const g = Math.round(blueRGB[1] * (1 - colorT) + violetRGB[1] * colorT);
                    const b = Math.round(blueRGB[2] * (1 - colorT) + violetRGB[2] * colorT);

                    const currentColor1 = `rgba(${r}, ${g}, ${b}, 0.22)`;
                    const currentColor2 = `rgba(${r}, ${g}, ${b}, 0.08)`;

                    return { ...glow, x: newX, y: newY, currentScale, currentColor1, currentColor2 };
                })
            );
            requestRef.current = requestAnimationFrame(animate);
        };

        requestRef.current = requestAnimationFrame(animate);

        return () => {
            window.removeEventListener("mousemove", handleMouseMove);
            if (requestRef.current) cancelAnimationFrame(requestRef.current);
        };
    }, []);

    return (
        <div className="relative min-h-screen bg-graphito-dark overflow-hidden font-body">
            {/* Contenedores de los Resplandores (Glows) */}
            <div className="pointer-events-none fixed inset-0 z-0 overflow-hidden">
                {glows.map((glow) => {
                    const scale = glow.currentScale || 1;
                    const currentSize = glow.size * scale;

                    return (
                        <div
                            key={glow.id}
                            className="absolute rounded-full transition-opacity duration-1000 blur-[80px]"
                            style={{
                                width: `${currentSize}px`,
                                height: `${currentSize}px`,
                                left: `${glow.x - currentSize / 2}px`,
                                top: `${glow.y - currentSize / 2}px`,
                                background: `radial-gradient(circle, ${glow.currentColor1} 0%, ${glow.currentColor2} 40%, transparent 80%)`,
                                opacity: 0.6 + (scale - 1) * 2, // Sutil variación de opacidad también
                            }}
                        />
                    );
                })}
            </div>

            {/* Contenido principal */}
            <div className="relative z-10 w-full min-h-screen flex flex-col">
                {children}
            </div>
        </div>
    );
}
