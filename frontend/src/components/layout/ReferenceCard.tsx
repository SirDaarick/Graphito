import { useState, useEffect, useRef } from "react"
import { Calendar, GitCompare, ChevronDown, Plus, ShieldCheck, HelpCircle, MoreVertical, Users, Archive, ArchiveRestore, Trash2 } from "lucide-react"
import { GradientButton } from "../ui/GradientButton"
import { cn } from "../../lib/utils";
import { getSavedVerdicts, VerdictType } from "../../lib/verdicts";
import { ComparisonView, describeDictamen } from "../../lib/dictamen";

export interface Comparison extends ComparisonView {
    veredicto?: VerdictType | null
}

// Color from the backend verdict (calibrated flags), never from fixed score cut-offs.
function scoreColor(comparison: Comparison): string {
    const verdict = describeDictamen(comparison.dictamen, comparison.estado)
    if (verdict.flagged) return "text-risk-high"
    if (verdict.tone === "clear") return "text-risk-low"
    return "text-slate-400"
}

interface ReferenceCardProps {
    title: string
    category: string
    categoryColor: "orange" | "purple" | "cyan"
    description: string
    updatedAt: string
    activeComparisons: number
    comparisons: Comparison[]
    onCompare?: () => void
    onComparisonClick?: (comparison: Comparison, allComparisons?: Comparison[]) => void
    archived?: boolean
    onAssignToGroup?: () => void
    onToggleArchive?: () => void
    onDelete?: () => void
}

// Mapeamos los colores de categoría a tu paleta
const categoryColors = {
    orange: "bg-risk-medium/10 text-risk-medium border-risk-medium/20",
    purple: "bg-graphito-violet/10 text-graphito-violet border-graphito-violet/20",
    cyan: "bg-graphito-blue/10 text-graphito-blue border-graphito-blue/20",
}

