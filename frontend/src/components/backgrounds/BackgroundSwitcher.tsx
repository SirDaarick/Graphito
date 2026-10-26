import { useState, useEffect } from "react";
import { Wand2, X } from "lucide-react";
import { BackgroundMode } from "./InteractiveCanvas";

interface BackgroundSwitcherProps {
    currentMode: BackgroundMode;
    onModeChange: (mode: BackgroundMode) => void;
    className?: string;
}

const STORAGE_KEY = "graphito_bg_mode";
const COLLAPSED_STORAGE_KEY = "graphito_bg_switcher_collapsed";

const MODES: { id: BackgroundMode; label: string; icon: string; ariaLabel: string }[] = [
    {
        id: "dotgrid",
        label: "🔮 DotGrid",
        icon: "🔮",
        ariaLabel: "Modo fondo interactivo DotGrid React Bits con físicas elásticas WebGL2",
    },
    {
        id: "dots",
        label: "✨ Nodos",
        icon: "✨",
        ariaLabel: "Modo fondo interactivo de nodos y grafo",
    },
    {
        id: "waves",
        label: "🌊 Ondas",
        icon: "🌊",
        ariaLabel: "Modo fondo interactivo de ondas de seda matemática",
    },
    {
        id: "aurora",
        label: "🌌 Aurora",
        icon: "🌌",
        ariaLabel: "Modo fondo interactivo aurora boreal ambiental",
    },
];

export function BackgroundSwitcher({
    currentMode,
    onModeChange,
    className = "",
}: BackgroundSwitcherProps) {
    const [isExpanded, setIsExpanded] = useState(false);

    // Load collapsed state preference on mount
    useEffect(() => {
        try {
            const savedCollapsed = localStorage.getItem(COLLAPSED_STORAGE_KEY);
            // Default to expanded on larger screens, collapsed if user explicitly minimized it
            if (savedCollapsed !== null) {
                setIsExpanded(savedCollapsed === "false");
            } else {
                // If screen is wide, start expanded for discoverability
                setIsExpanded(window.innerWidth >= 768);
            }
        } catch {
            setIsExpanded(true);
        }
    }, []);

    const handleToggleExpand = () => {
        const nextState = !isExpanded;
        setIsExpanded(nextState);
        try {
            localStorage.setItem(COLLAPSED_STORAGE_KEY, String(!nextState));
        } catch {
            // ignore storage errors
        }
    };

    const handleSelectMode = (mode: BackgroundMode) => {
        onModeChange(mode);
        try {
            localStorage.setItem(STORAGE_KEY, mode);
        } catch {
            // ignore storage errors
        }
    };

    return (
        <aside
            aria-label="Controles de estilo de fondo animado"
            className={`fixed bottom-5 left-5 z-40 select-none print:hidden transition-all duration-300 ease-out ${className}`}
        >
            {!isExpanded ? (
                <button
                    type="button"
                    onClick={handleToggleExpand}
                    aria-label="Personalizar estilo de fondo animado"
                    aria-expanded={false}
                    title="Personalizar fondo animado"
                    className="min-h-[44px] min-w-[44px] p-2.5 rounded-full flex items-center justify-center gap-2 bg-white/80 dark:bg-slate-900/80 backdrop-blur-md border border-slate-200/90 dark:border-slate-800/90 shadow-lg shadow-slate-900/10 dark:shadow-black/40 text-slate-700 dark:text-slate-300 hover:text-blue-600 dark:hover:text-blue-400 hover:border-blue-400/50 dark:hover:border-blue-500/50 hover:shadow-blue-500/10 transition-all duration-200 focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2 dark:focus-visible:ring-offset-slate-900 focus:outline-none group"
                >
                    <Wand2 className="w-5 h-5 transition-transform duration-300 group-hover:rotate-12 text-blue-500" />
                    <span className="text-xs font-semibold pr-1 hidden sm:inline text-slate-600 dark:text-slate-300">
                        Fondo
                    </span>
                </button>
            ) : (
                <div
                    role="toolbar"
                    aria-label="Selector de estilo de fondo"
                    className="flex items-center gap-1 p-1 rounded-full bg-white/90 dark:bg-slate-900/90 backdrop-blur-md border border-slate-200/90 dark:border-slate-800/90 shadow-xl shadow-slate-900/15 dark:shadow-black/50 transition-all duration-200"
                >
                    <button
                        type="button"
                        onClick={handleToggleExpand}
                        aria-label="Minimizar selector de fondo"
                        aria-expanded={true}
                        title="Minimizar controles de fondo"
                        className="min-h-[44px] min-w-[44px] rounded-full flex items-center justify-center text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors focus-visible:ring-2 focus-visible:ring-blue-500 focus:outline-none"
                    >
                        <X className="w-4 h-4" />
                    </button>

                    <div className="flex items-center gap-1">
                        {MODES.map((item) => {
                            const isActive = currentMode === item.id;
                            return (
                                <button
                                    key={item.id}
                                    type="button"
                                    onClick={() => handleSelectMode(item.id)}
                                    aria-pressed={isActive}
                                    aria-label={item.ariaLabel}
                                    className={`min-h-[44px] px-3.5 py-1.5 rounded-full text-xs font-medium transition-all duration-200 flex items-center justify-center gap-1.5 focus-visible:ring-2 focus-visible:ring-blue-500 focus:outline-none ${
                                        isActive
                                            ? "bg-gradient-to-r from-blue-500/15 via-purple-500/15 to-pink-500/15 border border-blue-400/50 text-blue-700 dark:text-blue-300 shadow-sm shadow-blue-500/20 font-semibold"
                                            : "border border-transparent text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white hover:bg-slate-100/80 dark:hover:bg-slate-800/60"
                                    }`}
                                >
                                    <span>{item.label}</span>
                                </button>
                            );
                        })}
                    </div>
                </div>
            )}
        </aside>
    );
}
