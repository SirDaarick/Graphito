import { useState, useEffect, useRef, type MouseEvent as ReactMouseEvent } from "react";
import { createPortal } from "react-dom";
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
import { Button } from "../ui/Button";
import { cn } from "../../lib/utils";
import { getSavedVerdicts, VerdictType } from "../../lib/verdicts";
import { ComparisonView } from "../../lib/dictamen";
import { Grupo } from "../../lib/api";

export interface Comparison extends ComparisonView {
    veredicto?: VerdictType | null;
}

// One neutral color for every score: the color never says whether a value is good or bad (the teacher decides).
const SCORE_COLOR = "text-slate-700 dark:text-slate-200";

interface ReferenceCardProps {
    /** Backend problem id; lets the guided tour point at one specific card. */
    problemId?: number;
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
    /** Guided tour: keep the submissions list open while true (closed again when it turns false). */
    forceExpanded?: boolean;
}

// Colors for language badges: C++ in pink, C in blue (>4.5:1 contrast)
const categoryColors = {
    orange: "bg-amber-500/10 text-amber-700 dark:text-amber-400 border-amber-500/30",
    purple: "bg-pink-500/10 text-pink-600 dark:text-pink-400 border-pink-500/30",
    cyan: "bg-blue-500/10 text-blue-600 dark:text-blue-400 border-blue-500/30",
};