export function ReferenceCard({
    title,
    category,
    categoryColor,
    description,
    updatedAt,
    activeComparisons,
    comparisons,
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
    const [verdicts, setVerdicts] = useState<Record<string, VerdictType>>(() => getSavedVerdicts());

    useEffect(() => {
        const handleUpdate = () => {
            setVerdicts(getSavedVerdicts());
        };
        window.addEventListener("graphito_verdict_updated", handleUpdate);
        return () => window.removeEventListener("graphito_verdict_updated", handleUpdate);
    }, []);

    return (
        <div className={cn(
            "mb-6 bg-white dark:bg-graphito-card border border-slate-200 dark:border-graphito-border rounded-2xl transition-all hover:shadow-lg hover:shadow-graphito-blue/5",
            archived && "opacity-70"
        )}>
            <div className="p-6">
                <div className="flex items-start justify-between gap-4">
                    <div className="flex-1 space-y-3">
                        <div className="flex items-center gap-3">
                            <h3 className="text-xl font-display font-bold text-slate-900 dark:text-white tracking-tight">{title}</h3>
                            <span className={cn(
                                "px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-widest border",
                                categoryColors[categoryColor]
                            )}>
                                {category}
                            </span>
                            {archived && (
                                <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-widest border bg-slate-500/10 text-slate-500 dark:text-slate-400 border-slate-500/30">
                                    Archivado
                                </span>
                            )}
                        </div>
                        <p className="font-body text-sm text-slate-600 dark:text-slate-400 leading-relaxed max-w-2xl">
                            {description}
                        </p>
                        <div className="flex items-center gap-4 font-body text-xs text-slate-500 dark:text-slate-400">
                            <span className="flex items-center gap-1.5">
                                <Calendar className="h-3.5 w-3.5" />
                                Actualizado: {updatedAt}
                            </span>
                            <span className="flex items-center gap-1.5 text-graphito-blue font-semibold">
                                <GitCompare className="h-3.5 w-3.5" />
                                {activeComparisons} Comparaciones activas
                            </span>
                        </div>
                    </div>

                    <div className="flex items-center gap-3">
                        {/* Usamos tu GradientButton aquí */}
                        <GradientButton className="text-sm py-2 px-4" onClick={onCompare}>
                            <Plus className="h-4 w-4" />
                            <span>Comparar</span>
                        </GradientButton>

                        {hasActions && (
                            <div className="relative" ref={menuRef}>
                                <button
                                    type="button"
                                    onClick={() => setIsMenuOpen(!isMenuOpen)}
                                    className="p-2.5 min-w-11 min-h-11 bg-slate-100 hover:bg-slate-200 dark:bg-graphito-dark dark:hover:bg-graphito-border text-slate-600 dark:text-slate-400 rounded-xl transition-all duration-300 focus-visible:ring-2 focus-visible:ring-graphito-blue/50 focus-visible:outline-none"
                                    aria-label="Más acciones"
                                    aria-haspopup="menu"
                                    aria-expanded={isMenuOpen}
                                >
                                    <MoreVertical className="h-5 w-5" />
                                </button>
                                {isMenuOpen && (
                                    <div
                                        role="menu"
                                        className="absolute right-0 z-30 mt-2 w-56 rounded-xl bg-white dark:bg-graphito-card border border-slate-200 dark:border-graphito-border shadow-xl p-1.5"
                                    >
                                        {onAssignToGroup && !archived && (
                                            <button
                                                type="button"
                                                role="menuitem"
                                                onClick={() => runAction(onAssignToGroup)}
                                                className="w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm font-semibold text-slate-700 dark:text-slate-200 hover:bg-slate-100 dark:hover:bg-graphito-dark transition-colors text-left"
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
                                                className="w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm font-semibold text-slate-700 dark:text-slate-200 hover:bg-slate-100 dark:hover:bg-graphito-dark transition-colors text-left"
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
                                                className="w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm font-semibold text-red-600 dark:text-red-400 hover:bg-red-500/10 transition-colors text-left"
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
                            className="p-2.5 min-w-11 min-h-11 bg-slate-100 hover:bg-slate-200 dark:bg-graphito-dark dark:hover:bg-graphito-border text-slate-600 dark:text-slate-400 rounded-xl transition-all duration-300 focus-visible:ring-2 focus-visible:ring-graphito-blue/50 focus-visible:outline-none"
                            aria-label={isExpanded ? "Colapsar comparaciones" : "Expandir comparaciones"}
                            aria-expanded={isExpanded}
                        >
                            <ChevronDown
                                className={cn(
                                    "h-5 w-5 transition-transform duration-400 ease-[cubic-bezier(0.16,1,0.3,1)]",
                                    isExpanded && "rotate-180"
                                )}
                            />
                        </button>
                    </div>
                </div>

                {/* Sección de Comparaciones (Acordeón con animación suave) */}
                <div
                    className={cn(
                        "grid transition-all duration-400 ease-[cubic-bezier(0.16,1,0.3,1)]",
                        isExpanded ? "grid-rows-[1fr] opacity-100" : "grid-rows-[0fr] opacity-0"
                    )}
                >
                    <div className="overflow-hidden">
                        {comparisons.length > 0 && (
                            <div className={cn(
                                "border-t border-slate-200 dark:border-graphito-border transition-all duration-300",
                                isExpanded ? "mt-6 pt-6" : "mt-0 pt-0 pb-0 border-transparent"
                            )}>
                                <h4 className="text-[10px] font-bold text-slate-400 dark:text-slate-500 uppercase tracking-[0.2em] mb-4">
                                    Entregas y Análisis Recientes
                                </h4>
                                <div className="space-y-3">
                                    {comparisons.map((comparison) => {
                                        const v = verdicts[String(comparison.id)] || comparison.veredicto;
                                        return (
                                            <div
                                                key={comparison.id}
                                                onClick={() => onComparisonClick?.(comparison, comparisons)}
                                                className={cn(
                                                    "flex items-center justify-between p-4 bg-slate-50 hover:bg-slate-100 dark:bg-graphito-dark/50 border rounded-xl hover:border-graphito-blue/30 transition-all duration-200 cursor-pointer group shadow-sm",
                                                    v === "CONFORME"
                                                        ? "border-l-4 border-l-emerald-500 border-slate-200 dark:border-graphito-border bg-emerald-500/[0.02]"
                                                        : v === "DUDA"
                                                        ? "border-l-4 border-l-amber-500 border-slate-200 dark:border-graphito-border bg-amber-500/[0.02]"
                                                        : "border-slate-200 dark:border-graphito-border"
                                                )}
                                            >
                                                <div className="flex flex-col">
                                                    <div className="flex items-center gap-2">
                                                        <span className="text-sm font-semibold text-slate-800 dark:text-slate-200 group-hover:text-graphito-blue dark:group-hover:text-white transition-colors">
                                                            {comparison.title}
                                                        </span>
                                                        {v === "CONFORME" && (
                                                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border border-emerald-500/30 shrink-0 font-sans">
                                                                <ShieldCheck size={11} /> Conforme
                                                            </span>
                                                        )}
                                                        {v === "DUDA" && (
                                                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-500/15 text-amber-600 dark:text-amber-400 border border-amber-500/30 shrink-0 font-sans">
                                                                <HelpCircle size={11} /> Duda
                                                            </span>
                                                        )}
                                                    </div>
                                                    <span className="text-xs text-slate-500 mt-0.5">{comparison.subtitle}</span>
                                                </div>

                                                <div className="flex items-center gap-4">
                                                    {comparison.engine === "stub" && (
                                                        <span className="px-1.5 py-0.5 rounded text-[9px] font-bold font-mono bg-amber-500/15 text-amber-600 dark:text-amber-400 border border-amber-500/30">
                                                            STUB
                                                        </span>
                                                    )}
                                                    <div
                                                        className={cn("text-sm font-black font-mono", scoreColor(comparison))}
                                                        title="Canal A: Jaccard léxico, 5 tokens (similitud bruta)"
                                                    >
                                                        {comparison.similarity == null ? "—" : `${comparison.similarity}%`}
                                                    </div>
                                                    <ChevronDown className="h-4 w-4 text-slate-400 dark:text-slate-600 -rotate-90 group-hover:translate-x-0.5 transition-transform" />
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
    )
}