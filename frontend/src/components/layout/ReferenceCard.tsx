import { useState, useEffect, useRef } from "react";
import {
    Calendar,
    GitCompare,
    ChevronDown,
    Plus,
    MoreVertical,
    Users,
    Archive,
    ArchiveRestore,
    Trash2,
} from "lucide-react";
import { GradientButton } from "../ui/GradientButton";
import { cn } from "../../lib/utils";
import { getSavedVerdicts, VerdictType } from "../../lib/verdicts";
import { ComparisonView, describeDictamen } from "../../lib/dictamen";
import { Grupo } from "../../lib/api";

export interface Comparison extends ComparisonView {
    veredicto?: VerdictType | null;
}

// Color from the backend verdict (calibrated flags), never from fixed score cut-offs.
function scoreColor(comparison: Comparison): string {
    const verdict = describeDictamen(comparison.dictamen, comparison.estado);
    if (verdict.flagged) return "text-risk-high";
    if (verdict.tone === "clear") return "text-risk-low";
    return "text-slate-400 dark:text-slate-400";
}

interface ReferenceCardProps {
    title: string;
    category: string;
    categoryColor: "orange" | "purple" | "cyan";
    description: string;
    updatedAt: string;
    activeComparisons: number;
    comparisons: Comparison[];
    assignedGroups?: Grupo[];
    onCompare?: () => void;
    onComparisonClick?: (comparison: Comparison, allComparisons?: Comparison[]) => void;
    archived?: boolean;
    onAssignToGroup?: () => void;
    onToggleArchive?: () => void;
    onDelete?: () => void;
}

// Colors for language badges: C++ in pink, C in blue (>4.5:1 contrast)
const categoryColors = {
    orange: "bg-amber-500/10 text-amber-700 dark:text-amber-400 border-amber-500/30",
    purple: "bg-pink-500/10 text-pink-600 dark:text-pink-400 border-pink-500/30",
    cyan: "bg-blue-500/10 text-blue-600 dark:text-blue-400 border-blue-500/30",
};

