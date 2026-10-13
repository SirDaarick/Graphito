import { AlertTriangle, Cpu, FileCode2, Sparkles, Binary, ArrowRight, CheckCircle } from "lucide-react";
import { IndicadorIntegridad } from "../../lib/api";
import { formatFlag, formatNumber, lookupLabel } from "../../lib/dictamen";
import { channelText, indicatorBadge, isHeuristic } from "../../lib/evidence";

interface EvidenceDrawerProps {
    /** Channel A raw Jaccard as a whole percentage; null when not evaluated. */
    semanticPct: number | null;
    /** Channel B calibrated CharCNN as a whole percentage; null when not evaluated or abstained. */
    aiPct: number | null;
    flagA?: boolean | null;
    flagB?: boolean | null;
    estadoCanalA?: string | null;
    estadoCanalB?: string | null;
    umbralA?: number | null;
    umbralB?: number | null;
    indicadores: IndicadorIntegridad[];
    codeMetrics?: {
        total_lineas: number;
        lineas_codigo: number;
        lineas_comentarios: number;
        densidad_comentarios: string;
        complejidad_ciclomatica: number;
    };
    onNavigateToLine?: (lineNumber: number) => void;
}

const SEVERITY_BADGES: Record<string, string> = {
    CRITICA: "bg-rose-500/15 text-rose-400 border-rose-500/30",
    ALTA: "bg-amber-500/15 text-amber-400 border-amber-500/30",
    MEDIA: "bg-yellow-500/15 text-yellow-300 border-yellow-500/30",
};

const DEFAULT_SEVERITY_BADGE = "bg-cyan-500/15 text-cyan-400 border-cyan-500/30";

