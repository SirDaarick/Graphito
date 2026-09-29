import { useState, useEffect, useRef } from "react";
import { ArrowLeft, CheckCircle2, Download, PlayCircle, Settings, Sparkles, Info, ShieldCheck, UserCheck, Code2, FileText, ChevronDown, ChevronUp, ChevronLeft, ChevronRight, Maximize2, Minimize2, X } from "lucide-react";
import { useGSAP } from "@gsap/react";
import gsap from "gsap";
import { AuthCard } from "../components/layout/AuthCard";
import { api } from "../lib/api";
import { SideBySideDiffViewer, ComentarioRevisionItem } from "../components/code/SideBySideDiffViewer";

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
    submissions?: ComparisonData[];
    onSelectComparison?: (comparison: ComparisonData) => void;
}

export function SimilarityReportModal({
    isOpen,
    onClose,
    comparison,
    submissions,
    onSelectComparison,
}: SimilarityReportModalProps) {
    const [isAnimating, setIsAnimating] = useState(false);
    const [shouldRender, setShouldRender] = useState(isOpen);
    const [isDownloadingPdf, setIsDownloadingPdf] = useState(false);
    const [viewMode, setViewMode] = useState<"report" | "code_diff">("report");
    const [isUltraWide, setIsUltraWide] = useState(false);
    const [codeData, setCodeData] = useState<{
        reference_code: string;
        student_code: string;
        reference_author: string;
        student_author: string;
        language: string;
    } | null>(null);
    const [isLoadingCode, setIsLoadingCode] = useState(false);
    const [comments, setComments] = useState<ComentarioRevisionItem[]>([]);
    const [isSubmittingComment, setIsSubmittingComment] = useState(false);
    const [isNavigating, setIsNavigating] = useState(false);
    const [triageToast, setTriageToast] = useState<{ message: string; type: "success" | "warning" } | null>(null);
    const backdropRef = useRef<HTMLDivElement>(null);
    const contentRef = useRef<HTMLDivElement>(null);
    const bodyContainerRef = useRef<HTMLDivElement>(null);

    const currentIndex = submissions && comparison
        ? submissions.findIndex((s) => String(s.id) === String(comparison.id))
        : -1;
    const hasNext = Boolean(submissions && currentIndex >= 0 && currentIndex < submissions.length - 1);
    const hasPrev = Boolean(submissions && currentIndex > 0);

    const navigateTo = (newIndex: number) => {
        if (!submissions || newIndex < 0 || newIndex >= submissions.length || isNavigating) return;
        setIsNavigating(true);

        const direction = newIndex > currentIndex ? 1 : -1;

        if (bodyContainerRef.current) {
            gsap.to(bodyContainerRef.current, {
                opacity: 0,
                x: -direction * 24,
                duration: 0.16,
                ease: "power2.in",
                onComplete: () => {
                    onSelectComparison?.(submissions[newIndex]);
                    if (bodyContainerRef.current) {
                        bodyContainerRef.current.scrollTop = 0;
                    }
                    gsap.fromTo(
                        bodyContainerRef.current,
                        { opacity: 0, x: direction * 24 },
                        {
                            opacity: 1,
                            x: 0,
                            duration: 0.22,
                            ease: "power2.out",
                            onComplete: () => setIsNavigating(false),
                        }
                    );
                },
            });
        } else {
            onSelectComparison?.(submissions[newIndex]);
            setIsNavigating(false);
        }
    };

    const handleVerdictAndAdvance = (type: "conforme" | "aclaracion") => {
        const isConforme = type === "conforme";
        const msg = isConforme
            ? "Entrega validada como Conforme por el docente."
            : "Entrega citada para entrevista y aclaración con el estudiante.";

        setTriageToast({
            message: msg,
            type: isConforme ? "success" : "warning",
        });

        setTimeout(() => {
            setTriageToast(null);
        }, 2600);

        if (hasNext && currentIndex >= 0) {
            navigateTo(currentIndex + 1);
        } else {
            setTimeout(() => {
                onClose();
            }, 1000);
        }
    };

    useEffect(() => {
        if (isOpen && comparison?.id) {
            const repId = typeof comparison.id === "string" ? parseInt(comparison.id, 10) : comparison.id;
            if (!isNaN(repId)) {
                api.comments.list(repId).then(setComments).catch(() => setComments([]));
                if (viewMode === "code_diff") {
                    fetchCode(repId);
                }
            }
        } else {
            setViewMode("report");
            setCodeData(null);
        }
    }, [isOpen, comparison?.id, viewMode]);

    useEffect(() => {
        if (!isOpen) return;

        const handleKeyDown = (e: KeyboardEvent) => {
            const target = e.target as HTMLElement;
            if (
                target &&
                (target.tagName === "INPUT" ||
                 target.tagName === "TEXTAREA" ||
                 target.isContentEditable)
            ) {
                return;
            }

            if (e.key === "ArrowRight") {
                e.preventDefault();
                if (hasNext && currentIndex >= 0) {
                    navigateTo(currentIndex + 1);
                }
            } else if (e.key === "ArrowLeft") {
                e.preventDefault();
                if (hasPrev && currentIndex >= 0) {
                    navigateTo(currentIndex - 1);
                }
            } else if (e.key === "Escape") {
                e.preventDefault();
                onClose();
            } else if (e.key === "a" || e.key === "A") {
                e.preventDefault();
                handleVerdictAndAdvance("conforme");
            } else if (e.key === "r" || e.key === "R") {
                e.preventDefault();
                handleVerdictAndAdvance("aclaracion");
            }
        };

        window.addEventListener("keydown", handleKeyDown);
        return () => window.removeEventListener("keydown", handleKeyDown);
    }, [isOpen, currentIndex, hasNext, hasPrev, submissions, isNavigating]);

    const fetchCode = async (repId: number) => {
        setIsLoadingCode(true);
        try {
            const data = await api.analysis.getCode(repId);
            setCodeData({
                reference_code: data.reference_code || "// Sin código de referencia registrado",
                student_code: data.student_code || "// Sin código de entrega registrado",
                reference_author: data.reference_author || "Docente (Referencia)",
                student_author: data.student_author || comparison?.title || "Estudiante",
                language: data.language || "c",
            });
        } catch (err) {
            console.warn("No se pudo obtener el código desde la API, usando código de demostración:", err);
            setCodeData({
                reference_code: `// Código Canónico de Referencia - ${comparison?.title || "Práctica"}
#include <stdio.h>
#include <stdlib.h>

int busqueda_binaria(int arr[], int n, int objetivo) {
    int inicio = 0;
    int fin = n - 1;

    while (inicio <= fin) {
        int medio = inicio + (fin - inicio) / 2;
        if (arr[medio] == objetivo) {
            return medio; // Encontrado
        }
        if (arr[medio] < objetivo) {
            inicio = medio + 1;
        } else {
            fin = medio - 1;
        }
    }
    return -1; // No encontrado
}

int main() {
    int datos[] = {2, 4, 6, 8, 10, 12, 14, 16};
    int tam = sizeof(datos) / sizeof(datos[0]);
    int obj = 10;
    int pos = busqueda_binaria(datos, tam, obj);
    printf("Posicion: %d\\n", pos);
    return 0;
}`,
                student_code: `// Entrega del Alumno - ${comparison?.title || "Solución"}
#include <stdio.h>

int binarySearch(int a[], int size, int target) {
    int low = 0;
    int high = size - 1;

    // Búsqueda iterativa en subarreglo ordenado
    while (low <= high) {
        int mid = (low + high) / 2;
        if (a[mid] == target) {
            return mid;
        }
        if (a[mid] < target) {
            low = mid + 1;
        } else {
            high = mid - 1;
        }
    }
    return -1;
}

int main() {
    int a[] = {2, 4, 6, 8, 10, 12, 14, 16};
    int n = 8;
    int x = 10;
    int r = binarySearch(a, n, x);
    printf("Resultado: %d\\n", r);
    return 0;
}`,
                reference_author: "Prof. Manuel Portillo (ESCOM)",
                student_author: comparison?.title || "Estudiante Evaluado",
                language: "c",
            });
        } finally {
            setIsLoadingCode(false);
        }
    };

    const handleAddComment = async (lineNum: number | null, text: string) => {
        if (!comparison?.id) return;
        const repId = typeof comparison.id === "string" ? parseInt(comparison.id, 10) : comparison.id;
        if (isNaN(repId)) return;

        setIsSubmittingComment(true);
        try {
            const newComment = await api.comments.create(repId, {
                numero_linea: lineNum,
                contenido: text,
            });
            setComments((prev) => [...prev, newComment]);
        } catch (err) {
            console.error("Error al crear comentario:", err);
            setComments((prev) => [
                ...prev,
                {
                    id: Date.now(),
                    reporte_id: repId,
                    docente_id: 1,
                    numero_linea: lineNum,
                    contenido: text,
                    created_at: new Date().toISOString(),
                    autor_nombre: "Docente",
                },
            ]);
        } finally {
            setIsSubmittingComment(false);
        }
    };

    const handleDeleteComment = async (commentId: number) => {
        if (!comparison?.id) return;
        const repId = typeof comparison.id === "string" ? parseInt(comparison.id, 10) : comparison.id;
        if (!isNaN(repId)) {
            try {
                await api.comments.delete(repId, commentId);
            } catch (err) {
                console.warn("Error al eliminar comentario en API:", err);
            }
        }
        setComments((prev) => prev.filter((c) => c.id !== commentId));
    };

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
        <div className={`fixed inset-0 z-[100] flex items-center justify-center ${viewMode === 'code_diff' ? 'p-2 sm:p-3 md:p-4' : 'p-4'}`}>
            {/* Backdrop */}
            <div
                ref={backdropRef}
                className={`absolute inset-0 bg-black/80 backdrop-blur-sm opacity-0`}
                onClick={onClose}
            />

            {/* Modal Content */}
            <div
                ref={contentRef}
                className={`w-full ${
                    viewMode === 'code_diff'
                        ? (isUltraWide ? 'w-[98vw] max-w-[99vw]' : 'w-[92vw] sm:w-[94vw] max-w-[96vw] 2xl:max-w-[2500px]')
                        : 'max-w-5xl'
                } opacity-0 transform translate-y-8 scale-95 transition-all duration-300`}
            >
                <AuthCard className="w-full p-0 overflow-hidden border-slate-200 dark:border-[#2b3346]/60 bg-white/95 dark:bg-[#0f1522]/90">

                    <div className={`flex flex-col h-full ${viewMode === 'code_diff' ? 'h-[95vh] max-h-[96vh]' : 'max-h-[92vh]'} relative`}>
                        {/* Floating Toast para Veredicto y Avance Ágil */}
                        {triageToast && (
                            <div className={`absolute top-16 left-1/2 -translate-x-1/2 z-50 px-5 py-2.5 rounded-2xl text-xs font-bold shadow-2xl border flex items-center gap-2.5 backdrop-blur-md transition-all ${
                                triageToast.type === "success"
                                    ? "bg-emerald-950/95 text-emerald-200 border-emerald-500/50 shadow-emerald-950/60"
                                    : "bg-amber-950/95 text-amber-200 border-amber-500/50 shadow-amber-950/60"
                            }`}>
                                {triageToast.type === "success" ? <ShieldCheck size={18} className="text-emerald-400" /> : <UserCheck size={18} className="text-amber-400" />}
                                <span>{triageToast.message}</span>
                                {hasNext && <span className="opacity-80 font-mono text-[10px] ml-1 bg-white/10 px-1.5 py-0.5 rounded">→ Pasando a siguiente entrega</span>}
                            </div>
                        )}

                        {/* Top Navigation Bar — Zen Unified Header */}
                        <div className="flex items-center justify-between px-4 sm:px-6 py-2.5 border-b border-slate-200 dark:border-[#2b3346]/40 bg-slate-50 dark:bg-[#0f1422] shrink-0 gap-3">
                            {/* Left: Volver */}
                            <button
                                onClick={onClose}
                                aria-label="Volver a la biblioteca"
                                className="group relative p-2 rounded-xl text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white hover:bg-slate-200/60 dark:hover:bg-slate-800/80 active:scale-95 transition-all shrink-0"
                            >
                                <ArrowLeft size={16} />
                                <div role="tooltip" className="absolute top-full left-0 mt-2 opacity-0 pointer-events-none group-hover:opacity-100 transition-opacity duration-200 flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-slate-900/95 dark:bg-[#090e1a]/95 border border-slate-700/80 text-white text-xs font-sans font-medium whitespace-nowrap shadow-2xl z-[120]">
                                    <span>Volver a la biblioteca</span>
                                    <kbd className="px-1.5 py-0.5 text-[9px] font-mono bg-white/10 rounded border border-white/20">Esc</kbd>
                                </div>
                            </button>

                            {/* Center: In Diff Mode, show Agile Carousel */}
                            {viewMode === "code_diff" ? (
                                <div className="flex items-center gap-2 sm:gap-3 overflow-x-auto py-0.5">
                                    {submissions && submissions.length > 0 && currentIndex >= 0 && (
                                        <div className="flex items-center gap-1.5 bg-slate-200/50 dark:bg-[#141b2a] px-2 py-1 rounded-xl border border-slate-300/40 dark:border-slate-800 shrink-0">
                                            <button
                                                onClick={() => navigateTo(currentIndex - 1)}
                                                disabled={!hasPrev || isNavigating}
                                                aria-label="Entrega anterior"
                                                className="group relative p-1.5 rounded-lg text-slate-700 dark:text-slate-300 hover:bg-white dark:hover:bg-slate-800 disabled:opacity-30 disabled:cursor-not-allowed transition-all"
                                            >
                                                <ChevronLeft size={14} />
                                                <div role="tooltip" className="absolute top-full left-0 mt-2 opacity-0 pointer-events-none group-hover:opacity-100 transition-opacity duration-200 flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-slate-900/95 dark:bg-[#090e1a]/95 border border-slate-700/80 text-white text-[11px] font-sans font-medium whitespace-nowrap shadow-xl z-[120]">
                                                    <span>Entrega anterior</span>
                                                    <kbd className="px-1 text-[9px] font-mono bg-white/10 rounded">←</kbd>
                                                </div>
                                            </button>
                                            <span className="text-xs font-black text-slate-800 dark:text-slate-200 px-1 font-mono">
                                                {currentIndex + 1} / {submissions.length}
                                            </span>
                                            <span className="text-xs text-slate-500 dark:text-slate-400 max-w-[200px] truncate hidden sm:inline font-medium" title={comparison.title}>
                                                {comparison.title}
                                            </span>
                                            <button
                                                onClick={() => navigateTo(currentIndex + 1)}
                                                disabled={!hasNext || isNavigating}
                                                aria-label="Siguiente entrega"
                                                className="group relative p-1.5 rounded-lg text-slate-700 dark:text-slate-300 hover:bg-white dark:hover:bg-slate-800 disabled:opacity-30 disabled:cursor-not-allowed transition-all"
                                            >
                                                <ChevronRight size={14} />
                                                <div role="tooltip" className="absolute top-full right-0 mt-2 opacity-0 pointer-events-none group-hover:opacity-100 transition-opacity duration-200 flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-slate-900/95 dark:bg-[#090e1a]/95 border border-slate-700/80 text-white text-[11px] font-sans font-medium whitespace-nowrap shadow-xl z-[120]">
                                                    <span>Siguiente entrega</span>
                                                    <kbd className="px-1 text-[9px] font-mono bg-white/10 rounded">→</kbd>
                                                </div>
                                            </button>
                                        </div>
                                    )}
                                </div>
                            ) : (
                                /* In Report Mode: Carousel */
                                submissions && submissions.length > 0 && currentIndex >= 0 ? (
                                    <div className="flex items-center gap-1.5 bg-slate-200/60 dark:bg-[#161d2d] px-2 py-1 rounded-2xl border border-slate-300/60 dark:border-[#2b3346]">
                                        <button
                                            onClick={() => navigateTo(currentIndex - 1)}
                                            disabled={!hasPrev || isNavigating}
                                            aria-label="Entrega anterior"
                                            className="group relative p-1.5 rounded-xl text-slate-700 dark:text-slate-300 hover:bg-white dark:hover:bg-slate-800 disabled:opacity-30 disabled:cursor-not-allowed transition-all"
                                        >
                                            <ChevronLeft size={15} />
                                            <div role="tooltip" className="absolute top-full left-0 mt-2 opacity-0 pointer-events-none group-hover:opacity-100 transition-opacity duration-200 flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-slate-900/95 dark:bg-[#090e1a]/95 border border-slate-700/80 text-white text-[11px] font-sans font-medium whitespace-nowrap shadow-xl z-[120]">
                                                <span>Entrega anterior</span>
                                                <kbd className="px-1 text-[9px] font-mono bg-white/10 rounded">←</kbd>
                                            </div>
                                        </button>
                                        <span className="text-xs font-bold text-slate-800 dark:text-slate-200 px-2 font-mono">
                                            {currentIndex + 1} de {submissions.length} — {comparison.title}
                                        </span>
                                        <button
                                            onClick={() => navigateTo(currentIndex + 1)}
                                            disabled={!hasNext || isNavigating}
                                            aria-label="Siguiente entrega"
                                            className="group relative p-1.5 rounded-xl text-slate-700 dark:text-slate-300 hover:bg-white dark:hover:bg-slate-800 disabled:opacity-30 disabled:cursor-not-allowed transition-all"
                                        >
                                            <ChevronRight size={15} />
                                            <div role="tooltip" className="absolute top-full right-0 mt-2 opacity-0 pointer-events-none group-hover:opacity-100 transition-opacity duration-200 flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-slate-900/95 dark:bg-[#090e1a]/95 border border-slate-700/80 text-white text-[11px] font-sans font-medium whitespace-nowrap shadow-xl z-[120]">
                                                <span>Siguiente entrega</span>
                                                <kbd className="px-1 text-[9px] font-mono bg-white/10 rounded">→</kbd>
                                            </div>
                                        </button>
                                    </div>
                                ) : null
                            )}

                            {/* Right Actions */}
                            <div className="flex items-center gap-2 shrink-0">
                                {viewMode === "code_diff" && (
                                    <button
                                        onClick={() => setIsUltraWide(!isUltraWide)}
                                        aria-label={isUltraWide ? "Ajustar ancho a 94%" : "Expandir ancho a 98%"}
                                        className="group relative p-2 rounded-xl border border-slate-300 dark:border-slate-700 bg-slate-100 dark:bg-[#1a2234] text-slate-700 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-700 active:scale-95 transition-all shadow-sm"
                                    >
                                        {isUltraWide ? <Minimize2 size={16} className="text-cyan-400" /> : <Maximize2 size={16} className="text-cyan-400" />}
                                        <div role="tooltip" className="absolute top-full right-0 mt-2 opacity-0 pointer-events-none group-hover:opacity-100 transition-opacity duration-200 flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-slate-900/95 dark:bg-[#090e1a]/95 border border-slate-700/80 text-white text-xs font-sans font-medium whitespace-nowrap shadow-2xl z-[120]">
                                            <span>{isUltraWide ? "Ajustar ancho (94% pantalla)" : "Modo Ultra-Ancho (98% pantalla)"}</span>
                                        </div>
                                    </button>
                                )}

                                {/* Botón de alternancia entre reporte y visualizador diff */}
                                <button
                                    onClick={() => {
                                        if (viewMode === "report") {
                                            setViewMode("code_diff");
                                            const repId = typeof comparison.id === "string" ? parseInt(comparison.id, 10) : comparison.id;
                                            if (!isNaN(repId)) {
                                                fetchCode(repId);
                                            }
                                        } else {
                                            setViewMode("report");
                                        }
                                    }}
                                    aria-label={viewMode === "report" ? "Abrir comparación diff" : "Ver reporte completo"}
                                    className="group relative p-2 rounded-xl border border-slate-300 dark:border-slate-700 bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-200 active:scale-95 transition-all shadow-sm"
                                >
                                    {viewMode === "report" ? (
                                        <Code2 size={16} className="text-cyan-500" />
                                    ) : (
                                        <FileText size={16} className="text-violet-400" />
                                    )}
                                    <div role="tooltip" className="absolute top-full right-0 mt-2 opacity-0 pointer-events-none group-hover:opacity-100 transition-opacity duration-200 flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-slate-900/95 dark:bg-[#090e1a]/95 border border-slate-700/80 text-white text-xs font-sans font-medium whitespace-nowrap shadow-2xl z-[120]">
                                        <span>{viewMode === "report" ? "Abrir cotejo de código (Diff Synthwave '84)" : "Ver reporte técnico completo"}</span>
                                    </div>
                                </button>
                            </div>
                        </div>

                        {/* Hero Metrics HUD Telemetry Bar (Exclusive in Code Diff Mode) */}
                        {viewMode === "code_diff" && (
                            <div className="px-5 sm:px-8 py-3 bg-slate-100/90 dark:bg-[#0a0f1d] border-b border-slate-200 dark:border-[#1a2337] flex items-center justify-between gap-4 overflow-x-auto shrink-0 scrollbar-none">
                                <div className="flex items-center gap-5 sm:gap-8 lg:gap-10">
                                    {/* Metric 1: Global Similarity (Hero) */}
                                    <div className="flex items-center gap-3">
                                        <div className="flex flex-col">
                                            <div className="flex items-baseline gap-2">
                                                <span className={`text-2xl sm:text-3xl lg:text-4xl font-black font-mono tracking-tight ${auditInfo.color}`}>
                                                    {overallScore}%
                                                </span>
                                                <span className={`text-[10px] font-extrabold uppercase tracking-wider px-2 py-0.5 rounded-md border font-sans ${
                                                    dictamenRaw === 'INTEGRO' || dictamenRaw === 'SIN_ALERTAS'
                                                        ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30'
                                                        : 'bg-amber-500/10 text-amber-400 border-amber-500/30'
                                                }`}>
                                                    {auditInfo.label}
                                                </span>
                                            </div>
                                            <span className="text-[10px] uppercase tracking-wider font-bold text-slate-500 dark:text-slate-400 mt-0.5">
                                                Similitud Global
                                            </span>
                                        </div>
                                    </div>

                                    {/* Metric 2: Canal A (Semántica DFG) */}
                                    <div className="flex flex-col border-l border-slate-300/70 dark:border-slate-800/90 pl-5 sm:pl-8">
                                        <div className="flex items-baseline gap-1">
                                            <span className="text-xl sm:text-2xl lg:text-3xl font-black font-mono text-cyan-500 dark:text-cyan-400 tracking-tight">
                                                {semanticPct}%
                                            </span>
                                        </div>
                                        <span className="text-[10px] uppercase tracking-wider font-bold text-slate-500 dark:text-slate-400 mt-0.5">
                                            Semántica (Grafo DFG)
                                        </span>
                                    </div>

                                    {/* Metric 3: Canal B (Estilometría IA) */}
                                    <div className="flex flex-col border-l border-slate-300/70 dark:border-slate-800/90 pl-5 sm:pl-8">
                                        <div className="flex items-baseline gap-1">
                                            <span className="text-xl sm:text-2xl lg:text-3xl font-black font-mono text-violet-500 dark:text-violet-400 tracking-tight">
                                                {aiPct}%
                                            </span>
                                        </div>
                                        <span className="text-[10px] uppercase tracking-wider font-bold text-slate-500 dark:text-slate-400 mt-0.5">
                                            Sintaxis IA (CharCNN)
                                        </span>
                                    </div>

                                    {/* Metric 4: Discrepancia Asimétrica */}
                                    <div className="flex flex-col border-l border-slate-300/70 dark:border-slate-800/90 pl-5 sm:pl-8">
                                        <div className="flex items-baseline gap-1">
                                            <span className="text-xl sm:text-2xl lg:text-3xl font-black font-mono text-amber-500 dark:text-amber-300 tracking-tight">
                                                {comparison.discrepancia_score ?? (semanticPct * aiPct / 10000).toFixed(2)}
                                            </span>
                                        </div>
                                        <span className="text-[10px] uppercase tracking-wider font-bold text-slate-500 dark:text-slate-400 mt-0.5">
                                            Discrepancia
                                        </span>
                                    </div>
                                </div>

                                {/* HITL Assistant Tag */}
                                <div className="hidden xl:flex items-center gap-2 px-3 py-1.5 rounded-xl bg-slate-200/50 dark:bg-[#12192b] border border-slate-300/50 dark:border-slate-800 text-[11px] text-slate-400 font-sans">
                                    <Sparkles size={13} className="text-cyan-400 shrink-0" />
                                    <span>Telemetría HITL</span>
                                </div>
                            </div>
                        )}

                        {/* Header (solo en modo reporte completo) */}
                        {viewMode === "report" && (
                            <div className="px-10 pt-8 pb-6 flex items-start justify-between shrink-0">
                                <div>
                                    <h2 className="text-3xl font-display font-black text-slate-900 dark:text-white tracking-tight">
                                        Reporte de similitud
                                    </h2>
                                    <div className="flex items-center gap-4 mt-2 text-sm text-slate-600 dark:text-slate-400 font-medium">
                                        <span>Proyecto: {comparison.title}</span>
                                        <span className="w-1 h-1 rounded-full bg-slate-400 dark:bg-slate-600"></span>
                                        <span>14 de Abril, 2026</span>
                                    </div>
                                </div>
                                <div className="flex items-center gap-2 bg-slate-100 dark:bg-[#1a2031] border border-slate-200 dark:border-[#2b3346] px-4 py-2 rounded-full">
                                    <div className="w-2 h-2 rounded-full bg-graphito-blue"></div>
                                    <span className="text-xs font-bold text-slate-700 dark:text-slate-300">Análisis completado</span>
                                </div>
                            </div>
                        )}

                        {/* Body */}
                        <div ref={bodyContainerRef} className={`flex-1 overflow-y-auto ${viewMode === 'code_diff' ? 'p-3' : 'px-10 pb-8'} scrollbar-thin scrollbar-thumb-slate-300 dark:scrollbar-thumb-[#2b3346] scrollbar-track-transparent`}>
                            {viewMode === "code_diff" ? (
                                <div className="flex flex-col h-full">
                                    {/* Visualizador Diff Synthwave '84 */}
                                    {isLoadingCode ? (
                                        <div className="flex flex-col items-center justify-center py-28 text-slate-400">
                                            <div className="w-8 h-8 border-2 border-fuchsia-400 border-t-transparent rounded-full animate-spin mb-3" />
                                            <span className="text-xs font-mono">Cargando códigos fuente para cotejo diff...</span>
                                        </div>
                                    ) : (
                                        <div className="flex-1 min-h-[520px]">
                                            <SideBySideDiffViewer
                                                referenceCode={codeData?.reference_code || ""}
                                                studentCode={codeData?.student_code || ""}
                                                referenceAuthor={codeData?.reference_author}
                                                studentAuthor={codeData?.student_author}
                                                language={codeData?.language || "c"}
                                                reportId={typeof comparison.id === "string" ? parseInt(comparison.id, 10) : (comparison.id ?? 1)}
                                                comments={comments}
                                                onAddComment={handleAddComment}
                                                onDeleteComment={handleDeleteComment}
                                                isSubmittingComment={isSubmittingComment}
                                            />
                                        </div>
                                    )}
                                </div>
                            ) : (
                                <>
                                    {/* DSS Institutional Banner */}
                                    <div className="flex items-center gap-3 px-5 py-3 mb-6 bg-blue-500/10 border border-blue-500/25 rounded-2xl text-xs font-medium text-blue-700 dark:text-blue-200">
                                        <Info size={18} className="shrink-0 text-blue-500 dark:text-blue-400" />
                                        <span><strong>Sistema de Soporte a la Decisión (HITL):</strong> Graphito provee métricas periciales automatizadas sin emitir sentencias disciplinarias. La evaluación y calificación final corresponden al criterio pedagógico del profesor.</span>
                                    </div>

                            <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">

                                {/* Left Column: Big Chart */}
                                <div className="lg:col-span-4 flex flex-col items-center justify-center p-8 bg-slate-50 dark:bg-[#121827]/40 border border-slate-200 dark:border-[#2b3346]/60 rounded-3xl h-full">

                                    {/* Circular Graph */}
                                    <div className="relative w-64 h-64 flex items-center justify-center">
                                        {/* Background Circle */}
                                        <svg className="w-full h-full transform -rotate-90">
                                            <circle
                                                cx="128"
                                                cy="128"
                                                r={radius}
                                                className="stroke-slate-200 dark:stroke-[#2b3346] fill-none"
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
                                            <span className="text-5xl font-black text-slate-900 dark:text-white tracking-tight">
                                                {overallScore}%
                                            </span>
                                            <span className={`text-xs font-bold uppercase tracking-wider mt-1.5 ${auditInfo.color}`}>
                                                {auditInfo.label}
                                            </span>
                                        </div>
                                    </div>

                                    <h3 className="text-lg font-bold text-slate-900 dark:text-white mt-8 mb-2">Similitud total</h3>
                                    <p className="text-sm text-center text-slate-600 dark:text-slate-400">
                                        Se detectó una coincidencia {overallScore > 50 ? 'significativa' : 'menor'} en la estructura lógica central del código analizado.
                                    </p>
                                </div>

                                {/* Right Column: Breakdown & Interpretation */}
                                <div className="lg:col-span-8 flex flex-col gap-6">

                                    {/* Top row: Two metric cards */}
                                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6 p-1">

                                        {/* Stylometry Card */}
                                        <div className="bg-slate-50 dark:bg-[#121827]/40 border border-slate-200 dark:border-[#2b3346]/60 rounded-3xl p-6 hover:bg-slate-100/50 dark:hover:bg-[#121827]/60 transition-colors">
                                            <div className="flex items-center gap-3 mb-6">
                                                <div className="w-10 h-10 rounded-xl bg-graphito-violet/10 flex items-center justify-center text-graphito-violet">
                                                    <Settings size={20} />
                                                </div>
                                                <h4 className="font-bold text-slate-900 dark:text-white">Análisis estilométrico</h4>
                                            </div>

                                            <div className="space-y-4">
                                                <div>
                                                    <div className="flex justify-between text-xs font-bold text-slate-600 dark:text-slate-400 mb-2">
                                                        <span>Probabilidad de IA</span>
                                                        <span className="text-slate-900 dark:text-white">{aiPct}%</span>
                                                    </div>
                                                    <div className="h-1.5 w-full bg-slate-200 dark:bg-[#2b3346]/60 rounded-full overflow-hidden">
                                                        <div
                                                            className="h-full bg-graphito-violet rounded-full transition-all duration-1000 ease-out"
                                                            style={{ width: isAnimating ? `${aiPct}%` : '0%' }}
                                                        ></div>
                                                    </div>
                                                </div>

                                                <ul className="space-y-3 mt-6">
                                                    {comparison.indicadores && comparison.indicadores.length > 0 ? (
                                                        comparison.indicadores.map((ind, idx) => (
                                                            <li key={idx} className="flex items-start gap-2.5 text-xs text-slate-700 dark:text-slate-300">
                                                                <CheckCircle2 size={16} className={`${ind.severidad === 'ALTA' || ind.severidad === 'CRITICA' ? 'text-orange-500 dark:text-orange-400' : 'text-slate-400 dark:text-slate-500'} shrink-0 mt-0.5`} />
                                                                <span><strong className="text-slate-900 dark:text-white">{ind.tipo_alerta}:</strong> {ind.descripcion}</span>
                                                            </li>
                                                        ))
                                                    ) : (
                                                        <>
                                                            <li className="flex items-start gap-2.5 text-xs text-slate-700 dark:text-slate-300">
                                                                <CheckCircle2 size={16} className="text-slate-400 dark:text-slate-500 shrink-0" />
                                                                <span>Nomenclatura y patrones sintácticos analizados con CharCNN.</span>
                                                            </li>
                                                            <li className="flex items-start gap-2.5 text-xs text-slate-700 dark:text-slate-300">
                                                                <CheckCircle2 size={16} className="text-slate-400 dark:text-slate-500 shrink-0" />
                                                                <span>Estructura léxica y regularidad de comentarios evaluada.</span>
                                                            </li>
                                                        </>
                                                    )}
                                                </ul>
                                            </div>
                                        </div>

                                        {/* Semantic Card */}
                                        <div className="bg-slate-50 dark:bg-[#121827]/40 border border-slate-200 dark:border-[#2b3346]/60 rounded-3xl p-6 hover:bg-slate-100/50 dark:hover:bg-[#121827]/60 transition-colors">
                                            <div className="flex items-center gap-3 mb-6">
                                                <div className="w-10 h-10 rounded-xl bg-graphito-blue/10 flex items-center justify-center text-graphito-blue">
                                                    <PlayCircle size={20} />
                                                </div>
                                                <h4 className="font-bold text-slate-900 dark:text-white">Análisis semántico</h4>
                                            </div>

                                            <div className="space-y-4">
                                                <div>
                                                    <div className="flex justify-between text-xs font-bold text-slate-600 dark:text-slate-400 mb-2">
                                                        <span>Similitud de flujo DFG</span>
                                                        <span className="text-slate-900 dark:text-white">{semanticPct}%</span>
                                                    </div>
                                                    <div className="h-1.5 w-full bg-slate-200 dark:bg-[#2b3346]/60 rounded-full overflow-hidden">
                                                        <div
                                                            className="h-full bg-graphito-blue rounded-full transition-all duration-1000 ease-out"
                                                            style={{ width: isAnimating ? `${semanticPct}%` : '0%' }}
                                                        ></div>
                                                    </div>
                                                </div>

                                                <ul className="space-y-3 mt-6">
                                                    <li className="flex items-start gap-2.5 text-xs text-slate-700 dark:text-slate-300">
                                                        <CheckCircle2 size={16} className="text-slate-400 dark:text-slate-500 shrink-0" />
                                                        <span>Grafo de flujo de datos (DFG) comparado contra soluciones canónicas.</span>
                                                    </li>
                                                    <li className="flex items-start gap-2.5 text-xs text-slate-700 dark:text-slate-300">
                                                        <CheckCircle2 size={16} className="text-slate-400 dark:text-slate-500 shrink-0" />
                                                        <span>Invarianza ante renombramiento de variables y reordenamiento de bloques.</span>
                                                    </li>
                                                </ul>
                                            </div>
                                        </div>

                                    </div>

                                    {/* Bottom row: AI Interpretation (Typewriter) */}
                                    <div className="bg-slate-50 dark:bg-[#121827]/60 border border-slate-200 dark:border-[#2b3346]/60 rounded-3xl p-6 flex-1 hover:border-slate-300 dark:hover:border-[#334155] transition-colors relative overflow-hidden group">
                                        <div
                                            className="absolute top-0 right-0 w-64 h-64 rounded-full -translate-y-1/2 translate-x-1/2 opacity-0 group-hover:opacity-100 transition-opacity duration-700 pointer-events-none"
                                            style={{
                                                background: "radial-gradient(circle, rgba(59, 130, 246, 0.12) 0%, rgba(59, 130, 246, 0.03) 40%, transparent 70%)"
                                            }}
                                        />

                                        <div className="flex items-center gap-4 mb-4">
                                            <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-graphito-blue to-graphito-violet flex items-center justify-center text-white shadow-lg shadow-graphito-blue/20">
                                                <Sparkles size={24} />
                                            </div>
                                            <h4 className="text-lg font-bold text-slate-900 dark:text-white">Interpretación del análisis</h4>
                                        </div>

                                        <div className="text-sm font-medium text-slate-700 dark:text-slate-300 leading-relaxed max-w-3xl whitespace-pre-line break-words format-text min-h-[120px]">
                                            {typewriterText}
                                            {/* Blinking cursor */}
                                            <span className="inline-block w-1.5 h-4 bg-graphito-blue ml-1 animate-pulse align-middle"></span>
                                        </div>
                                    </div>

                                </div>
                            </div>
                        </>
                    )}
                </div>

                        {/* Footer */}
                        <div className={`flex items-center justify-between ${viewMode === 'code_diff' ? 'px-6 py-2.5 bg-slate-50 dark:bg-[#0f1422]' : 'px-10 py-5 bg-slate-50 dark:bg-black/40'} border-t border-slate-200 dark:border-[#2b3346]/40 mt-auto shrink-0`}>
                            <div className="flex items-center gap-4 text-xs font-medium text-slate-500">
                                <span className="font-mono font-semibold text-slate-600 dark:text-slate-400">
                                    {comparison.id ? `REP_${comparison.id}` : 'REP_LIVE-RUN'}
                                </span>
                                <div className="hidden md:flex items-center gap-2.5 text-[11px] text-slate-400 border-l border-slate-300 dark:border-slate-800 pl-4 font-mono">
                                    <span><kbd className="px-1 py-0.2 bg-slate-200 dark:bg-slate-800 rounded border border-slate-300 dark:border-slate-700">←</kbd> <kbd className="px-1 py-0.2 bg-slate-200 dark:bg-slate-800 rounded border border-slate-300 dark:border-slate-700">→</kbd> navegar</span>
                                    <span>•</span>
                                    <span><kbd className="px-1 py-0.2 bg-slate-200 dark:bg-slate-800 rounded border border-slate-300 dark:border-slate-700">A</kbd> conforme</span>
                                    <span>•</span>
                                    <span><kbd className="px-1 py-0.2 bg-slate-200 dark:bg-slate-800 rounded border border-slate-300 dark:border-slate-700">R</kbd> aclaración</span>
                                    <span>•</span>
                                    <span><kbd className="px-1 py-0.2 bg-slate-200 dark:bg-slate-800 rounded border border-slate-300 dark:border-slate-700">Esc</kbd> cerrar</span>
                                </div>
                            </div>
                            <div className="flex items-center gap-2.5">
                                {/* Validar Conforme */}
                                <button
                                    onClick={() => handleVerdictAndAdvance("conforme")}
                                    aria-label="Validar Conforme: Autoría legítima (Atajo: A)"
                                    className="group relative p-2.5 rounded-xl border border-emerald-500/40 bg-emerald-500/10 text-emerald-500 dark:text-emerald-400 hover:bg-emerald-500/20 hover:border-emerald-500/60 active:scale-95 transition-all shadow-sm flex items-center justify-center"
                                >
                                    <ShieldCheck size={19} />
                                    <span className="absolute -top-1 -right-1 px-1 py-0.2 text-[8px] font-mono font-bold bg-emerald-500/30 text-emerald-700 dark:text-emerald-200 border border-emerald-500/50 rounded">A</span>
                                    <div role="tooltip" className="absolute bottom-full right-0 mb-2 opacity-0 pointer-events-none group-hover:opacity-100 transition-opacity duration-200 flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-slate-900/95 dark:bg-[#070c18]/95 border border-emerald-500/40 text-emerald-100 text-xs font-sans font-medium whitespace-nowrap shadow-2xl z-[150]">
                                        <span>Validar Conforme: Autoría legítima</span>
                                        <kbd className="px-1.5 py-0.5 text-[9px] font-mono bg-emerald-500/30 text-emerald-200 rounded border border-emerald-500/40">A</kbd>
                                    </div>
                                </button>

                                {/* Citar a Aclaración */}
                                <button
                                    onClick={() => handleVerdictAndAdvance("aclaracion")}
                                    aria-label="Citar a Aclaración: Defensa oral (Atajo: R)"
                                    className="group relative p-2.5 rounded-xl border border-amber-500/40 bg-amber-500/10 text-amber-500 dark:text-amber-400 hover:bg-amber-500/20 hover:border-amber-500/60 active:scale-95 transition-all shadow-sm flex items-center justify-center"
                                >
                                    <UserCheck size={19} />
                                    <span className="absolute -top-1 -right-1 px-1 py-0.2 text-[8px] font-mono font-bold bg-amber-500/30 text-amber-700 dark:text-amber-200 border border-amber-500/50 rounded">R</span>
                                    <div role="tooltip" className="absolute bottom-full right-0 mb-2 opacity-0 pointer-events-none group-hover:opacity-100 transition-opacity duration-200 flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-slate-900/95 dark:bg-[#070c18]/95 border border-amber-500/40 text-amber-100 text-xs font-sans font-medium whitespace-nowrap shadow-2xl z-[150]">
                                        <span>Citar a Aclaración: Programar defensa oral</span>
                                        <kbd className="px-1.5 py-0.5 text-[9px] font-mono bg-amber-500/30 text-amber-200 rounded border border-amber-500/40">R</kbd>
                                    </div>
                                </button>

                                {/* Descargar PDF */}
                                <button
                                    onClick={handleDownloadPdf}
                                    disabled={isDownloadingPdf || !comparison.id}
                                    aria-label="Descargar reporte en PDF"
                                    className="group relative p-2.5 rounded-xl border border-slate-300 dark:border-slate-700 bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-700 hover:text-white active:scale-95 focus:outline-none focus-visible:ring-2 focus-visible:ring-slate-400 disabled:opacity-50 disabled:cursor-not-allowed transition-all shadow-sm flex items-center justify-center"
                                >
                                    {isDownloadingPdf ? (
                                        <div className="w-[19px] h-[19px] border-2 border-slate-400 dark:border-white/30 border-t-graphito-blue dark:border-t-white rounded-full animate-spin" />
                                    ) : (
                                        <Download size={19} />
                                    )}
                                    <div role="tooltip" className="absolute bottom-full right-0 mb-2 opacity-0 pointer-events-none group-hover:opacity-100 transition-opacity duration-200 flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-slate-900/95 dark:bg-[#070c18]/95 border border-slate-700/80 text-white text-xs font-sans font-medium whitespace-nowrap shadow-2xl z-[150]">
                                        <span>Descargar Informe Pericial en PDF</span>
                                    </div>
                                </button>

                                {/* Cerrar */}
                                <button
                                    onClick={onClose}
                                    aria-label="Cerrar visor (Esc)"
                                    className="group relative p-2.5 rounded-xl border border-slate-300 dark:border-slate-700 bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 hover:text-rose-500 hover:border-rose-500/40 hover:bg-rose-500/10 active:scale-95 transition-all shadow-sm flex items-center justify-center"
                                >
                                    <X size={19} />
                                    <div role="tooltip" className="absolute bottom-full right-0 mb-2 opacity-0 pointer-events-none group-hover:opacity-100 transition-opacity duration-200 flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-slate-900/95 dark:bg-[#070c18]/95 border border-slate-700/80 text-white text-xs font-sans font-medium whitespace-nowrap shadow-2xl z-[150]">
                                        <span>Cerrar visor</span>
                                        <kbd className="px-1.5 py-0.5 text-[9px] font-mono bg-white/10 text-white rounded border border-white/20">Esc</kbd>
                                    </div>
                                </button>
                            </div>
                        </div>

                    </div>
                </AuthCard>
            </div>
        </div>
    );
}
