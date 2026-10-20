import { useState, useEffect, useMemo, useRef } from "react";
import { ArrowLeft, Download, ShieldCheck, UserCheck, ChevronLeft, ChevronRight, X } from "lucide-react";
import { useGSAP } from "@gsap/react";
import gsap from "gsap";
import { AuthCard } from "../components/layout/AuthCard";
import { api, IndicadorIntegridad, ReportScoring } from "../lib/api";
import { saveVerdict } from "../lib/verdicts";
import { evidenceByLine } from "../lib/evidence";
import { SideBySideDiffViewer, ComentarioRevisionItem } from "../components/code/SideBySideDiffViewer";
import { ReportMetrics } from "../components/report/ReportMetrics";

export interface IndicadorItem {
    id?: number;
    tipo_alerta: string;
    descripcion: string;
    severidad: "BAJA" | "MEDIA" | "ALTA" | "CRITICA" | string;
    numero_linea?: number | null;
    categoria?: string;
    origen?: string;
}

/** Report fields as returned by the API (nullable scores, provenance) plus display text. */
export interface ComparisonData extends ReportScoring {
    id?: string | number;
    title?: string;
    subtitle?: string;
    similarity?: number | null;
    indicadores?: IndicadorItem[];
}

interface SimilarityReportModalProps {
    isOpen: boolean;
    onClose: () => void;
    comparison: ComparisonData | null;
    submissions?: ComparisonData[];
    onSelectComparison?: (comparison: ComparisonData) => void;
}

interface CodeData {
    reference_code: string;
    student_code: string;
    reference_author: string;
    student_author: string;
    language: string;
    indicadores?: IndicadorIntegridad[];
}

const KBD = "px-1 py-0.2 bg-slate-200 dark:bg-slate-800 rounded border border-slate-300 dark:border-slate-700";