export function EvidenceDrawer({
    semanticPct,
    aiPct,
    flagA,
    flagB,
    estadoCanalA,
    estadoCanalB,
    umbralA,
    umbralB,
    indicadores,
    codeMetrics,
    onNavigateToLine,
}: EvidenceDrawerProps) {
    return (
        <div className="space-y-6 p-6 rounded-2xl bg-surface border border-line-subtle shadow-xl">
            {/* Encabezado con título e indicación pedagógica */}
            <div className="flex items-center justify-between pb-3 border-b border-line-subtle">
                <div className="flex items-center gap-2.5">
                    <div className="w-8 h-8 rounded-lg bg-cyan-500/10 border border-cyan-500/20 flex items-center justify-center text-cyan-400">
                        <Sparkles size={18} />
                    </div>
                    <div>
                        <h3 className="text-sm font-bold text-content-primary flex items-center gap-2">
                            Desglose de Evidencias Técnicas (XAI)
                            <span className="text-[10px] font-mono uppercase px-2 py-0.5 rounded-full bg-cyan-500/10 text-cyan-400 border border-cyan-500/30">
                                Banderas + Heurísticas
                            </span>
                        </h3>
                        <p className="text-[11px] text-content-secondary">
                            Las filas de decisión vienen de las banderas calibradas; las reglas por línea son heurísticas (no son salida del modelo).
                        </p>
                    </div>
                </div>
            </div>

            {/* Pilares de evaluación: el texto sigue a las banderas, no a cortes fijos */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                <div className="p-3.5 rounded-xl bg-surface-elevated/70 border border-line-subtle space-y-1.5">
                    <div className="flex items-center justify-between">
                        <span className="text-[11px] font-mono uppercase text-content-muted flex items-center gap-1.5">
                            <Cpu size={13} className="text-purple-400" />
                            Canal A · Jaccard léxico
                        </span>
                        <span className="text-sm font-bold text-purple-400">{semanticPct === null ? "—" : `${semanticPct}%`}</span>
                    </div>
                    <p className="text-[11px] text-content-secondary leading-relaxed">
                        {channelText({
                            score: semanticPct,
                            flag: flagA,
                            estado: estadoCanalA,
                            onFlag: "Similitud léxica con la referencia sobre el umbral calibrado.",
                            onClear: "Similitud léxica bajo el umbral calibrado.",
                        })}{" "}
                        Umbral {formatNumber(umbralA)} · Bandera {formatFlag(flagA)}
                    </p>
                </div>

                <div className="p-3.5 rounded-xl bg-surface-elevated/70 border border-line-subtle space-y-1.5">
                    <div className="flex items-center justify-between">
                        <span className="text-[11px] font-mono uppercase text-content-muted flex items-center gap-1.5">
                            <FileCode2 size={13} className="text-emerald-400" />
                            Canal B · CharCNN v2
                        </span>
                        <span className="text-sm font-bold text-emerald-400">
                            {estadoCanalB === "ABSTENIDO" ? "Abstenido" : aiPct === null ? "—" : `${aiPct}%`}
                        </span>
                    </div>
                    <p className="text-[11px] text-content-secondary leading-relaxed">
                        {estadoCanalB === "ABSTENIDO"
                            ? "Código demasiado corto: el clasificador se abstiene y no aporta bandera."
                            : channelText({
                                  score: aiPct,
                                  flag: flagB,
                                  estado: estadoCanalB,
                                  onFlag: "Estilo compatible con código generado sobre el umbral calibrado.",
                                  onClear: "Estilo bajo el umbral calibrado.",
                              })}{" "}
                        Umbral {formatNumber(umbralB)} · Bandera {formatFlag(flagB)}
                    </p>
                </div>

                <div className="p-3.5 rounded-xl bg-surface-elevated/70 border border-line-subtle space-y-1.5">
                    <div className="flex items-center justify-between">
                        <span className="text-[11px] font-mono uppercase text-content-muted flex items-center gap-1.5">
                            <Binary size={13} className="text-cyan-400" />
                            Complejidad McCabe
                        </span>
                        <span className="text-sm font-bold text-cyan-400 font-mono">
                            v(G) = {codeMetrics ? codeMetrics.complejidad_ciclomatica : "—"}
                        </span>
                    </div>
                    <p className="text-[11px] text-content-secondary leading-relaxed">
                        {codeMetrics
                            ? `${codeMetrics.lineas_codigo} líneas efectivas, ${codeMetrics.densidad_comentarios} comentarios (heurística, no interviene en el resumen de similitud).`
                            : "Métricas no cargadas; abre el cotejo de código para calcularlas."}
                    </p>
                </div>
            </div>

            {/* Lista de Puntos de Interés Detectados */}
            <div className="space-y-2.5">
                <div className="flex items-center justify-between">
                    <span className="text-xs font-bold uppercase tracking-wider text-content-muted flex items-center gap-1.5">
                        <AlertTriangle size={13} className="text-amber-400" />
                        Puntos de Interés y Atribución por Línea ({indicadores.length})
                    </span>
                    <span className="text-[10px] text-content-muted">
                        Haz clic en una alerta para examinar el código
                    </span>
                </div>

                {indicadores.length === 0 ? (
                    <div className="p-4 rounded-xl bg-surface-elevated/40 border border-line-subtle text-center text-xs text-content-muted flex items-center justify-center gap-2">
                        <CheckCircle size={15} className="text-slate-400" />
                        <span>Sin indicadores registrados para este reporte.</span>
                    </div>
                ) : (
                    <div className="space-y-2 max-h-64 overflow-y-auto custom-scrollbar pr-1">
                        {indicadores.map((ind, idx) => {
                            const cat = indicatorBadge(ind);
                            const hasLine = typeof ind.numero_linea === "number" && ind.numero_linea > 0;

                            return (
                                <div
                                    key={idx}
                                    onClick={() => hasLine && onNavigateToLine?.(ind.numero_linea!)}
                                    className={`group p-3 rounded-xl bg-surface-elevated/80 border border-line-subtle transition-all duration-200 flex items-start justify-between gap-3 ${
                                        hasLine
                                            ? "hover:border-cyan-500/50 hover:bg-surface-elevated cursor-pointer hover:shadow-md"
                                            : ""
                                    }`}
                                >
                                    <div className="space-y-1 flex-1">
                                        <div className="flex items-center gap-2 flex-wrap">
                                            <span
                                                className={`text-[10px] font-bold px-2 py-0.5 rounded-md border ${
                                                    lookupLabel(SEVERITY_BADGES, ind.severidad.toUpperCase()) ?? DEFAULT_SEVERITY_BADGE
                                                }`}
                                            >
                                                {ind.severidad}
                                            </span>
                                            <span className={`text-[10px] font-mono font-semibold ${cat.color}`}>
                                                {cat.label}
                                            </span>
                                            {isHeuristic(ind) && (
                                                <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-surface border border-line-subtle text-content-muted">
                                                    Heurística (no es salida del modelo)
                                                </span>
                                            )}
                                            {hasLine && (
                                                <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-surface border border-line-subtle text-content-secondary">
                                                    Línea {ind.numero_linea}
                                                </span>
                                            )}
                                        </div>
                                        <p className="text-xs text-content-primary leading-snug">
                                            {ind.descripcion}
                                        </p>
                                    </div>

                                    {hasLine && (
                                        <button
                                            type="button"
                                            className="shrink-0 flex items-center gap-1 text-[11px] font-semibold text-cyan-400 group-hover:text-cyan-300 group-hover:translate-x-0.5 transition-transform pt-1"
                                        >
                                            <span>Ver</span>
                                            <ArrowRight size={12} />
                                        </button>
                                    )}
                                </div>
                            );
                        })}
                    </div>
                )}
            </div>
        </div>
    );
}
