import { useState, useEffect, useRef } from "react";
import { ArrowLeft, CheckCircle2, Download, PlayCircle, Settings, Sparkles, Info, ShieldCheck, UserCheck } from "lucide-react";
import { useGSAP } from "@gsap/react";
import gsap from "gsap";
import { AuthCard } from "../components/layout/AuthCard";
import { api } from "../lib/api";

// Helper hook for the typewriter effect (optimized for performance)
function useTypewriter(text: string, speed: number = 15) {
    const [displayedText, setDisplayedText] = useState("");

    useEffect(() => {
        setDisplayedText(""); // Reset when text changes
        if (!text) return;
        
        let i = 0;
        const interval = setInterval(() => {
            if (i < text.length) {
                setDisplayedText(text.slice(0, i + 1));
                i++;
            } else {
                clearInterval(interval);
            }
        }, speed);

        return () => clearInterval(interval);
    }, [text, speed]);

    return displayedText;
}

export interface IndicadorItem {
    id?: number;
    tipo_alerta: string;
    descripcion: string;
    severidad: "BAJA" | "MEDIA" | "ALTA" | "CRITICA" | string;
}

export interface ComparisonData {
    id?: string | number;
    title?: string;
    subtitle?: string;
    similarity?: number;
    similitud_semantica?: number;
    probabilidad_ia?: number;
    discrepancia_score?: number;
    dictamen?: "INTEGRO" | "SOSPECHA_IA" | "PLAGIO_PROBABLE" | string;
    indicadores?: IndicadorItem[];
}

interface SimilarityReportModalProps {
    isOpen: boolean;
    onClose: () => void;
    comparison: ComparisonData | null;
}