export function ReferenceCard({
    problemId,
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
    forceExpanded = false,
}: ReferenceCardProps) {
    const [isExpanded, setIsExpanded] = useState(forceExpanded);
    const wasForcedRef = useRef(forceExpanded);
    const [isMenuOpen, setIsMenuOpen] = useState(false);
    const [menuPos, setMenuPos] = useState<{ top: number; right: number } | null>(null);
    const menuRef = useRef<HTMLDivElement>(null);
    const menuButtonRef = useRef<HTMLButtonElement>(null);
    const hasActions = Boolean(onAssignToGroup || onToggleArchive || onDelete);

    // The guided tour opens the list while its step is current and closes it when the step ends.
    useEffect(() => {
        if (forceExpanded) setIsExpanded(true);
        else if (wasForcedRef.current) setIsExpanded(false);
        wasForcedRef.current = forceExpanded;
    }, [forceExpanded]);

    useEffect(() => {
        if (!isMenuOpen) return;
        const onDown = (event: MouseEvent) => {
            const target = event.target as Node;
            if (menuRef.current?.contains(target) || menuButtonRef.current?.contains(target)) return;
            setIsMenuOpen(false);
        };
        const onKey = (event: KeyboardEvent) => {
            if (event.key === "Escape") setIsMenuOpen(false);
        };
        const close = () => setIsMenuOpen(false);
        document.addEventListener("mousedown", onDown);
        document.addEventListener("keydown", onKey);
        window.addEventListener("resize", close);
        window.addEventListener("scroll", close, true);
        return () => {
            document.removeEventListener("mousedown", onDown);
            document.removeEventListener("keydown", onKey);
            window.removeEventListener("resize", close);
            window.removeEventListener("scroll", close, true);
        };
    }, [isMenuOpen]);

    const toggleMenu = () => {
        if (!isMenuOpen) {
            const rect = menuButtonRef.current?.getBoundingClientRect();
            if (rect) setMenuPos({ top: rect.bottom + 8, right: window.innerWidth - rect.right });
        }
        setIsMenuOpen((open) => !open);
    };

    // The whole card toggles the submissions list; interactive children keep their own behavior.
    const isOpen = forceExpanded || isExpanded;

    const handleCardClick = (event: ReactMouseEvent<HTMLDivElement>) => {
        if ((event.target as HTMLElement).closest("button, a, input, select, textarea, [role='button'], [role='menu']")) {
            return;
        }
        if (forceExpanded) return;
        setIsExpanded((v) => !v);
    };

    const runAction = (action?: () => void) => {
        setIsMenuOpen(false);
        action?.();
    };

    const [verdicts, setVerdicts] = useState<Record<string, VerdictType>>(() => getSavedVerdicts());

    /** The teacher's own mark: what they just set here wins over what the server returned with the list. */
    const verdictOf = (comparison: Comparison): VerdictType | null => {
        const local = verdicts[String(comparison.id)];
        if (local) return local;
        if (comparison.decision_docente === "APROBADO") return "CONFORME";
        if (comparison.decision_docente === "EN_DUDA") return "DUDA";
        return null;
    };

    useEffect(() => {
        const handleUpdate = () => {
            setVerdicts(getSavedVerdicts());
        };
        window.addEventListener("graphito_verdict_updated", handleUpdate);
        return () => window.removeEventListener("graphito_verdict_updated", handleUpdate);
    }, []);

    return (
        <div
            data-tour="problem-card"
            data-problem-id={problemId}
            className={cn(
                "mb-5 bg-white/25 dark:bg-graphito-card/15 backdrop-blur-[3px] border border-slate-200/60 dark:border-white/15 rounded-2xl transition-all duration-200 hover:shadow-xl hover:shadow-graphito-blue/5 hover:border-graphito-blue/40 dark:hover:border-graphito-blue/40 shadow-sm",
                archived && "opacity-70"
            )}
        >
            <div className="p-6 cursor-pointer" onClick={handleCardClick}>
                {/* Distributed Horizontal Layout across the wide card */}
                <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-6">
                    {/* Left Section: Title, Badges (Language & Groups) and Description */}
                    <div className="space-y-2 flex-1 min-w-0">
                        <h3
                            className="text-lg sm:text-xl font-display font-bold text-slate-900 dark:text-white tracking-tight truncate max-w-md"
                            title={title}
                        >
                            {title}
                        </h3>
                        {/* Badges live on their own row so their position never depends on the title length */}
                        <div className="flex flex-wrap items-center gap-2">
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
                                        className="inline-flex items-center gap-1 px-2.5 py-1 min-h-[32px] rounded-md text-xs font-semibold text-slate-600 dark:text-slate-300 hover:text-graphito-blue focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-graphito-blue hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors border border-dashed border-slate-300 dark:border-slate-700 shrink-0"
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
                        <Button
                            variant="outline"
                            className="text-xs sm:text-sm !py-2.5 !px-5 min-h-[44px] !rounded-xl whitespace-nowrap !text-graphito-blue !border-graphito-blue/50 hover:!bg-graphito-blue/10"
                            onClick={onCompare}
                            data-tour="compare"
                            data-problem-id={problemId}
                            leftIcon={<Plus className="h-4 w-4" aria-hidden="true" />}
                        >
                            Comparar
                        </Button>

                        {hasActions && (
                            <div className="relative">
                                <button
                                    ref={menuButtonRef}
                                    type="button"
                                    onClick={toggleMenu}
                                    className="p-2.5 min-w-[42px] min-h-[42px] flex items-center justify-center bg-slate-100 hover:bg-slate-200 dark:bg-graphito-dark dark:hover:bg-graphito-subtle text-slate-600 dark:text-slate-300 rounded-xl transition-all duration-200 focus-visible:ring-2 focus-visible:ring-graphito-blue focus-visible:outline-none active:scale-95"
                                    aria-label="Más opciones"
                                    aria-haspopup="menu"
                                    aria-expanded={isMenuOpen}
                                >
                                    <MoreVertical className="h-4 w-4" />
                                </button>
                                {isMenuOpen && menuPos && createPortal(
                                    <div
                                        ref={menuRef}
                                        role="menu"
                                        style={{ position: "fixed", top: menuPos.top, right: menuPos.right }}
                                        className="z-[200] w-56 rounded-xl bg-white dark:bg-graphito-card backdrop-blur-xl border border-slate-200/80 dark:border-white/[0.08] shadow-2xl p-1.5"
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
                                    </div>,
                                    document.body
                                )}
                            </div>
                        )}

                        <button
                            onClick={() => {
                                if (forceExpanded) return;
                                setIsExpanded(!isExpanded);
                            }}
                            className="p-2.5 min-w-[42px] min-h-[42px] flex items-center justify-center bg-slate-100 hover:bg-slate-200 dark:bg-graphito-dark dark:hover:bg-graphito-subtle text-slate-600 dark:text-slate-300 rounded-xl transition-all duration-200 focus-visible:ring-2 focus-visible:ring-graphito-blue focus-visible:outline-none active:scale-95"
                            aria-label={isOpen ? "Colapsar entregas" : "Expandir entregas"}
                            aria-expanded={isOpen}
                        >
                            <ChevronDown
                                className={cn(
                                    "h-4 w-4 transition-transform duration-300 ease-[cubic-bezier(0.16,1,0.3,1)]",
                                    isOpen && "rotate-180"
                                )}
                            />
                        </button>
                    </div>
                </div>

                {/* Submissions Section (Accordion) */}
                <div
                    className={cn(
                        "grid transition-all duration-300 ease-[cubic-bezier(0.16,1,0.3,1)]",
                        isOpen ? "grid-rows-[1fr] opacity-100" : "grid-rows-[0fr] opacity-0"
                    )}
                >
                    <div className="overflow-hidden">
                        {comparisons.length > 0 && (
                            <div
                                data-tour="problem-submissions"
                                data-problem-id={problemId}
                                className={cn(
                                    "border-t border-slate-200 dark:border-graphito-border transition-all duration-300",
                                    isOpen ? "mt-5 pt-5" : "mt-0 pt-0 pb-0 border-transparent"
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
                                        const verdict = verdictOf(comparison);
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
                                                className={cn(
                                                    "flex items-center justify-between p-3 px-4 backdrop-blur-[2px] border rounded-xl transition-all duration-150 cursor-pointer group shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-graphito-blue",
                                                    verdict === "CONFORME"
                                                        ? "bg-emerald-500/10 hover:bg-emerald-500/20 border-emerald-500/40 hover:border-emerald-500/60"
                                                        : verdict === "DUDA"
                                                        ? "bg-amber-500/10 hover:bg-amber-500/20 border-amber-500/40 hover:border-amber-500/60"
                                                        : "bg-white/40 hover:bg-white/90 dark:bg-graphito-dark/30 dark:hover:bg-graphito-dark/60 border-slate-200/80 dark:border-white/[0.06] hover:border-graphito-blue/40"
                                                )}
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
                                                    {verdict && (
                                                        <span
                                                            className={cn(
                                                                "px-2 py-0.5 rounded-md text-xs font-bold border",
                                                                verdict === "CONFORME"
                                                                    ? "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300 border-emerald-500/40"
                                                                    : "bg-amber-500/15 text-amber-700 dark:text-amber-300 border-amber-500/40"
                                                            )}
                                                        >
                                                            {verdict === "CONFORME" ? "Revisado" : "Por aclarar"}
                                                        </span>
                                                    )}
                                                    {comparison.engine === "stub" && (
                                                        <span className="px-1.5 py-0.5 rounded text-[9px] font-bold font-mono bg-amber-500/15 text-amber-700 dark:text-amber-400 border border-amber-500/30">
                                                            STUB
                                                        </span>
                                                    )}
                                                    <div className="flex items-baseline gap-1.5">
                                                        <span className="sr-only sm:not-sr-only text-[10px] font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                                                            Similitud lógica
                                                        </span>
                                                        <span className={cn("text-sm font-black font-mono", SCORE_COLOR)}>
                                                            {comparison.similarity == null
                                                                ? "—"
                                                                : `${comparison.similarity}%`}
                                                        </span>
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
