import { AlertTriangle, Cpu, FileCode2, Sparkles, Binary, ArrowRight, ShieldAlert, CheckCircle, Info } from "lucide-react";
import { IndicadorIntegridad } from "../../lib/api";

interface EvidenceDrawerProps {
    semanticScore: number;
    aiScore: number;
    discrepancyScore?: number;
    dictamen?: string;
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

export function EvidenceDrawer({
    semanticScore,
    aiScore,
    discrepancyScore,
    dictamen,
    indicadores,
    codeMetrics,
    onNavigateToLine,
}: EvidenceDrawerProps) {
    const getSeverityBadge = (severity: string) => {
        switch (severity.toUpperCase()) {
            case "CRITICA":
                return "bg-rose-500/15 text-rose-400 border-rose-500/30";
            case "ALTA":
                return "bg-amber-500/15 text-amber-400 border-amber-500/30";
            case "MEDIA":
                return "bg-yellow-500/15 text-yellow-300 border-yellow-500/30";
            default:
                return "bg-cyan-500/15 text-cyan-400 border-cyan-500/30";
        }
    };

    const getCategoryBadge = (category?: string) => {
        switch (category) {
            case "ISOMORFISMO_DFG":
                return { label: "Flujo Lógico (DFG)", color: "text-purple-400" };
            case "ESTILO_LLM":
                return { label: "Patrón IA Generativa", color: "text-emerald-400" };
            case "NIVEL_AVANZADO":
                return { label: "Construcción Avanzada", color: "text-amber-400" };
            default:
                return { label: "Observación Forense", color: "text-cyan-400" };
        }
    };

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
                                Explainable AI
                            </span>
                        </h3>
                        <p className="text-[11px] text-content-secondary">
                            Trazabilidad objetiva de anomalías sintácticas y equivalencia semántica para respaldo docente.
                        </p>
                    </div>
                </div>
            </div>

            {/* Pilares Multidimensionales de Evaluación */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                {/* Pilar 1: Semántica DFG */}
                <div className="p-3.5 rounded-xl bg-surface-elevated/70 border border-line-subtle space-y-1.5">
                    <div className="flex items-center justify-between">
                        <span className="text-[11px] font-mono uppercase text-content-muted flex items-center gap-1.5">
                            <Cpu size={13} className="text-purple-400" />
                            Equivalencia Semántica
                        </span>
                        <span className="text-sm font-bold text-purple-400">{Math.round(semanticScore)}%</span>
                    </div>
                    <p className="text-[11px] text-content-secondary leading-relaxed">
                        {semanticScore >= 80
                            ? "Estructura isomórfica crítica en el grafo de flujo de variables frente a la solución canónica."
                            : semanticScore >= 50
                            ? "Solución con similitud algorítmica moderada pero variantes de diseño propias."
                            : "Estructura algorítmica independiente y divergente de la referencia."}
                    </p>
                </div>

                {/* Pilar 2: Estilometría CharCNN */}
                <div className="p-3.5 rounded-xl bg-surface-elevated/70 border border-line-subtle space-y-1.5">
                    <div className="flex items-center justify-between">
                        <span className="text-[11px] font-mono uppercase text-content-muted flex items-center gap-1.5">
                            <FileCode2 size={13} className="text-emerald-400" />
                            Huella Estilométrica
                        </span>
                        <span className="text-sm font-bold text-emerald-400">{Math.round(aiScore)}%</span>
                    </div>
                    <p className="text-[11px] text-content-secondary leading-relaxed">
                        {aiScore >= 70
                            ? "Densidad de comentarios y uniformidad de caracteres altamente correlacionada con modelos LLM."
                            : "Patrones de escritura, indentación irregular y nombres característicos de un programador novel."}
                    </p>
                </div>

                {/* Pilar 3: Complejidad y Métricas de Código */}
                <div className="p-3.5 rounded-xl bg-surface-elevated/70 border border-line-subtle space-y-1.5">
                    <div className="flex items-center justify-between">
                        <span className="text-[11px] font-mono uppercase text-content-muted flex items-center gap-1.5">
                            <Binary size={13} className="text-cyan-400" />
                            Complejidad McCabe
                        </span>
                        <span className="text-sm font-bold text-cyan-400 font-mono">
                            v(G) = {codeMetrics?.complejidad_ciclomatica ?? 3}
                        </span>
                    </div>
                    <p className="text-[11px] text-content-secondary leading-relaxed">
                        {codeMetrics ? (
                            <>
                                {codeMetrics.lineas_codigo} líneas efectivas, {codeMetrics.densidad_comentarios} comentarios
                                (Nivel esperado para curso introductorio).
                            </>
                        ) : (
                            "Densidad de bifurcaciones y construcciones de control dentro del rango escolar estándar."
                        )}
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
                        <CheckCircle size={15} className="text-emerald-400" />
                        <span>No se detectaron anomalías críticas ni patrones atípicos de generación.</span>
                    </div>
                ) : (
                    <div className="space-y-2 max-h-64 overflow-y-auto custom-scrollbar pr-1">
                        {indicadores.map((ind, idx) => {
                            const cat = getCategoryBadge(ind.categoria);
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
                                        <div className="flex items-center gap-2">
                                            <span
                                                className={`text-[10px] font-bold px-2 py-0.5 rounded-md border ${getSeverityBadge(
                                                    ind.severidad
                                                )}`}
                                            >
                                                {ind.severidad}
                                            </span>
                                            <span className={`text-[10px] font-mono font-semibold ${cat.color}`}>
                                                {cat.label}
                                            </span>
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