export function SimilarityReportModal({ isOpen, onClose, comparison }: SimilarityReportModalProps) {
    const [isAnimating, setIsAnimating] = useState(false);
    const [shouldRender, setShouldRender] = useState(isOpen);
    const [isDownloadingPdf, setIsDownloadingPdf] = useState(false);
    const backdropRef = useRef<HTMLDivElement>(null);
    const contentRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        if (isOpen) {
            setShouldRender(true);
            const timer = setTimeout(() => setIsAnimating(true), 10);
            return () => clearTimeout(timer);
        } else {
            setIsAnimating(false);
            const timer = setTimeout(() => setShouldRender(false), 300);
            return () => clearTimeout(timer);
        }
    }, [isOpen]);

    useGSAP(() => {
        if (!shouldRender) return;

        if (isOpen) {
            gsap.fromTo(backdropRef.current, { opacity: 0 }, { opacity: 1, duration: 0.3, ease: "power2.out" });
            gsap.fromTo(contentRef.current, { opacity: 0, scale: 0.95, y: 32 }, { opacity: 1, scale: 1, y: 0, duration: 0.4, ease: "back.out(1.2)" });
        } else {
            gsap.to(backdropRef.current, { opacity: 0, duration: 0.3, ease: "power2.in" });
            gsap.to(contentRef.current, { opacity: 0, scale: 0.95, y: 32, duration: 0.3, ease: "power2.in", onComplete: () => setShouldRender(false) });
        }
    }, [isOpen, shouldRender]);

    // Dynamic metrics from backend or mock fallback
    const semanticPct = comparison?.similitud_semantica !== undefined
        ? Math.round(comparison.similitud_semantica * 100)
        : (comparison?.similarity ?? 62);
    const aiPct = comparison?.probabilidad_ia !== undefined
        ? Math.round(comparison.probabilidad_ia * 100)
        : 85;
    const overallScore = comparison?.similarity ?? semanticPct;
    const dictamenRaw = comparison?.dictamen || (overallScore > 70 ? 'REVISION_ESTILOMETRICA' : 'SIN_ALERTAS');

    const getAuditInfo = (status: string) => {
        switch (status) {
            case "REVISION_ESTILOMETRICA":
            case "SOSPECHA_IA":
                return {
                    label: "Revisión Sugerida (IA)",
                    color: "text-amber-400",
                };
            case "REVISION_SEMANTICA":
            case "PLAGIO_PROBABLE":
                return {
                    label: "Coincidencia Lógica",
                    color: "text-purple-400",
                };
            case "DISCREPANCIA_DUAL":
                return {
                    label: "Alerta Dual (Lógica + IA)",
                    color: "text-rose-400",
                };
            default:
                return {
                    label: "Conforme (Sin Alertas)",
                    color: "text-emerald-400",
                };
        }
    };
    const auditInfo = getAuditInfo(dictamenRaw);

    // Typewriter effect description
    const fullInterpretationText = comparison?.dictamen
        ? `Diagnóstico de Soporte Docente: ${auditInfo.label}

Canal A (Similitud Semántica): ${semanticPct}% de coincidencia con soluciones de referencia mediante Grafos de Flujo de Datos (DFG).
Canal B (Estilometría CharCNN): ${aiPct}% de probabilidad de sintaxis afín a modelos generativos (LLM).
Puntaje de Discrepancia Asimétrica: ${comparison.discrepancia_score ?? (semanticPct * aiPct / 10000).toFixed(2)}.

${dictamenRaw === 'REVISION_ESTILOMETRICA' || dictamenRaw === 'SOSPECHA_IA' || dictamenRaw === 'DISCREPANCIA_DUAL'
    ? 'Recomendación Pericial: Se identificaron regularidades sintácticas afines a modelos generativos. Este dato es una guía orientativa de apoyo; se sugiere formular preguntas conceptuales al estudiante sobre sus decisiones de implementación.'
    : 'Recomendación Pericial: El código analizado presenta una redacción y estructura acordes a la variabilidad esperada de autoría humana estudiantil.'}`
        : `Este informe técnico proporciona evidencia cuantitativa para asistir la evaluación académica del docente. La resolución pedagógica final es potestad exclusiva de la cátedra.`;

    const typewriterText = useTypewriter(isOpen ? fullInterpretationText : "", 3);

    const handleDownloadPdf = async () => {
        if (!comparison?.id) return;
        try {
            setIsDownloadingPdf(true);
            const reportId = typeof comparison.id === "string" ? parseInt(comparison.id, 10) : comparison.id;
            if (!isNaN(reportId)) {
                await api.analysis.downloadPdf(reportId, `reporte_integridad_${reportId}.pdf`);
            }
        } catch (err) {
            console.error("Error al descargar PDF:", err);
            alert("No se pudo generar o descargar el reporte PDF.");
        } finally {
            setIsDownloadingPdf(false);
        }
    };

    if (!shouldRender || !comparison) return null;

    // SVG Circle Graphic calculations
    const radius = 90;
    const circumference = 2 * Math.PI * radius;
    const strokeDashoffset = isAnimating ? circumference - (overallScore / 100) * circumference : circumference;

    return (
        <div className={`fixed inset-0 z-[100] flex items-center justify-center p-4`}>
            {/* Backdrop */}
            <div
                ref={backdropRef}
                className={`absolute inset-0 bg-black/80 backdrop-blur-md opacity-0`}
                onClick={onClose}
            />

            {/* Modal Content */}
            <div ref={contentRef} className={`w-full max-w-5xl opacity-0 transform translate-y-8 scale-95`}>
                <AuthCard className="w-full p-0 overflow-hidden border-[#2b3346]/60 backdrop-blur-2xl bg-[#0f1522]/90">

                    <div className="flex flex-col h-full max-h-[90vh]">
                        {/* Top Navigation Bar */}
                        <div className="flex items-center justify-between px-8 py-4 border-b border-[#2b3346]/40 bg-black/20">
                            <button
                                onClick={onClose}
                                className="flex items-center gap-2 text-sm font-medium text-slate-400 hover:text-white active:scale-95 focus:outline-none focus-visible:ring-2 focus-visible:ring-slate-400 rounded-md px-2 py-1 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
                            >
                                <ArrowLeft size={16} />
                                Volver a la biblioteca
                            </button>
                        </div>

                        {/* Header */}
                        <div className="px-10 pt-8 pb-6 flex items-start justify-between">
                            <div>
                                <h2 className="text-3xl font-display font-black text-white tracking-tight">
                                    Reporte de similitud
                                </h2>
                                <div className="flex items-center gap-4 mt-2 text-sm text-slate-400 font-medium">
                                    <span>Proyecto: {comparison.title}</span>
                                    <span className="w-1 h-1 rounded-full bg-slate-600"></span>
                                    <span>14 de Abril, 2026</span>
                                </div>
                            </div>
                            <div className="flex items-center gap-2 bg-[#1a2031] border border-[#2b3346] px-4 py-2 rounded-full">
                                <div className="w-2 h-2 rounded-full bg-graphito-blue"></div>
                                <span className="text-xs font-bold text-slate-300">Análisis completado</span>
                            </div>
                        </div>

                        {/* Body */}
                        <div className="flex-1 overflow-y-auto px-10 pb-8 scrollbar-thin scrollbar-thumb-[#2b3346] scrollbar-track-transparent">
                            {/* DSS Institutional Banner */}
                            <div className="flex items-center gap-3 px-5 py-3 mb-6 bg-blue-500/10 border border-blue-500/25 rounded-2xl text-xs font-medium text-blue-200">
                                <Info size={18} className="shrink-0 text-blue-400" />
                                <span><strong>Sistema de Soporte a la Decisión (HITL):</strong> Graphito provee métricas periciales automatizadas sin emitir sentencias disciplinarias. La evaluación y calificación final corresponden al criterio pedagógico del profesor.</span>
                            </div>

                            <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">

                                {/* Left Column: Big Chart */}
                                <div className="lg:col-span-4 flex flex-col items-center justify-center p-8 bg-[#121827]/40 border border-[#2b3346]/60 rounded-3xl h-full">

                                    {/* Circular Graph */}
                                    <div className="relative w-64 h-64 flex items-center justify-center">
                                        {/* Background Circle */}
                                        <svg className="w-full h-full transform -rotate-90">
                                            <circle
                                                cx="128"
                                                cy="128"
                                                r={radius}
                                                className="stroke-[#2b3346] fill-none"
                                                strokeWidth="16"
                                            />

                                            {/* Gradient defs */}
                                            <defs>
                                                <linearGradient id="scoreGradient" x1="0%" y1="0%" x2="100%" y2="100%">
                                                    <stop offset="0%" stopColor="#3b82f6" />
                                                    <stop offset="100%" stopColor="#a78bfa" />
                                                </linearGradient>
                                            </defs>

                                            {/* Foreground Circle - Animated */}
                                            <circle
                                                cx="128"
                                                cy="128"
                                                r={radius}
                                                className="fill-none transition-all duration-1000 ease-out"
                                                stroke="url(#scoreGradient)"
                                                strokeWidth="16"
                                                strokeLinecap="round"
                                                strokeDasharray={circumference}
                                                strokeDashoffset={strokeDashoffset}
                                            />
                                        </svg>

                                        {/* Score Text */}
                                        <div className="absolute flex flex-col items-center justify-center text-center px-4">
                                            <span className="text-5xl font-black text-white tracking-tight">
                                                {overallScore}%
                                            </span>
                                            <span className={`text-xs font-bold uppercase tracking-wider mt-1.5 ${auditInfo.color}`}>
                                                {auditInfo.label}
                                            </span>
                                        </div>
                                    </div>

                                    <h3 className="text-lg font-bold text-white mt-8 mb-2">Similitud total</h3>
                                    <p className="text-sm text-center text-slate-400">
                                        Se detectó una coincidencia {overallScore > 50 ? 'significativa' : 'menor'} en la estructura lógica central del código analizado.
                                    </p>
                                </div>

                                {/* Right Column: Breakdown & Interpretation */}
                                <div className="lg:col-span-8 flex flex-col gap-6">

                                    {/* Top row: Two metric cards */}
                                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6 p-1">

                                        {/* Stylometry Card */}
                                        <div className="bg-[#121827]/40 border border-[#2b3346]/60 rounded-3xl p-6 hover:bg-[#121827]/60 transition-colors">
                                            <div className="flex items-center gap-3 mb-6">
                                                <div className="w-10 h-10 rounded-xl bg-graphito-violet/10 flex items-center justify-center text-graphito-violet">
                                                    <Settings size={20} />
                                                </div>
                                                <h4 className="font-bold text-white">Análisis estilométrico</h4>
                                            </div>

                                            <div className="space-y-4">
                                                <div>
                                                    <div className="flex justify-between text-xs font-bold text-slate-400 mb-2">
                                                        <span>Probabilidad de IA</span>
                                                        <span className="text-white">{aiPct}%</span>
                                                    </div>
                                                    <div className="h-1.5 w-full bg-[#2b3346]/60 rounded-full overflow-hidden">
                                                        <div
                                                            className="h-full bg-graphito-violet rounded-full transition-all duration-1000 ease-out"
                                                            style={{ width: isAnimating ? `${aiPct}%` : '0%' }}
                                                        ></div>
                                                    </div>
                                                </div>

                                                <ul className="space-y-3 mt-6">
                                                    {comparison.indicadores && comparison.indicadores.length > 0 ? (
                                                        comparison.indicadores.map((ind, idx) => (
                                                            <li key={idx} className="flex items-start gap-2.5 text-xs text-slate-300">
                                                                <CheckCircle2 size={16} className={`${ind.severidad === 'ALTA' || ind.severidad === 'CRITICA' ? 'text-orange-400' : 'text-slate-500'} shrink-0 mt-0.5`} />
                                                                <span><strong className="text-white">{ind.tipo_alerta}:</strong> {ind.descripcion}</span>
                                                            </li>
                                                        ))
                                                    ) : (
                                                        <>
                                                            <li className="flex items-start gap-2.5 text-xs text-slate-300">
                                                                <CheckCircle2 size={16} className="text-slate-500 shrink-0" />
                                                                <span>Nomenclatura y patrones sintácticos analizados con CharCNN.</span>
                                                            </li>
                                                            <li className="flex items-start gap-2.5 text-xs text-slate-300">
                                                                <CheckCircle2 size={16} className="text-slate-500 shrink-0" />
                                                                <span>Estructura léxica y regularidad de comentarios evaluada.</span>
                                                            </li>
                                                        </>
                                                    )}
                                                </ul>
                                            </div>
                                        </div>

                                        {/* Semantic Card */}
                                        <div className="bg-[#121827]/40 border border-[#2b3346]/60 rounded-3xl p-6 hover:bg-[#121827]/60 transition-colors">
                                            <div className="flex items-center gap-3 mb-6">
                                                <div className="w-10 h-10 rounded-xl bg-graphito-blue/10 flex items-center justify-center text-graphito-blue">
                                                    <PlayCircle size={20} />
                                                </div>
                                                <h4 className="font-bold text-white">Análisis semántico</h4>
                                            </div>

                                            <div className="space-y-4">
                                                <div>
                                                    <div className="flex justify-between text-xs font-bold text-slate-400 mb-2">
                                                        <span>Similitud de flujo DFG</span>
                                                        <span className="text-white">{semanticPct}%</span>
                                                    </div>
                                                    <div className="h-1.5 w-full bg-[#2b3346]/60 rounded-full overflow-hidden">
                                                        <div
                                                            className="h-full bg-graphito-blue rounded-full transition-all duration-1000 ease-out"
                                                            style={{ width: isAnimating ? `${semanticPct}%` : '0%' }}
                                                        ></div>
                                                    </div>
                                                </div>

                                                <ul className="space-y-3 mt-6">
                                                    <li className="flex items-start gap-2.5 text-xs text-slate-300">
                                                        <CheckCircle2 size={16} className="text-slate-500 shrink-0" />
                                                        <span>Grafo de flujo de datos (DFG) comparado contra soluciones canónicas.</span>
                                                    </li>
                                                    <li className="flex items-start gap-2.5 text-xs text-slate-300">
                                                        <CheckCircle2 size={16} className="text-slate-500 shrink-0" />
                                                        <span>Invarianza ante renombramiento de variables y reordenamiento de bloques.</span>
                                                    </li>
                                                </ul>
                                            </div>
                                        </div>

                                    </div>

                                    {/* Bottom row: AI Interpretation (Typewriter) */}
                                    <div className="bg-[#121827]/60 border border-[#2b3346]/60 rounded-3xl p-6 flex-1 hover:border-[#334155] transition-colors relative overflow-hidden group">
                                        <div className="absolute top-0 right-0 w-64 h-64 bg-graphito-blue/5 rounded-full blur-3xl -translate-y-1/2 translate-x-1/2 opacity-0 group-hover:opacity-100 transition-opacity duration-700"></div>

                                        <div className="flex items-center gap-4 mb-4">
                                            <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-graphito-blue to-graphito-violet flex items-center justify-center text-white shadow-lg shadow-graphito-blue/20">
                                                <Sparkles size={24} />
                                            </div>
                                            <h4 className="text-lg font-bold text-white">Interpretación del análisis</h4>
                                        </div>

                                        <div className="text-sm font-medium text-slate-300 leading-relaxed max-w-3xl whitespace-pre-line break-words format-text min-h-[120px]">
                                            {typewriterText}
                                            {/* Blinking cursor */}
                                            <span className="inline-block w-1.5 h-4 bg-graphito-blue ml-1 animate-pulse align-middle"></span>
                                        </div>
                                    </div>

                                </div>
                            </div>
                        </div>

                        {/* Footer */}
                        <div className="flex items-center justify-between px-10 py-6 border-t border-[#2b3346]/40 bg-black/40 mt-auto shrink-0">
                            <div className="text-xs font-medium text-slate-500">
                                Documento: {comparison.id ? `REP_${comparison.id}` : 'REP_LIVE-RUN'}
                            </div>
                            <div className="flex items-center gap-3">
                                <button
                                    onClick={() => {
                                        alert("Entrega validada como Conforme por el docente.");
                                        onClose();
                                    }}
                                    className="flex items-center gap-1.5 px-4 py-2.5 rounded-xl border border-emerald-500/30 bg-emerald-500/10 text-emerald-300 hover:bg-emerald-500/20 active:scale-95 text-xs font-bold transition-all"
                                    title="El docente valida la entrega como autoría legítima"
                                >
                                    <ShieldCheck size={16} />
                                    <span>Validar Conforme</span>
                                </button>
                                <button
                                    onClick={() => {
                                        alert("Entrega marcada para entrevista y defensa oral con el estudiante.");
                                        onClose();
                                    }}
                                    className="flex items-center gap-1.5 px-4 py-2.5 rounded-xl border border-amber-500/30 bg-amber-500/10 text-amber-300 hover:bg-amber-500/20 active:scale-95 text-xs font-bold transition-all"
                                    title="El docente cita al alumno para justificar sus decisiones de código"
                                >
                                    <UserCheck size={16} />
                                    <span>Citar a Aclaración</span>
                                </button>
                                <button
                                    onClick={handleDownloadPdf}
                                    disabled={isDownloadingPdf || !comparison.id}
                                    className="flex items-center gap-2 px-5 py-2.5 rounded-xl border border-[#2b3346] text-xs font-bold text-white hover:bg-white/5 active:scale-95 focus:outline-none focus-visible:ring-2 focus-visible:ring-slate-400 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
                                >
                                    {isDownloadingPdf ? (
                                        <>
                                            <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                                            <span>Generando...</span>
                                        </>
                                    ) : (
                                        <>
                                            <Download size={16} />
                                            <span>Descargar PDF</span>
                                        </>
                                    )}
                                </button>
                                <button
                                    onClick={onClose}
                                    className="px-5 py-2.5 rounded-xl bg-gradient-to-r from-graphito-blue to-graphito-violet text-xs font-bold text-white hover:opacity-90 active:scale-95 focus:outline-none focus-visible:ring-2 focus-visible:ring-graphito-blue disabled:opacity-50 disabled:cursor-not-allowed transition-all"
                                >
                                    Cerrar
                                </button>
                            </div>
                        </div>

                    </div>
                </AuthCard>
            </div>
        </div>
    );
}
