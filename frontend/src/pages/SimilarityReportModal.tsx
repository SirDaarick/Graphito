import { useState, useEffect, useMemo, useRef } from "react";
import { ArrowLeft, Code2, Download, ShieldCheck, UserCheck, ChevronLeft, ChevronRight, X } from "lucide-react";
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

type ViewMode = "report" | "code_diff";
type CodeStatus = "idle" | "loading" | "error" | "ready";

const KBD = "px-1 py-0.2 bg-slate-200 dark:bg-slate-800 rounded border border-slate-300 dark:border-slate-700";

const FOOTER_TOOLTIP =
    "absolute bottom-full right-0 mb-2 opacity-0 pointer-events-none group-hover:opacity-100 group-focus-visible:opacity-100 transition-opacity duration-200 flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-slate-900/95 dark:bg-[#070c18]/95 border border-slate-700/80 text-white text-xs font-sans font-medium whitespace-nowrap shadow-2xl z-[150]";

function parseReportId(id: string | number | undefined): number | null {
    if (id === undefined || id === null || id === "") return null;
    const n = typeof id === "string" ? parseInt(id, 10) : id;
    return Number.isNaN(n) ? null : n;
}

/** True when the viewport is at least `minWidth` px wide; used to size the code panes (side by side vs stacked). */
function useMinWidth(minWidth: number): boolean {
    const query = `(min-width: ${minWidth}px)`;
    const [matches, setMatches] = useState(() => typeof window !== "undefined" && window.matchMedia(query).matches);
    useEffect(() => {
        const mql = window.matchMedia(query);
        const onChange = () => setMatches(mql.matches);
        onChange();
        mql.addEventListener("change", onChange);
        return () => mql.removeEventListener("change", onChange);
    }, [query]);
    return matches;
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
    const [viewMode, setViewMode] = useState<ViewMode>("report");
    const [codeData, setCodeData] = useState<CodeData | null>(null);
    const [codeStatus, setCodeStatus] = useState<CodeStatus>("idle");
    const [comments, setComments] = useState<ComentarioRevisionItem[]>([]);
    const [isSubmittingComment, setIsSubmittingComment] = useState(false);
    const [isNavigating, setIsNavigating] = useState(false);
    const [triageToast, setTriageToast] = useState<{ message: string; type: "success" | "warning" } | null>(null);
    const backdropRef = useRef<HTMLDivElement>(null);
    const contentRef = useRef<HTMLDivElement>(null);
    const bodyContainerRef = useRef<HTMLDivElement>(null);
    const viewCodeButtonRef = useRef<HTMLButtonElement>(null);
    const backToSummaryRef = useRef<HTMLButtonElement>(null);
    /** Report id whose code was requested last; guards against late responses and avoids refetching. */
    const requestedCodeFor = useRef<number | null>(null);
    const previousViewMode = useRef<ViewMode>("report");
    const isWide = useMinWidth(768);

    const reportId = parseReportId(comparison?.id);
    const currentIndex = submissions && comparison
        ? submissions.findIndex((s) => String(s.id) === String(comparison.id))
        : -1;
    const hasNext = Boolean(submissions && currentIndex >= 0 && currentIndex < submissions.length - 1);
    const hasPrev = Boolean(submissions && currentIndex > 0);
    const inCodeView = viewMode === "code_diff";

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
            if (reportId !== null) {
                api.analysis.updateVerdict(reportId, isConforme ? "APROBADO" : "EN_DUDA").catch((err) => {
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

    const loadCode = (repId: number) => {
        requestedCodeFor.current = repId;
        setCodeStatus("loading");
        const isCurrent = () => requestedCodeFor.current === repId;

        api.comments
            .list(repId)
            .then((list) => isCurrent() && setComments(list))
            .catch(() => isCurrent() && setComments([]));

        api.analysis
            .getCode(repId)
            .then((data) => {
                if (!isCurrent()) return;
                setCodeData({
                    reference_code: data.reference_code || "// Sin código de referencia registrado",
                    student_code: data.student_code || "// Sin código de entrega registrado",
                    reference_author: data.reference_author || "Docente (Referencia)",
                    student_author: data.student_author || comparison?.title || "Estudiante",
                    language: data.language || "c",
                    indicadores: data.indicadores,
                });
                setCodeStatus("ready");
            })
            .catch((err) => {
                if (!isCurrent()) return;
                console.warn("No se pudo obtener el código desde la API:", err);
                setCodeData(null);
                setCodeStatus("error");
            });
    };

    // Reset everything tied to a report when it changes or the modal closes.
    useEffect(() => {
        requestedCodeFor.current = null;
        setCodeData(null);
        setCodeStatus("idle");
        setComments([]);
        if (!isOpen) setViewMode("report");
    }, [isOpen, reportId]);

    // The code is fetched lazily, the first time the code view is opened for a report.
    useEffect(() => {
        if (!isOpen || !inCodeView || reportId === null) return;
        if (requestedCodeFor.current === reportId) return;
        loadCode(reportId);
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [isOpen, inCodeView, reportId]);

    // Keep keyboard focus on the control that replaces the one just used.
    useEffect(() => {
        if (previousViewMode.current === viewMode) return;
        previousViewMode.current = viewMode;
        if (viewMode === "code_diff") backToSummaryRef.current?.focus();
        else viewCodeButtonRef.current?.focus();
    }, [viewMode]);

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
                // An open "?" popover handles Escape first (capture phase); here it steps back or closes.
                if (inCodeView) setViewMode("report");
                else onClose();
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
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [isOpen, currentIndex, hasNext, hasPrev, submissions, isNavigating, inCodeView]);

    const handleAddComment = async (lineNum: number | null, text: string) => {
        if (reportId === null) return;

        setIsSubmittingComment(true);
        try {
            const newComment = await api.comments.create(reportId, {
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
                    reporte_id: reportId,
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
        if (reportId !== null) {
            try {
                await api.comments.delete(reportId, commentId);
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
        if (reportId === null) return;
        try {
            setIsDownloadingPdf(true);
            await api.analysis.downloadPdf(reportId, `reporte_integridad_${reportId}.pdf`);
        } catch (err) {
            console.error("Error al descargar PDF:", err);
            alert("No se pudo generar o descargar el reporte PDF.");
        } finally {
            setIsDownloadingPdf(false);
        }
    };

    if (!shouldRender || !comparison) return null;

    const isSample = comparison.engine === "stub" || comparison.engine === "demo";
    const navButton =
        "p-2 rounded-xl text-slate-700 dark:text-slate-300 hover:bg-white dark:hover:bg-slate-800 disabled:opacity-30 disabled:cursor-not-allowed transition-all focus:outline-none focus-visible:ring-2 focus-visible:ring-graphito-blue/60";
    const headerButton =
        "p-2 rounded-xl text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white hover:bg-slate-200/60 dark:hover:bg-slate-800/80 active:scale-95 transition-all shrink-0 focus:outline-none focus-visible:ring-2 focus-visible:ring-graphito-blue/60";
    // Two panes side by side on wide screens; stacked (two shorter panes) on phones.
    const paneHeight = isWide ? "calc(92dvh - 220px)" : "clamp(200px, 30dvh, 320px)";

    return (
        <div className="fixed inset-0 z-[100] flex items-center justify-center p-2 sm:p-4">
            {/* Backdrop */}
            <div
                ref={backdropRef}
                className="absolute inset-0 bg-black/80 backdrop-blur-sm opacity-0"
                onClick={onClose}
            />

            {/* Modal Content: compact for the summary, wide for the code comparison */}
            <div
                ref={contentRef}
                role="dialog"
                aria-modal="true"
                aria-labelledby="report-modal-title"
                className={`relative w-full opacity-0 ${inCodeView ? "max-w-[1600px]" : "max-w-4xl"}`}
            >
                <AuthCard className="w-full !p-0 !rounded-3xl overflow-hidden border-slate-200 dark:border-[#2b3346]/60 bg-white/95 dark:bg-[#0f1522]/90">
                    <div className={`flex flex-col relative ${inCodeView ? "h-[92dvh]" : "max-h-[92dvh]"}`}>
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
                                {inCodeView ? (
                                    <button
                                        ref={backToSummaryRef}
                                        onClick={() => setViewMode("report")}
                                        className="flex items-center gap-1.5 px-2.5 py-2 rounded-xl text-sm font-semibold text-slate-700 dark:text-slate-200 hover:bg-slate-200/60 dark:hover:bg-slate-800/80 active:scale-95 transition-all shrink-0 focus:outline-none focus-visible:ring-2 focus-visible:ring-graphito-blue/60"
                                    >
                                        <ArrowLeft size={16} aria-hidden="true" />
                                        <span className="hidden sm:inline">Volver al resumen</span>
                                        <span className="sm:hidden">Resumen</span>
                                    </button>
                                ) : (
                                    <button onClick={onClose} aria-label="Volver a la biblioteca" className={headerButton}>
                                        <ArrowLeft size={18} />
                                    </button>
                                )}
                                <div className="min-w-0">
                                    <h2 id="report-modal-title" className="text-base sm:text-xl font-display font-black text-slate-900 dark:text-white tracking-tight leading-tight">
                                        {inCodeView ? "Comparación de código" : "Reporte de similitud"}
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

                        {/* Body: the summary by default; the code comparison only when asked for */}
                        <div
                            ref={bodyContainerRef}
                            className={`flex-1 overflow-y-auto scrollbar-thin scrollbar-thumb-slate-300 dark:scrollbar-thumb-[#2b3346] scrollbar-track-transparent ${
                                inCodeView ? "p-3 sm:p-4" : "p-4 sm:p-6"
                            }`}
                        >
                            {inCodeView ? (
                                <CodeView
                                    status={codeStatus}
                                    codeData={codeData}
                                    reportId={reportId ?? 1}
                                    comments={comments}
                                    onAddComment={handleAddComment}
                                    onDeleteComment={handleDeleteComment}
                                    isSubmittingComment={isSubmittingComment}
                                    evidence={lineEvidence}
                                    paneHeight={paneHeight}
                                    onRetry={() => reportId !== null && loadCode(reportId)}
                                />
                            ) : (
                                <div className="flex flex-col gap-5">
                                    <ReportMetrics report={comparison} animate={isAnimating} />
                                    <div className="flex sm:justify-end">
                                        <button
                                            ref={viewCodeButtonRef}
                                            onClick={() => setViewMode("code_diff")}
                                            className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-5 py-3 rounded-xl bg-graphito-blue text-white text-sm font-semibold shadow-sm hover:brightness-110 active:scale-[0.98] transition-all focus:outline-none focus-visible:ring-2 focus-visible:ring-graphito-blue/60 focus-visible:ring-offset-2 dark:focus-visible:ring-offset-[#0f1522]"
                                        >
                                            <Code2 size={18} aria-hidden="true" />
                                            Ver comparación de código
                                        </button>
                                    </div>
                                </div>
                            )}
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
                                <span><kbd className={KBD}>Esc</kbd> {inCodeView ? "volver al resumen" : "cerrar"}</span>
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
                                    disabled={isDownloadingPdf || reportId === null}
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
                                    aria-label="Cerrar"
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

interface CodeViewProps {
    status: CodeStatus;
    codeData: CodeData | null;
    reportId: number;
    comments: ComentarioRevisionItem[];
    onAddComment: (lineNum: number | null, text: string) => Promise<void>;
    onDeleteComment: (commentId: number) => Promise<void>;
    isSubmittingComment: boolean;
    evidence: ReturnType<typeof evidenceByLine>;
    paneHeight: string;
    onRetry: () => void;
}

/** The optional second view: loading, error with retry, or the side-by-side comparison. */
function CodeView({ status, codeData, reportId, evidence, paneHeight, onRetry, ...viewer }: CodeViewProps) {
    if (status === "error") {
        return (
            <div role="alert" className="flex flex-col items-center justify-center gap-3 py-20 text-center">
                <p className="text-base font-semibold text-slate-900 dark:text-white">No se pudo cargar el código</p>
                <p className="max-w-sm text-sm text-slate-600 dark:text-slate-400">
                    Revisa tu conexión e inténtalo de nuevo. El resumen de la entrega sigue disponible.
                </p>
                <button
                    onClick={onRetry}
                    className="mt-1 rounded-xl border border-slate-300 bg-slate-100 px-4 py-2 text-sm font-semibold text-slate-800 transition-all hover:bg-slate-200 focus:outline-none focus-visible:ring-2 focus-visible:ring-graphito-blue/60 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-100 dark:hover:bg-slate-700"
                >
                    Reintentar
                </button>
            </div>
        );
    }

    if (status !== "ready" || !codeData) {
        return (
            <div className="flex flex-col items-center justify-center py-24 text-slate-500 dark:text-slate-400" role="status">
                <div className="w-8 h-8 border-2 border-graphito-blue border-t-transparent rounded-full animate-spin mb-3" />
                <span className="text-sm">Cargando el código de la entrega...</span>
            </div>
        );
    }

    return (
        <div>
            <SideBySideDiffViewer
                referenceCode={codeData.reference_code}
                studentCode={codeData.student_code}
                referenceAuthor={codeData.reference_author}
                studentAuthor={codeData.student_author}
                language={codeData.language}
                reportId={reportId}
                evidence={evidence}
                paneHeight={paneHeight}
                {...viewer}
            />
            {evidence.size > 0 && (
                <p className="mt-2 px-1 text-xs text-slate-500 dark:text-slate-400">
                    Las líneas resaltadas en amarillo tienen una observación: pasa el cursor o enfócalas con el teclado para leerla.
                </p>
            )}
        </div>
    );
}