const FOOTER_TOOLTIP =
    "absolute bottom-full right-0 mb-2 opacity-0 pointer-events-none group-hover:opacity-100 group-focus-visible:opacity-100 transition-opacity duration-200 flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-slate-900/95 dark:bg-[#070c18]/95 border border-slate-700/80 text-white text-xs font-sans font-medium whitespace-nowrap shadow-2xl z-[150]";

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
    const [codeData, setCodeData] = useState<CodeData | null>(null);
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
            ? "Entrega marcada por el docente como revisada, sin observaciones."
            : "Entrega marcada por el docente para aclarar con el estudiante.";

        if (comparison?.id) {
            saveVerdict(comparison.id, isConforme ? "CONFORME" : "DUDA");
            const repId = typeof comparison.id === "string" ? parseInt(comparison.id, 10) : comparison.id;
            if (!isNaN(repId)) {
                api.analysis.updateVerdict(repId, isConforme ? "APROBADO" : "EN_DUDA").catch((err) => {
                    console.warn("No se pudo persistir el veredicto en backend:", err);
                });
            }
        }

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
                fetchCode(repId);
            }
        } else {
            setCodeData(null);
        }
    }, [isOpen, comparison?.id]);

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
                indicadores: data.indicadores,
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
                indicadores: [
                    {
                        tipo_alerta: "Estructura idéntica a la referencia",
                        descripcion: "Bucle iterativo con cálculo de punto medio idéntico a la referencia.",
                        severidad: "MEDIA",
                        numero_linea: 7,
                        categoria: "ISOMORFISMO_DFG",
                    },
                    {
                        tipo_alerta: "Estilo de código generado",
                        descripcion: "Nomenclatura y formateo afín a generadores LLM.",
                        severidad: "BAJA",
                        numero_linea: 4,
                        categoria: "ESTILO_LLM",
                    }
                ],
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
            gsap.fromTo(contentRef.current, { opacity: 0, scale: 0.97, y: 24 }, { opacity: 1, scale: 1, y: 0, duration: 0.35, ease: "power2.out" });
        } else {
            gsap.to(backdropRef.current, { opacity: 0, duration: 0.3, ease: "power2.in" });
            gsap.to(contentRef.current, { opacity: 0, scale: 0.97, y: 24, duration: 0.3, ease: "power2.in", onComplete: () => setShouldRender(false) });
        }
    }, [isOpen, shouldRender]);

    // Line-level evidence for the code view: the report's own rows, or the ones that came with the code.
    const lineEvidence = useMemo(() => {
        const own = comparison?.indicadores ?? [];
        return evidenceByLine(own.length > 0 ? own : codeData?.indicadores ?? []);
    }, [comparison?.indicadores, codeData?.indicadores]);

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

    const isSample = comparison.engine === "stub" || comparison.engine === "demo";
    const reportId = typeof comparison.id === "string" ? parseInt(comparison.id, 10) : (comparison.id ?? 1);
    const navButton =
        "p-2 rounded-xl text-slate-700 dark:text-slate-300 hover:bg-white dark:hover:bg-slate-800 disabled:opacity-30 disabled:cursor-not-allowed transition-all focus:outline-none focus-visible:ring-2 focus-visible:ring-graphito-blue/60";

    return (
        <div className="fixed inset-0 z-[100] flex items-center justify-center p-2 sm:p-4">
            {/* Backdrop */}
            <div
                ref={backdropRef}
                className="absolute inset-0 bg-black/80 backdrop-blur-sm opacity-0"
                onClick={onClose}
            />

            {/* Modal Content */}
            <div
                ref={contentRef}
                role="dialog"
                aria-modal="true"
                aria-labelledby="report-modal-title"
                className="relative w-full max-w-[1200px] opacity-0"
            >
                <AuthCard className="w-full !p-0 !rounded-3xl overflow-hidden border-slate-200 dark:border-[#2b3346]/60 bg-white/95 dark:bg-[#0f1522]/90">
                    <div className="flex flex-col max-h-[92dvh] relative">
                        {/* Floating Toast para Veredicto y Avance Ágil */}
                        {triageToast && (
                            <div
                                role="status"
                                className={`absolute top-16 left-1/2 -translate-x-1/2 z-50 px-5 py-2.5 rounded-2xl text-xs font-bold shadow-2xl border flex items-center gap-2.5 backdrop-blur-md transition-all ${
                                    triageToast.type === "success"
                                        ? "bg-emerald-950/95 text-emerald-200 border-emerald-500/50 shadow-emerald-950/60"
                                        : "bg-amber-950/95 text-amber-200 border-amber-500/50 shadow-amber-950/60"
                                }`}
                            >
                                {triageToast.type === "success" ? <ShieldCheck size={18} className="text-emerald-400" /> : <UserCheck size={18} className="text-amber-400" />}
                                <span>{triageToast.message}</span>
                                {hasNext && <span className="opacity-80 text-[10px] ml-1 bg-white/10 px-1.5 py-0.5 rounded">Pasando a la siguiente entrega</span>}
                            </div>
                        )}

                        {/* Top bar: back, title, submission carousel */}
                        <div className="flex items-center justify-between gap-3 px-4 sm:px-6 py-3 border-b border-slate-200 dark:border-[#2b3346]/40 bg-slate-50 dark:bg-[#0f1422] shrink-0">
                            <div className="flex items-center gap-3 min-w-0">
                                <button
                                    onClick={onClose}
                                    aria-label="Volver a la biblioteca"
                                    className="p-2 rounded-xl text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white hover:bg-slate-200/60 dark:hover:bg-slate-800/80 active:scale-95 transition-all shrink-0 focus:outline-none focus-visible:ring-2 focus-visible:ring-graphito-blue/60"
                                >
                                    <ArrowLeft size={18} />
                                </button>
                                <div className="min-w-0">
                                    <h2 id="report-modal-title" className="text-lg sm:text-xl font-display font-black text-slate-900 dark:text-white tracking-tight leading-tight">
                                        Reporte de similitud
                                    </h2>
                                    <p className="text-xs sm:text-sm text-slate-600 dark:text-slate-400 font-medium truncate">
                                        Entrega de {comparison.title}
                                    </p>
                                </div>
                            </div>

                            <div className="flex items-center gap-2 shrink-0">
                                {isSample && (
                                    <span className="hidden sm:inline px-3 py-1 rounded-full text-xs font-bold bg-amber-500/15 text-amber-700 dark:text-amber-400 border border-amber-500/40">
                                        Datos de ejemplo
                                    </span>
                                )}
                                {submissions && submissions.length > 0 && currentIndex >= 0 && (
                                    <div className="flex items-center gap-1 bg-slate-200/60 dark:bg-[#161d2d] px-1.5 py-1 rounded-2xl border border-slate-300/60 dark:border-[#2b3346]">
                                        <button
                                            onClick={() => navigateTo(currentIndex - 1)}
                                            disabled={!hasPrev || isNavigating}
                                            aria-label="Entrega anterior (flecha izquierda)"
                                            className={navButton}
                                        >
                                            <ChevronLeft size={16} />
                                        </button>
                                        <span className="text-xs font-bold text-slate-800 dark:text-slate-200 px-1 tabular-nums">
                                            {currentIndex + 1} de {submissions.length}
                                        </span>
                                        <button
                                            onClick={() => navigateTo(currentIndex + 1)}
                                            disabled={!hasNext || isNavigating}
                                            aria-label="Siguiente entrega (flecha derecha)"
                                            className={navButton}
                                        >
                                            <ChevronRight size={16} />
                                        </button>
                                    </div>
                                )}
                            </div>
                        </div>

                        {/* Body: metrics first on phones, code comparison large beside them on desktop */}
                        <div
                            ref={bodyContainerRef}
                            className="flex-1 overflow-y-auto p-3 sm:p-5 scrollbar-thin scrollbar-thumb-slate-300 dark:scrollbar-thumb-[#2b3346] scrollbar-track-transparent"
                        >
                            <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 lg:gap-5">
                                <div className="order-1 lg:order-2 lg:col-span-4">
                                    <ReportMetrics report={comparison} animate={isAnimating} />
                                </div>

                                <div className="order-2 lg:order-1 lg:col-span-8 min-w-0">
                                    {isLoadingCode ? (
                                        <div className="flex flex-col items-center justify-center py-24 text-slate-500 dark:text-slate-400" role="status">
                                            <div className="w-8 h-8 border-2 border-graphito-blue border-t-transparent rounded-full animate-spin mb-3" />
                                            <span className="text-sm">Cargando el código de la entrega...</span>
                                        </div>
                                    ) : (
                                        <div className="h-full">
                                            <SideBySideDiffViewer
                                                referenceCode={codeData?.reference_code || ""}
                                                studentCode={codeData?.student_code || ""}
                                                referenceAuthor={codeData?.reference_author}
                                                studentAuthor={codeData?.student_author}
                                                language={codeData?.language || "c"}
                                                reportId={reportId}
                                                comments={comments}
                                                onAddComment={handleAddComment}
                                                onDeleteComment={handleDeleteComment}
                                                isSubmittingComment={isSubmittingComment}
                                                evidence={lineEvidence}
                                                paneHeight="clamp(300px, 52vh, 560px)"
                                            />
                                            {lineEvidence.size > 0 && (
                                                <p className="mt-2 px-1 text-xs text-slate-500 dark:text-slate-400">
                                                    Las líneas resaltadas en amarillo tienen una observación: pasa el cursor o enfócalas con el teclado para leerla.
                                                </p>
                                            )}
                                        </div>
                                    )}
                                </div>
                            </div>
                        </div>

                        {/* Footer */}
                        <div className="flex items-center justify-between px-4 sm:px-6 py-3 bg-slate-50 dark:bg-[#0f1422] border-t border-slate-200 dark:border-[#2b3346]/40 shrink-0">
                            <div className="hidden md:flex items-center gap-2.5 text-[11px] text-slate-500 dark:text-slate-400">
                                <span><kbd className={KBD}>←</kbd> <kbd className={KBD}>→</kbd> navegar</span>
                                <span aria-hidden="true">•</span>
                                <span><kbd className={KBD}>A</kbd> sin observaciones</span>
                                <span aria-hidden="true">•</span>
                                <span><kbd className={KBD}>R</kbd> aclarar</span>
                                <span aria-hidden="true">•</span>
                                <span><kbd className={KBD}>Esc</kbd> cerrar</span>
                            </div>
                            <div className="flex items-center gap-2.5 ml-auto">
                                {/* Validar Conforme */}
                                <button
                                    onClick={() => handleVerdictAndAdvance("conforme")}
                                    aria-label="Marcar sin observaciones (tecla A)"
                                    className="group relative p-2.5 rounded-xl border border-emerald-500/40 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 hover:bg-emerald-500/20 hover:border-emerald-500/60 active:scale-95 transition-all shadow-sm flex items-center justify-center focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400/60"
                                >
                                    <ShieldCheck size={19} />
                                    <div role="tooltip" className={FOOTER_TOOLTIP}>
                                        <span>Marcar sin observaciones</span>
                                    </div>
                                </button>

                                {/* Citar a Aclaración */}
                                <button
                                    onClick={() => handleVerdictAndAdvance("aclaracion")}
                                    aria-label="Marcar para aclarar con el estudiante (tecla R)"
                                    className="group relative p-2.5 rounded-xl border border-amber-500/40 bg-amber-500/10 text-amber-600 dark:text-amber-400 hover:bg-amber-500/20 hover:border-amber-500/60 active:scale-95 transition-all shadow-sm flex items-center justify-center focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-400/60"
                                >
                                    <UserCheck size={19} />
                                    <div role="tooltip" className={FOOTER_TOOLTIP}>
                                        <span>Marcar para aclarar con el estudiante</span>
                                    </div>
                                </button>

                                {/* Descargar PDF */}
                                <button
                                    onClick={handleDownloadPdf}
                                    disabled={isDownloadingPdf || !comparison.id}
                                    aria-label="Descargar reporte en PDF"
                                    className="group relative p-2.5 rounded-xl border border-slate-300 dark:border-slate-700 bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-700 active:scale-95 focus:outline-none focus-visible:ring-2 focus-visible:ring-slate-400 disabled:opacity-50 disabled:cursor-not-allowed transition-all shadow-sm flex items-center justify-center"
                                >
                                    {isDownloadingPdf ? (
                                        <div className="w-[19px] h-[19px] border-2 border-slate-400 dark:border-white/30 border-t-graphito-blue dark:border-t-white rounded-full animate-spin" />
                                    ) : (
                                        <Download size={19} />
                                    )}
                                    <div role="tooltip" className={FOOTER_TOOLTIP}>
                                        <span>Descargar informe en PDF</span>
                                    </div>
                                </button>

                                {/* Cerrar */}
                                <button
                                    onClick={onClose}
                                    aria-label="Cerrar (Esc)"
                                    className="group relative p-2.5 rounded-xl border border-slate-300 dark:border-slate-700 bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 hover:text-rose-500 hover:border-rose-500/40 hover:bg-rose-500/10 active:scale-95 transition-all shadow-sm flex items-center justify-center focus:outline-none focus-visible:ring-2 focus-visible:ring-rose-400/60"
                                >
                                    <X size={19} />
                                    <div role="tooltip" className={FOOTER_TOOLTIP}>
                                        <span>Cerrar</span>
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
