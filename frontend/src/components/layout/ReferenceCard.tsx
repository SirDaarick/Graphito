import { useState } from "react"
import { Calendar, GitCompare, ChevronDown, Plus } from "lucide-react"
import { GradientButton } from "../ui/GradientButton"
import { cn } from "../../lib/utils";

interface Comparison {
    id: string
    title: string
    subtitle: string
    similarity: number
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
    onComparisonClick?: (comparison: Comparison) => void
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
}: ReferenceCardProps) {
    const [isExpanded, setIsExpanded] = useState(false)

    return (
        <div className="mb-6 bg-graphito-card border border-graphito-border rounded-2xl overflow-hidden transition-all hover:shadow-lg hover:shadow-graphito-blue/5">
            <div className="p-6">
                <div className="flex items-start justify-between gap-4">
                    <div className="flex-1 space-y-3">
                        <div className="flex items-center gap-3">
                            <h3 className="text-xl font-display font-bold text-white tracking-tight">{title}</h3>
                            <span className={cn(
                                "px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-widest border",
                                categoryColors[categoryColor]
                            )}>
                                {category}
                            </span>
                        </div>
                        <p className="font-body text-sm text-slate-400 leading-relaxed max-w-2xl">
                            {description}
                        </p>
                        <div className="flex items-center gap-4 font-body text-xs text-slate-500">
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

                        <button
                            onClick={() => setIsExpanded(!isExpanded)}
                            className="p-2 bg-graphito-dark hover:bg-graphito-border text-slate-400 rounded-xl transition-all"
                        >
                            <ChevronDown
                                className={cn(
                                    "h-5 w-5 transition-transform duration-300",
                                    isExpanded && "rotate-180"
                                )}
                            />
                        </button>
                    </div>
                </div>

                {/* Sección de Comparaciones (Acordeón) */}
                <div
                    className={cn(
                        "grid transition-all duration-300 ease-in-out",
                        isExpanded ? "grid-rows-[1fr] opacity-100" : "grid-rows-[0fr] opacity-0"
                    )}
                >
                    <div className="overflow-hidden">
                        {comparisons.length > 0 && (
                            <div className={cn(
                                "border-t border-graphito-border transition-all duration-300",
                                isExpanded ? "mt-6 pt-6" : "mt-0 pt-0 pb-0 border-transparent"
                            )}>
                                <h4 className="text-[10px] font-bold text-slate-500 uppercase tracking-[0.2em] mb-4">
                                    Análisis Recientes
                                </h4>
                                <div className="space-y-3">
                                    {comparisons.map((comparison) => (
                                        <div
                                            key={comparison.id}
                                            onClick={() => onComparisonClick?.(comparison)}
                                            className="flex items-center justify-between p-4 bg-graphito-dark/50 border border-graphito-border rounded-xl hover:border-graphito-blue/30 transition-colors cursor-pointer group"
                                        >
                                            <div className="flex flex-col">
                                                <span className="text-sm font-semibold text-slate-200 group-hover:text-white transition-colors">
                                                    {comparison.title}
                                                </span>
                                                <span className="text-xs text-slate-500">{comparison.subtitle}</span>
                                            </div>

                                            <div className="flex items-center gap-4">
                                                {/* Aquí aplicamos la lógica de colores de riesgo que definiste */}
                                                <div className={cn(
                                                    "text-sm font-black font-mono",
                                                    comparison.similarity > 70 ? "text-risk-high" :
                                                        comparison.similarity > 30 ? "text-risk-medium" : "text-risk-low"
                                                )}>
                                                    {comparison.similarity}%
                                                </div>
                                                <ChevronDown className="h-4 w-4 text-slate-600 -rotate-90" />
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}
                    </div>
                </div>
            </div>
        </div>
    )
}