export function ReferenceCard({
    title,
    category,
    categoryColor,
    description,
    updatedAt,
    activeComparisons,
    comparisons,
    assignedGroups = [],
    onCompare,
    onComparisonClick,
    archived = false,
    onAssignToGroup,
    onToggleArchive,
    onDelete,
}: ReferenceCardProps) {
    const [isExpanded, setIsExpanded] = useState(false);
    const [isMenuOpen, setIsMenuOpen] = useState(false);
    const menuRef = useRef<HTMLDivElement>(null);
    const hasActions = Boolean(onAssignToGroup || onToggleArchive || onDelete);

    useEffect(() => {
        if (!isMenuOpen) return;
        const onDown = (event: MouseEvent) => {
            if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
                setIsMenuOpen(false);
            }
        };
        const onKey = (event: KeyboardEvent) => {
            if (event.key === "Escape") setIsMenuOpen(false);
        };
        document.addEventListener("mousedown", onDown);
        document.addEventListener("keydown", onKey);
        return () => {
            document.removeEventListener("mousedown", onDown);
            document.removeEventListener("keydown", onKey);
        };
    }, [isMenuOpen]);

    const runAction = (action?: () => void) => {
        setIsMenuOpen(false);
        action?.();
    };

    const [, setVerdicts] = useState<Record<string, VerdictType>>(() => getSavedVerdicts());

    useEffect(() => {
        const handleUpdate = () => {
            setVerdicts(getSavedVerdicts());
        };
        window.addEventListener("graphito_verdict_updated", handleUpdate);
        return () => window.removeEventListener("graphito_verdict_updated", handleUpdate);
    }, []);

    return (
        <div
            className={cn(
                "mb-5 bg-white/25 dark:bg-graphito-card/15 backdrop-blur-[3px] border border-slate-200/60 dark:border-white/15 rounded-2xl transition-all duration-200 hover:shadow-xl hover:shadow-graphito-blue/5 hover:border-graphito-blue/40 dark:hover:border-graphito-blue/40 shadow-sm",
                archived && "opacity-70"
            )}
        >
            <div className="p-6">
                {/* Distributed Horizontal Layout across the wide card */}
                <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-6">
                    {/* Left Section: Title, Badges (Language & Groups) and Description */}
                    <div className="space-y-2 flex-1 min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                            <h3 className="text-lg sm:text-xl font-display font-bold text-slate-900 dark:text-white tracking-tight truncate max-w-md">
                                {title}
                            </h3>
                            <span
                                className={cn(
                                    "px-2.5 py-0.5 rounded-md text-[10px] font-black uppercase tracking-wider border shrink-0",
                                    categoryColors[categoryColor]
                                )}
                            >
                                {category}
                            </span>

                            {/* Group Badges */}
                            {assignedGroups.length > 0 ? (
                                assignedGroups.map((g) => (
                                    <span
                                        key={g.id}
                                        className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-md text-[10px] font-bold bg-graphito-blue/10 text-graphito-blue dark:text-cyan-300 border border-graphito-blue/25 shrink-0"
                                        title={`Grupo: ${g.nombre} (${g.periodo})`}
                                    >
                                        <Users size={11} />
                                        <span>{g.codigo_grupo}</span>
                                    </span>
                                ))
                            ) : (
                                onAssignToGroup &&
                                !archived && (
                                    <button
                                        type="button"
                                        onClick={(e) => {
                                            e.stopPropagation();
                                            onAssignToGroup();
                                        }}
                                        className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] font-semibold text-slate-500 dark:text-slate-400 hover:text-graphito-blue hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors border border-dashed border-slate-300 dark:border-slate-700 shrink-0"
                                        title="Asignar este problema a un grupo académico"
                                    >
                                        <Plus size={10} />
                                        <span>Asignar grupo</span>
                                    </button>
                                )
                            )}

                            {archived && (
                                <span className="px-2 py-0.5 rounded-md text-[10px] font-bold uppercase tracking-widest border bg-slate-500/10 text-slate-600 dark:text-slate-400 border-slate-500/30 shrink-0">
                                    Archivado
                                </span>
                            )}
                        </div>

                        <p className="font-body text-xs sm:text-sm text-slate-600 dark:text-slate-300 leading-relaxed line-clamp-2 max-w-2xl">
                            {description}
                        </p>
                    </div>

                    {/* Middle Section: Distributed Stats Capsule */}
                    <div className="flex items-center gap-4 sm:gap-6 py-2 px-4 rounded-xl bg-slate-100/60 dark:bg-black/20 border border-slate-200/60 dark:border-white/5 shrink-0 self-start lg:self-center">
                        <div className="text-center">
                            <span className="text-[10px] uppercase font-bold tracking-widest text-slate-500 dark:text-slate-400 block">
                                Entregas
                            </span>
                            <div className="flex items-center justify-center gap-1 font-mono text-sm font-black text-graphito-blue">
                                <GitCompare size={13} />
                                <span>{activeComparisons}</span>
                            </div>
                        </div>

                        <div className="w-[1px] h-6 bg-slate-200 dark:bg-white/10" />

                        <div className="text-center">
                            <span className="text-[10px] uppercase font-bold tracking-widest text-slate-500 dark:text-slate-400 block">
                                Creado
                            </span>
                            <div className="flex items-center justify-center gap-1 font-body text-xs font-semibold text-slate-700 dark:text-slate-300">
                                <Calendar size={13} />
                                <span>{updatedAt}</span>
                            </div>
                        </div>
                    </div>

                    {/* Right Section: Action Controls */}
                    <div className="flex items-center gap-2.5 shrink-0 self-end lg:self-center">
                        <GradientButton
                            className="text-xs sm:text-sm !py-2.5 !px-5 min-h-[42px] !rounded-xl shadow-sm"
                            onClick={onCompare}
                        >
                            <Plus className="h-4 w-4" />
                            <span>Comparar</span>
                        </GradientButton>

                        {hasActions && (
                            <div className="relative" ref={menuRef}>
                                <button
                                    type="button"
                                    onClick={() => setIsMenuOpen(!isMenuOpen)}
                                    className="p-2.5 min-w-[42px] min-h-[42px] flex items-center justify-center bg-slate-100 hover:bg-slate-200 dark:bg-graphito-dark dark:hover:bg-graphito-subtle text-slate-600 dark:text-slate-300 rounded-xl transition-all duration-200 focus-visible:ring-2 focus-visible:ring-graphito-blue focus-visible:outline-none active:scale-95"
                                    aria-label="Más opciones"
                                    aria-haspopup="menu"
                                    aria-expanded={isMenuOpen}
                                >
                                    <MoreVertical className="h-4 w-4" />
                                </button>
                                {isMenuOpen && (
                                    <div
                                        role="menu"
                                        className="absolute right-0 z-30 mt-2 w-56 rounded-xl bg-white/95 dark:bg-graphito-card/95 backdrop-blur-xl border border-slate-200/80 dark:border-white/[0.08] shadow-2xl p-1.5"
                                    >
                                        {onAssignToGroup && !archived && (
                                            <button
                                                type="button"
                                                role="menuitem"
                                                onClick={() => runAction(onAssignToGroup)}
                                                className="w-full flex items-center gap-2.5 px-3 py-2.5 min-h-[40px] rounded-lg text-xs font-semibold text-slate-700 dark:text-slate-200 hover:bg-slate-100 dark:hover:bg-graphito-dark transition-colors text-left"
                                            >
                                                <Users className="h-4 w-4 text-graphito-blue" />
                                                Asignar a grupo
                                            </button>
                                        )}
                                        {onToggleArchive && (
                                            <button
                                                type="button"
                                                role="menuitem"
                                                onClick={() => runAction(onToggleArchive)}
                                                className="w-full flex items-center gap-2.5 px-3 py-2.5 min-h-[40px] rounded-lg text-xs font-semibold text-slate-700 dark:text-slate-200 hover:bg-slate-100 dark:hover:bg-graphito-dark transition-colors text-left"
                                            >
                                                {archived ? (
                                                    <ArchiveRestore className="h-4 w-4 text-graphito-violet" />
                                                ) : (
                                                    <Archive className="h-4 w-4 text-graphito-violet" />
                                                )}
                                                {archived ? "Desarchivar" : "Archivar"}
                                            </button>
                                        )}
                                        {onDelete && (
                                            <button
                                                type="button"
                                                role="menuitem"
                                                onClick={() => runAction(onDelete)}
                                                className="w-full flex items-center gap-2.5 px-3 py-2.5 min-h-[40px] rounded-lg text-xs font-semibold text-red-600 dark:text-red-400 hover:bg-red-500/10 transition-colors text-left"
                                            >
                                                <Trash2 className="h-4 w-4" />
                                                Eliminar
                                            </button>
                                        )}
                                    </div>
                                )}
                            </div>
                        )}

                        <button
                            onClick={() => setIsExpanded(!isExpanded)}
                            className="p-2.5 min-w-[42px] min-h-[42px] flex items-center justify-center bg-slate-100 hover:bg-slate-200 dark:bg-graphito-dark dark:hover:bg-graphito-subtle text-slate-600 dark:text-slate-300 rounded-xl transition-all duration-200 focus-visible:ring-2 focus-visible:ring-graphito-blue focus-visible:outline-none active:scale-95"
                            aria-label={isExpanded ? "Colapsar entregas" : "Expandir entregas"}
                            aria-expanded={isExpanded}
                        >
                            <ChevronDown
                                className={cn(
                                    "h-4 w-4 transition-transform duration-300 ease-[cubic-bezier(0.16,1,0.3,1)]",
                                    isExpanded && "rotate-180"
                                )}
                            />
                        </button>
                    </div>
                </div>

                {/* Submissions Section (Accordion) */}
                <div
                    className={cn(
                        "grid transition-all duration-300 ease-[cubic-bezier(0.16,1,0.3,1)]",
                        isExpanded ? "grid-rows-[1fr] opacity-100" : "grid-rows-[0fr] opacity-0"
                    )}
                >
                    <div className="overflow-hidden">
                        {comparisons.length > 0 && (
                            <div
                                className={cn(
                                    "border-t border-slate-200 dark:border-graphito-border transition-all duration-300",
                                    isExpanded ? "mt-5 pt-5" : "mt-0 pt-0 pb-0 border-transparent"
                                )}
                            >
                                <div className="flex items-center justify-between mb-3">
                                    <h4 className="text-[10px] font-bold text-slate-500 dark:text-slate-400 uppercase tracking-widest">
                                        Entregas registradas ({comparisons.length})
                                    </h4>
                                    <span className="text-[10px] text-slate-400">
                                        Selecciona una entrega para ver el análisis detallado
                                    </span>
                                </div>

                                <div className="space-y-2">
                                    {comparisons.map((comparison, idx) => {
                                        return (
                                            <div
                                                key={comparison.id}
                                                role="button"
                                                tabIndex={0}
                                                onClick={() => onComparisonClick?.(comparison, comparisons)}
                                                onKeyDown={(e) => {
                                                    if (e.key === "Enter" || e.key === " ") {
                                                        e.preventDefault();
                                                        onComparisonClick?.(comparison, comparisons);
                                                    }
                                                }}
                                                className="flex items-center justify-between p-3 px-4 bg-white/40 hover:bg-white/90 dark:bg-graphito-dark/30 dark:hover:bg-graphito-dark/60 backdrop-blur-[2px] border border-slate-200/80 dark:border-white/[0.06] rounded-xl hover:border-graphito-blue/40 transition-all duration-150 cursor-pointer group shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-graphito-blue"
                                            >
                                                {/* Left: Index badge & Student Name */}
                                                <div className="flex items-center gap-3 min-w-0">
                                                    <span className="w-7 h-7 rounded-lg bg-slate-100 dark:bg-black/30 border border-slate-200 dark:border-white/5 text-slate-500 dark:text-slate-400 flex items-center justify-center text-[11px] font-mono font-bold shrink-0">
                                                        #{idx + 1}
                                                    </span>
                                                    <span className="text-sm font-semibold text-slate-800 dark:text-slate-200 group-hover:text-graphito-blue dark:group-hover:text-white transition-colors truncate">
                                                        {comparison.title}
                                                    </span>
                                                </div>

                                                {/* Right: Similarity Score & Chevron */}
                                                <div className="flex items-center gap-3 shrink-0">
                                                    {comparison.engine === "stub" && (
                                                        <span className="px-1.5 py-0.5 rounded text-[9px] font-bold font-mono bg-amber-500/15 text-amber-700 dark:text-amber-400 border border-amber-500/30">
                                                            STUB
                                                        </span>
                                                    )}
                                                    <div
                                                        className={cn(
                                                            "text-sm font-black font-mono",
                                                            scoreColor(comparison)
                                                        )}
                                                    >
                                                        {comparison.similarity == null
                                                            ? "—"
                                                            : `${comparison.similarity}%`}
                                                    </div>
                                                    <ChevronDown className="h-4 w-4 text-slate-400 dark:text-slate-500 -rotate-90 group-hover:translate-x-0.5 transition-transform" />
                                                </div>
                                            </div>
                                        );
                                    })}
                                </div>
                            </div>
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
}
