import { useEffect, useRef } from "react";

export type BackgroundMode = "dots" | "waves" | "aurora" | "dotgrid";

export interface InteractiveCanvasProps {
    mode?: BackgroundMode;
    className?: string;
    darkBaseColor?: string;
    lightBaseColor?: string;
    colorStopBlue?: string;
    colorStopViolet?: string;
    colorStopPink?: string;
}

interface Point {
    x0: number;
    y0: number;
    x: number;
    y: number;
    activation: number;
}

// Helpers for color interpolation
function parseHex(hex: string): [number, number, number] {
    const cleaned = hex.replace("#", "");
    const num = parseInt(cleaned, 16);
    return [(num >> 16) & 255, (num >> 8) & 255, num & 255];
}

function lerpColor(
    c1: [number, number, number],
    c2: [number, number, number],
    t: number
): [number, number, number] {
    return [
        Math.round(c1[0] + (c2[0] - c1[0]) * t),
        Math.round(c1[1] + (c2[1] - c1[1]) * t),
        Math.round(c1[2] + (c2[2] - c1[2]) * t),
    ];
}

export function InteractiveCanvas({
    mode = "dots",
    className = "",
    darkBaseColor = "#090e1a",
    lightBaseColor = "#f8fafc",
    colorStopBlue = "#3b82f6",
    colorStopViolet = "#8b5cf6",
    colorStopPink = "#ec4899",
}: InteractiveCanvasProps) {
    const canvasRef = useRef<HTMLCanvasElement>(null);
    const containerRef = useRef<HTMLDivElement>(null);

    // Mouse and interaction state stored in refs to prevent React re-renders during motion
    const pointerRef = useRef({
        x: -9999,
        y: -9999,
        targetX: -9999,
        targetY: -9999,
        active: false,
    });

    const isDarkRef = useRef(false);
    const prefersReducedMotionRef = useRef(false);

    useEffect(() => {
        const canvas = canvasRef.current;
        const container = containerRef.current;
        if (!canvas || !container) return;

        const ctx = canvas.getContext("2d", { alpha: true });
        if (!ctx) return;

        // Sync dark mode state
        const updateTheme = () => {
            isDarkRef.current = document.documentElement.classList.contains("dark");
        };
        updateTheme();

        const themeObserver = new MutationObserver((mutations) => {
            for (const m of mutations) {
                if (m.attributeName === "class") {
                    updateTheme();
                    break;
                }
            }
        });
        themeObserver.observe(document.documentElement, { attributes: true });

        // Reduced motion preference
        const motionQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
        prefersReducedMotionRef.current = motionQuery.matches;
        const handleMotionChange = (e: MediaQueryListEvent) => {
            prefersReducedMotionRef.current = e.matches;
        };
        motionQuery.addEventListener("change", handleMotionChange);

        // Colors setup
        const rgbBlue = parseHex(colorStopBlue);
        const rgbViolet = parseHex(colorStopViolet);
        const rgbPink = parseHex(colorStopPink);

        let width = 0;
        let height = 0;
        let dpr = 1;
        let points: Point[] = [];
        let cols = 0;
        let rows = 0;
        const gridSpacing = 42;

        const rebuildPoints = () => {
            points = [];
            cols = Math.ceil(width / gridSpacing) + 1;
            rows = Math.ceil(height / gridSpacing) + 1;

            const offsetX = (width - (cols - 1) * gridSpacing) / 2;
            const offsetY = (height - (rows - 1) * gridSpacing) / 2;

            for (let r = 0; r < rows; r++) {
                for (let c = 0; c < cols; c++) {
                    const x0 = offsetX + c * gridSpacing;
                    const y0 = offsetY + r * gridSpacing;
                    points.push({
                        x0,
                        y0,
                        x: x0,
                        y: y0,
                        activation: 0,
                    });
                }
            }
        };

        const handleResize = () => {
            if (!container || !canvas) return;
            const rect = container.getBoundingClientRect();
            width = rect.width;
            height = rect.height;
            dpr = Math.min(window.devicePixelRatio || 1, 2);

            canvas.width = Math.floor(width * dpr);
            canvas.height = Math.floor(height * dpr);
            canvas.style.width = `${width}px`;
            canvas.style.height = `${height}px`;

            if (mode === "dots") {
                rebuildPoints();
            }
        };

        const resizeObserver = new ResizeObserver(() => {
            handleResize();
        });
        resizeObserver.observe(container);
        handleResize();

        // Pointer listeners on window
        const handlePointerMove = (e: PointerEvent) => {
            if (e.pointerType === "touch") return;
            const rect = canvas.getBoundingClientRect();
            pointerRef.current.x = e.clientX - rect.left;
            pointerRef.current.y = e.clientY - rect.top;
            pointerRef.current.active = true;

            // Initialize target on first move
            if (pointerRef.current.targetX < -1000) {
                pointerRef.current.targetX = pointerRef.current.x;
                pointerRef.current.targetY = pointerRef.current.y;
            }
        };

        const handlePointerLeave = () => {
            pointerRef.current.active = false;
        };

        window.addEventListener("pointermove", handlePointerMove, { passive: true });
        document.addEventListener("mouseleave", handlePointerLeave);

        let animationFrameId: number;
        let startTime = performance.now();

        // ------------------ Render functions for each mode ------------------

        const renderDots = (time: number) => {
            ctx.clearRect(0, 0, width, height);

            const isDark = isDarkRef.current;
            const mouseX = pointerRef.current.x;
            const mouseY = pointerRef.current.y;
            const mouseActive = pointerRef.current.active;
            const influenceRadius = 135;
            const influenceRadiusSq = influenceRadius * influenceRadius;

            // Update points
            for (let i = 0; i < points.length; i++) {
                const p = points[i];
                let targetX = p.x0;
                let targetY = p.y0;
                let targetActivation = 0;

                if (mouseActive) {
                    const dx = p.x - mouseX;
                    const dy = p.y - mouseY;
                    const distSq = dx * dx + dy * dy;

                    if (distSq < influenceRadiusSq) {
                        const dist = Math.sqrt(distSq);
                        const factor = 1 - dist / influenceRadius;
                        const push = factor * 16;
                        const angle = Math.atan2(dy, dx);
                        targetX = p.x0 + Math.cos(angle) * push;
                        targetY = p.y0 + Math.sin(angle) * push;
                        targetActivation = factor;
                    }
                }

                // Smooth spring-like lerp
                p.x += (targetX - p.x) * 0.14;
                p.y += (targetY - p.y) * 0.14;
                p.activation += (targetActivation - p.activation) * 0.12;
            }

            // Draw network connecting lines for active points
            ctx.lineWidth = 1;
            for (let r = 0; r < rows; r++) {
                for (let c = 0; c < cols; c++) {
                    const idx = r * cols + c;
                    const p1 = points[idx];
                    if (!p1) continue;

                    // Connect to right neighbor
                    if (c < cols - 1) {
                        const p2 = points[idx + 1];
                        if (p2) {
                            const act = Math.max(p1.activation, p2.activation);
                            if (act > 0.05) {
                                const alpha = act * (isDark ? 0.35 : 0.22);
                                ctx.strokeStyle = `rgba(139, 92, 246, ${alpha})`;
                                ctx.beginPath();
                                ctx.moveTo(p1.x, p1.y);
                                ctx.lineTo(p2.x, p2.y);
                                ctx.stroke();
                            }
                        }
                    }

                    // Connect to bottom neighbor
                    if (r < rows - 1) {
                        const p3 = points[idx + cols];
                        if (p3) {
                            const act = Math.max(p1.activation, p3.activation);
                            if (act > 0.05) {
                                const alpha = act * (isDark ? 0.35 : 0.22);
                                ctx.strokeStyle = `rgba(59, 130, 246, ${alpha})`;
                                ctx.beginPath();
                                ctx.moveTo(p1.x, p1.y);
                                ctx.lineTo(p3.x, p3.y);
                                ctx.stroke();
                            }
                        }
                    }
                }
            }

            // Draw dots
            const baseAlpha = isDark ? 0.15 : 0.2;
            const baseColor = isDark
                ? `rgba(148, 163, 184, ${baseAlpha})`
                : `rgba(100, 116, 139, ${baseAlpha})`;

            for (let i = 0; i < points.length; i++) {
                const p = points[i];
                ctx.beginPath();

                if (p.activation > 0.04) {
                    const t = Math.min(1, p.activation);
                    let colorRgb: [number, number, number];
                    if (t < 0.5) {
                        colorRgb = lerpColor(rgbBlue, rgbViolet, t * 2);
                    } else {
                        colorRgb = lerpColor(rgbViolet, rgbPink, (t - 0.5) * 2);
                    }
                    const dotAlpha = isDark ? 0.4 + t * 0.6 : 0.35 + t * 0.55;
                    ctx.fillStyle = `rgba(${colorRgb[0]}, ${colorRgb[1]}, ${colorRgb[2]}, ${dotAlpha})`;
                    const radius = 1.3 + t * 1.5;
                    ctx.arc(p.x, p.y, radius, 0, Math.PI * 2);
                } else {
                    ctx.fillStyle = baseColor;
                    ctx.arc(p.x, p.y, 1.2, 0, Math.PI * 2);
                }
                ctx.fill();
            }
        };

        const renderWaves = (time: number) => {
            ctx.clearRect(0, 0, width, height);

            const isDark = isDarkRef.current;
            const mouseX = pointerRef.current.x;
            const mouseY = pointerRef.current.y;
            const mouseActive = pointerRef.current.active;

            const waveCount = 7;
            const step = 14;

            // Gradient across width
            const grad = ctx.createLinearGradient(0, 0, width, 0);
            grad.addColorStop(0, colorStopBlue);
            grad.addColorStop(0.5, colorStopViolet);
            grad.addColorStop(1, colorStopPink);

            for (let i = 0; i < waveCount; i++) {
                const normalized = i / (waveCount - 1);
                const baseY = height * (0.28 + normalized * 0.54);
                const amplitude = 18 + i * 5;
                const freq1 = 0.0022 + i * 0.0003;
                const freq2 = 0.0048 - i * 0.0002;
                const speed = (0.0007 + i * 0.00015) * (i % 2 === 0 ? 1 : -1);
                const phase = i * 1.2;

                ctx.beginPath();
                let started = false;

                for (let x = 0; x <= width + step; x += step) {
                    // Base sinusoidal oscillation
                    const sin1 = Math.sin(x * freq1 + time * speed + phase);
                    const sin2 = Math.cos(x * freq2 - time * speed * 0.7);
                    let y = baseY + (sin1 + sin2 * 0.5) * amplitude;

                    // Mouse elastic deflection
                    if (mouseActive) {
                        const dx = x - mouseX;
                        const sigma = 180;
                        const gaussian = Math.exp(-(dx * dx) / (2 * sigma * sigma));
                        const bend = (mouseY - baseY) * 0.42 * gaussian;
                        y += bend;
                    }

                    if (!started) {
                        ctx.moveTo(x, y);
                        started = true;
                    } else {
                        ctx.lineTo(x, y);
                    }
                }

                // Stroke wave line
                ctx.strokeStyle = grad;
                const strokeAlpha = isDark ? 0.32 + normalized * 0.2 : 0.2 + normalized * 0.15;
                ctx.globalAlpha = strokeAlpha;
                ctx.lineWidth = 1.8 + normalized * 0.8;
                ctx.stroke();

                // Translucent fill underneath
                ctx.lineTo(width, height);
                ctx.lineTo(0, height);
                ctx.closePath();
                ctx.fillStyle = grad;
                ctx.globalAlpha = isDark ? 0.035 : 0.018;
                ctx.fill();
            }

            ctx.globalAlpha = 1;
        };

        const renderAurora = (time: number) => {
            ctx.clearRect(0, 0, width, height);

            const isDark = isDarkRef.current;
            const t = time * 0.00045;

            // Ambient drifting aurora orbs (smooth, fluid, without cursor-following spotlight)
            const orbs = [
                {
                    x: width * (0.25 + 0.18 * Math.sin(t * 1.1)),
                    y: height * (0.28 + 0.14 * Math.cos(t * 0.9)),
                    radius: Math.max(width, height) * 0.42,
                    rgb: rgbBlue,
                    alpha: isDark ? 0.32 : 0.16,
                },
                {
                    x: width * (0.75 + 0.16 * Math.cos(t * 0.8)),
                    y: height * (0.35 + 0.18 * Math.sin(t * 1.3)),
                    radius: Math.max(width, height) * 0.48,
                    rgb: rgbViolet,
                    alpha: isDark ? 0.35 : 0.18,
                },
                {
                    x: width * (0.5 + 0.22 * Math.sin(t * 0.7 + 1)),
                    y: height * (0.65 + 0.16 * Math.cos(t * 1.1 + 2)),
                    radius: Math.max(width, height) * 0.44,
                    rgb: rgbPink,
                    alpha: isDark ? 0.28 : 0.14,
                },
                {
                    x: width * (0.38 + 0.2 * Math.cos(t * 0.95 + 3)),
                    y: height * (0.45 + 0.18 * Math.sin(t * 0.85 + 1.5)),
                    radius: Math.max(width, height) * 0.38,
                    rgb: rgbViolet,
                    alpha: isDark ? 0.24 : 0.12,
                },
            ];

            // In dark mode, screen composite adds ethereal luminescence
            ctx.globalCompositeOperation = isDark ? "screen" : "source-over";

            for (const orb of orbs) {
                if (orb.radius <= 0) continue;
                const radial = ctx.createRadialGradient(
                    orb.x,
                    orb.y,
                    0,
                    orb.x,
                    orb.y,
                    orb.radius
                );
                radial.addColorStop(
                    0,
                    `rgba(${orb.rgb[0]}, ${orb.rgb[1]}, ${orb.rgb[2]}, ${orb.alpha})`
                );
                radial.addColorStop(
                    0.45,
                    `rgba(${orb.rgb[0]}, ${orb.rgb[1]}, ${orb.rgb[2]}, ${orb.alpha * 0.45})`
                );
                radial.addColorStop(
                    0.8,
                    `rgba(${orb.rgb[0]}, ${orb.rgb[1]}, ${orb.rgb[2]}, ${orb.alpha * 0.12})`
                );
                radial.addColorStop(1, "rgba(0, 0, 0, 0)");

                ctx.fillStyle = radial;
                ctx.beginPath();
                ctx.arc(orb.x, orb.y, orb.radius, 0, Math.PI * 2);
                ctx.fill();
            }

            ctx.globalCompositeOperation = "source-over";
        };

        // Main animation loop
        const loop = (currentTime: number) => {
            const elapsed = currentTime - startTime;

            ctx.save();
            ctx.scale(dpr, dpr);

            if (mode === "dots") {
                renderDots(elapsed);
            } else if (mode === "waves") {
                renderWaves(elapsed);
            } else if (mode === "aurora") {
                renderAurora(elapsed);
            }

            ctx.restore();

            // If user prefers reduced motion, draw once and don't loop
            if (!prefersReducedMotionRef.current) {
                animationFrameId = requestAnimationFrame(loop);
            }
        };

        animationFrameId = requestAnimationFrame(loop);

        return () => {
            cancelAnimationFrame(animationFrameId);
            resizeObserver.disconnect();
            themeObserver.disconnect();
            motionQuery.removeEventListener("change", handleMotionChange);
            window.removeEventListener("pointermove", handlePointerMove);
            document.removeEventListener("mouseleave", handlePointerLeave);
        };
    }, [
        mode,
        colorStopBlue,
        colorStopViolet,
        colorStopPink,
        darkBaseColor,
        lightBaseColor,
    ]);

    return (
        <div
            ref={containerRef}
            className={`absolute inset-0 pointer-events-none overflow-hidden ${className}`}
            style={{
                backgroundColor: "transparent",
            }}
        >
            <canvas
                ref={canvasRef}
                className="block w-full h-full pointer-events-none"
                aria-hidden="true"
            />
        </div>
    );
}
