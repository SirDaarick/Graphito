/**
 * @file SideBySideDiffViewer.tsx
 * @description Visor de código lado a lado para la revisión del docente.
 * 1. Entrega del estudiante a la izquierda; referencia del docente a la derecha.
 * 2. Cada panel se desplaza de forma independiente.
 * 3. Resaltado morado de las líneas que más influyen en el estilo, y de las líneas con una observación.
 * 4. Notas del docente (en línea y generales). Tema claro y oscuro.
 */

import React, { useId, useState, useRef, useMemo } from "react";
import { createPortal } from "react-dom";
import { MessageSquare, MessageSquarePlus, Plus, Trash2, X, Send, User, ChevronDown, ChevronUp } from "lucide-react";
import { SynthwaveLine } from "./SynthwaveHighlighter";
import type { LineEvidence } from "../../lib/evidence";
import { styleIntensityByLine, type LineaEstilo, type StyleIntensity } from "../../lib/styleAttribution";

export interface ComentarioRevisionItem {
    id: number;
    reporte_id: number;
    docente_id: number;
    numero_linea: number | null;
    contenido: string;
    created_at: string;
    autor_nombre?: string;
}

interface SideBySideDiffViewerProps {
    referenceCode: string;
    studentCode: string;
    referenceAuthor?: string;
    studentAuthor?: string;
    language?: string;
    reportId: number;
    comments: ComentarioRevisionItem[];
    onAddComment: (lineNum: number | null, text: string) => Promise<void>;
    onDeleteComment: (commentId: number) => Promise<void>;
    isSubmittingComment?: boolean;
    evidence?: Map<number, LineEvidence[]>;
    /** Style-attribution lines (approximation); undefined while unavailable. */
    styleLines?: LineaEstilo[];
    paneHeight?: string;
}

const STYLE_LEGEND =
    "Líneas que más influyen en el puntaje de estilo (aproximación: se quita cada línea y se mide el cambio).";

/** One violet family for everything that is highlighted: stronger bar and tint with more influence. */
const HIGHLIGHT_ROW_CLASS: Record<StyleIntensity, string> = {
    1: "bg-violet-500/10 hover:bg-violet-500/15 shadow-[inset_4px_0_0_rgba(124,58,237,0.5)]",
    2: "bg-violet-500/15 hover:bg-violet-500/20 shadow-[inset_4px_0_0_rgba(124,58,237,0.75)]",
    3: "bg-violet-500/20 hover:bg-violet-500/25 shadow-[inset_4px_0_0_rgba(124,58,237,1)]",
};

const PANEL_BORDER = "border-slate-200 dark:border-[#2d2244]";
const GUTTER_BORDER = "border-slate-200 dark:border-[#291e3e]";
const SCROLLBAR =
    "[scrollbar-width:thin] [scrollbar-color:rgba(139,92,246,0.5)_transparent] [&::-webkit-scrollbar]:h-2.5 [&::-webkit-scrollbar]:w-2.5 [&::-webkit-scrollbar-thumb]:rounded-full [&::-webkit-scrollbar-thumb]:bg-violet-400/50";

interface LineTip {
    line: number;
    top: number;
    bottom: number;
    left: number;
}

const NO_EVIDENCE: Map<number, LineEvidence[]> = new Map();
const TIP_WIDTH = 340;

export function SideBySideDiffViewer({
    referenceCode,
    studentCode,
    referenceAuthor = "Docente (Referencia Canónica)",
    studentAuthor = "Estudiante (Entrega)",
    language = "c",
    comments,
    onAddComment,
    onDeleteComment,
    isSubmittingComment = false,
    evidence = NO_EVIDENCE,
    styleLines,
    paneHeight,
}: SideBySideDiffViewerProps) {
    const styleIntensity = useMemo(() => styleIntensityByLine(styleLines), [styleLines]);

    const [tip, setTip] = useState<LineTip | null>(null);
    const tipId = useId();
    const tipRowRef = useRef<HTMLElement | null>(null);

    const [activeCommentLine, setActiveCommentLine] = useState<number | null>(null);
    const [commentText, setCommentText] = useState("");
    const [showGeneralComposer, setShowGeneralComposer] = useState(false);
    const [generalCommentText, setGeneralCommentText] = useState("");
    const [showGeneralCommentsTray, setShowGeneralCommentsTray] = useState(true);

    const refLines = useMemo(() => referenceCode.split("\n"), [referenceCode]);
    const stuLines = useMemo(() => studentCode.split("\n"), [studentCode]);

    const commentsByLine = useMemo(() => {
        const map = new Map<number, ComentarioRevisionItem[]>();
        comments.forEach((c) => {
            if (c.numero_linea !== null) {
                const list = map.get(c.numero_linea) || [];
                list.push(c);
                map.set(c.numero_linea, list);
            }
        });
        return map;
    }, [comments]);

    const generalComments = useMemo(
        () => comments.filter((c) => c.numero_linea === null),
        [comments]
    );

    const showTip = (line: number, row: HTMLElement, by: "mouse" | "focus") => {
        const rect = row.getBoundingClientRect();
        tipRowRef.current = by === "focus" ? row : null;
        setTip({ line, top: rect.top, bottom: rect.bottom, left: rect.left });
    };

    const syncTipOnScroll = () => {
        const row = tipRowRef.current;
        if (!row) {
            setTip(null);
            return;
        }
        const rect = row.getBoundingClientRect();
        setTip((prev) => (prev ? { ...prev, top: rect.top, bottom: rect.bottom, left: rect.left } : prev));
    };

    const handleSaveLineComment = async (lineNum: number) => {
        if (!commentText.trim()) return;
        await onAddComment(lineNum, commentText.trim());
        setCommentText("");
        setActiveCommentLine(null);
    };

    const handleSaveGeneralComment = async () => {
        if (!generalCommentText.trim()) return;
        await onAddComment(null, generalCommentText.trim());
        setGeneralCommentText("");
        setShowGeneralComposer(false);
    };

    const paneStyle = paneHeight && paneHeight !== "h-full" ? { height: paneHeight } : undefined;

    return (
        <div className="flex flex-col flex-1 h-full min-h-0 bg-white dark:bg-[#151020] rounded-2xl overflow-hidden border border-slate-200 dark:border-[#2d2244]/80 shadow-xl font-mono text-sm">
            {/* Top Accent Strip */}
            <div className="h-[2px] bg-gradient-to-r from-fuchsia-500/60 via-cyan-400/60 to-amber-300/60 shrink-0" />

            {/* Legend: what the highlighting means, and what it does not */}
            <ul
                aria-label="Leyenda del resaltado"
                className={`flex flex-wrap items-center gap-x-5 gap-y-1 px-4 py-2 bg-slate-50 dark:bg-[#1a1328] border-b ${PANEL_BORDER} font-sans text-xs text-slate-600 dark:text-slate-300 shrink-0`}
            >
                <li data-tour="style-lines" className="flex items-center gap-2">
                    <span className="inline-flex items-center gap-0.5" aria-hidden="true">
                        <span className="inline-block w-3.5 h-3.5 rounded-sm bg-violet-500/10 shadow-[inset_4px_0_0_rgba(124,58,237,0.5)]" />
                        <span className="inline-block w-3.5 h-3.5 rounded-sm bg-violet-500/15 shadow-[inset_4px_0_0_rgba(124,58,237,0.75)]" />
                        <span className="inline-block w-3.5 h-3.5 rounded-sm bg-violet-500/20 shadow-[inset_4px_0_0_rgba(124,58,237,1)]" />
                    </span>
                    {styleLines === undefined
                        ? "Aproximación de estilo no disponible por ahora."
                        : styleLines.length === 0
                        ? `${STYLE_LEGEND} Ninguna línea destaca en esta entrega.`
                        : STYLE_LEGEND}
                </li>
                <li className="text-slate-500 dark:text-slate-400">
                    Las líneas con una observación también se marcan en morado: pasa el cursor o enfócalas para leerla.
                </li>
            </ul>

            {/* General Comment Composer Dropdown */}
            {showGeneralComposer && (
                <div className="p-4 bg-fuchsia-50 dark:bg-[#231a38] border-b border-fuchsia-500/30 shrink-0">
                    <div className="flex items-center justify-between mb-2">
                        <span className="text-sm font-bold text-fuchsia-700 dark:text-fuchsia-300 flex items-center gap-1.5 font-sans">
                            <MessageSquare size={14} /> Nueva observación general
                        </span>
                        <button
                            onClick={() => setShowGeneralComposer(false)}
                            aria-label="Cerrar redactor"
                            className="text-slate-500 hover:text-slate-900 dark:text-slate-400 dark:hover:text-white"
                        >
                            <X size={16} />
                        </button>
                    </div>
                    <textarea
                        value={generalCommentText}
                        onChange={(e) => setGeneralCommentText(e.target.value)}
                        placeholder="Escribe una conclusión o justificación general para este análisis..."
                        className="w-full h-20 p-3 bg-white dark:bg-[#181324] border border-slate-300 dark:border-[#3d2f5a] rounded-xl text-slate-900 dark:text-slate-200 text-sm font-sans placeholder-slate-500 focus:outline-none focus:border-violet-500 transition-all resize-none"
                    />
                    <div className="flex justify-end gap-2 mt-2 font-sans">
                        <button
                            onClick={() => setShowGeneralComposer(false)}
                            className="px-3 py-1.5 text-sm text-slate-600 hover:text-slate-900 dark:text-slate-400 dark:hover:text-white"
                        >
                            Cancelar
                        </button>
                        <button
                            onClick={handleSaveGeneralComment}
                            disabled={isSubmittingComment || !generalCommentText.trim()}
                            className="flex items-center gap-1.5 px-4 py-1.5 rounded-lg bg-gradient-to-r from-fuchsia-500 to-indigo-600 text-white text-sm font-bold hover:opacity-90 active:scale-95 disabled:opacity-50"
                        >
                            <Send size={13} />
                            <span>Guardar nota general</span>
                        </button>
                    </div>
                </div>
            )}

            {/* General Comments Display */}
            {generalComments.length > 0 && (
                <div className={`px-6 py-2.5 bg-slate-50 dark:bg-[#1e1730] border-b ${PANEL_BORDER} font-sans shrink-0`}>
                    <button
                        onClick={() => setShowGeneralCommentsTray(!showGeneralCommentsTray)}
                        className="flex items-center justify-between w-full text-sm font-bold text-slate-700 dark:text-slate-300 hover:text-slate-900 dark:hover:text-white py-1"
                    >
                        <span className="flex items-center gap-2">
                            <span className="w-2 h-2 rounded-full bg-fuchsia-500 dark:bg-fuchsia-400" />
                            Notas generales del docente ({generalComments.length})
                        </span>
                        {showGeneralCommentsTray ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                    </button>

                    {showGeneralCommentsTray && (
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mt-2 max-h-40 overflow-y-auto">
                            {generalComments.map((gc) => (
                                <div
                                    key={gc.id}
                                    className="p-3 bg-white dark:bg-[#261d3c] border border-fuchsia-500/25 rounded-xl relative group text-sm"
                                >
                                    <div className="flex items-center justify-between mb-1 text-xs text-slate-500 dark:text-slate-400">
                                        <span className="font-semibold text-fuchsia-700 dark:text-fuchsia-300 flex items-center gap-1">
                                            <User size={12} /> {gc.autor_nombre || "Docente"}
                                        </span>
                                        <button
                                            onClick={() => onDeleteComment(gc.id)}
                                            className="text-slate-500 hover:text-rose-500 opacity-0 group-hover:opacity-100 focus-visible:opacity-100 transition-opacity"
                                            title="Eliminar comentario"
                                            aria-label="Eliminar comentario"
                                        >
                                            <Trash2 size={14} />
                                        </button>
                                    </div>
                                    <p className="text-slate-800 dark:text-slate-200 whitespace-pre-wrap leading-relaxed">{gc.contenido}</p>
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            )}

            {/* Column Headers: the student leads; the reference is context */}
            <div className={`grid grid-cols-1 md:grid-cols-2 border-b ${PANEL_BORDER} bg-slate-50 dark:bg-[#1a1427] font-sans shrink-0`}>
                {/* Left Side: Student Submission */}
                <div className={`px-5 py-3 flex items-center justify-between gap-3 md:border-r ${PANEL_BORDER}`}>
                    <div className="flex items-center gap-2.5 min-w-0">
                        <span className="w-3 h-3 rounded-full bg-[#ff7edb] shadow-[0_0_8px_rgba(255,126,219,0.6)] shrink-0" />
                        <span className="font-black text-slate-900 dark:text-white text-base sm:text-lg truncate" title={studentAuthor}>
                            {studentAuthor}
                        </span>
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                        {comments.length > 0 && (
                            <span className="text-xs text-slate-600 dark:text-slate-300 bg-slate-100 dark:bg-[#251d38] px-2 py-0.5 rounded-full border border-slate-300 dark:border-slate-700">
                                {comments.length} {comments.length === 1 ? "nota" : "notas"}
                            </span>
                        )}
                        <button
                            onClick={() => setShowGeneralComposer(!showGeneralComposer)}
                            aria-label={showGeneralComposer ? "Cerrar redactor de nota" : "Añadir conclusión o nota general del docente"}
                            className="group relative p-2 rounded-lg bg-fuchsia-50 dark:bg-fuchsia-950/40 border border-fuchsia-500/30 text-fuchsia-700 dark:text-fuchsia-300 hover:bg-fuchsia-100 dark:hover:bg-fuchsia-900/50 transition-all active:scale-95 flex items-center justify-center shadow-sm"
                        >
                            {showGeneralComposer ? <X size={16} /> : <MessageSquarePlus size={16} />}
                            <div role="tooltip" className="absolute right-0 top-full mt-2 opacity-0 pointer-events-none group-hover:opacity-100 group-focus-visible:opacity-100 transition-opacity duration-200 flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-900/95 border border-fuchsia-500/40 text-fuchsia-100 text-xs font-sans font-medium whitespace-nowrap shadow-2xl z-[120]">
                                <span>{showGeneralComposer ? "Cerrar redactor de nota" : "Añadir conclusión o nota general del docente"}</span>
                            </div>
                        </button>
                    </div>
                </div>

                {/* Right Side: Reference */}
                <div className="px-5 py-3 flex items-center justify-between gap-3">
                    <div className="flex items-center gap-2 min-w-0">
                        <span className="w-2.5 h-2.5 rounded-full bg-[#36f9f6] shadow-[0_0_8px_rgba(54,249,246,0.6)] shrink-0" />
                        <span className="text-xs uppercase tracking-wider font-semibold text-slate-500 dark:text-slate-400 shrink-0">
                            Referencia
                        </span>
                        <span className="font-semibold text-slate-700 dark:text-slate-300 text-sm truncate" title={referenceAuthor}>
                            {referenceAuthor}
                        </span>
                    </div>
                    <span className="text-xs font-mono text-slate-500 dark:text-slate-400 shrink-0">
                        {language.toUpperCase()}
                    </span>
                </div>
            </div>

            {/* Two panes, each with its own scroll */}
            <div data-tour="code-panes" className="grid grid-cols-1 md:grid-cols-2 flex-1 min-h-0 overflow-hidden relative">
                {/* Left Side: Student Submission + Inline Comments */}
                <div
                    onScroll={syncTipOnScroll}
                    className={`overflow-auto ${SCROLLBAR} md:border-r border-b md:border-b-0 ${PANEL_BORDER} bg-white dark:bg-[#181324] select-text h-full min-h-0`}
                    style={paneStyle}
                >
                    <table className="w-full border-collapse">
                        <tbody>
                            {stuLines.map((stuLine, index) => {
                                const lineNum = index + 1;
                                const evidenceItems = evidence.get(lineNum);
                                const styleLevel = styleIntensity.get(lineNum);
                                // A line with an observation reads as the strongest highlight of the same violet family.
                                const level: StyleIntensity | undefined = evidenceItems ? 3 : styleLevel;
                                const lineComments = commentsByLine.get(lineNum) || [];
                                const isComposerActive = activeCommentLine === lineNum;

                                return (
                                    <React.Fragment key={`stu-frag-${lineNum}`}>
                                        <tr
                                            data-line={lineNum}
                                            tabIndex={evidenceItems ? 0 : undefined}
                                            aria-describedby={evidenceItems && tip?.line === lineNum ? tipId : undefined}
                                            aria-label={evidenceItems ? `Línea ${lineNum}: tiene una observación` : undefined}
                                            onMouseEnter={evidenceItems ? (e) => showTip(lineNum, e.currentTarget, "mouse") : undefined}
                                            onMouseLeave={evidenceItems ? () => setTip(null) : undefined}
                                            onFocus={evidenceItems ? (e) => showTip(lineNum, e.currentTarget, "focus") : undefined}
                                            onBlur={evidenceItems ? () => { tipRowRef.current = null; setTip(null); } : undefined}
                                            className={`group transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-violet-500 ${
                                                level
                                                    ? `${HIGHLIGHT_ROW_CLASS[level]} ${evidenceItems ? "cursor-help" : ""}`
                                                    : "hover:bg-slate-100 dark:hover:bg-[#251d38]/50"
                                            }`}
                                        >
                                            {/* Line Number & Comment Trigger Button */}
                                            <td className={`w-16 py-1 px-2 text-right text-slate-500 dark:text-slate-400 font-mono text-[13px] select-none border-r ${GUTTER_BORDER} relative`}>
                                                <div className="flex items-center justify-end gap-1">
                                                    {lineComments.length > 0 && (
                                                        <span
                                                            className="w-2 h-2 rounded-full bg-fuchsia-500 dark:bg-fuchsia-400 shadow-[0_0_5px_#ff7edb]"
                                                            title={`${lineComments.length} comentarios`}
                                                        />
                                                    )}
                                                    <span className={index === 0 ? undefined : "group-hover:hidden"}>{lineNum}</span>
                                                    <button
                                                        data-tour={index === 0 ? "add-comment" : undefined}
                                                        onClick={() => {
                                                            setActiveCommentLine(isComposerActive ? null : lineNum);
                                                            setCommentText("");
                                                        }}
                                                        aria-label={`Agregar observación en la línea ${lineNum}`}
                                                        className={`${index === 0 ? "flex opacity-60 group-hover:opacity-100" : "hidden group-hover:flex"} items-center justify-center w-5 h-5 rounded-md bg-fuchsia-500/20 text-fuchsia-700 dark:text-fuchsia-300 hover:bg-fuchsia-500 hover:text-white transition-all`}
                                                        title="Agregar observación en esta línea"
                                                    >
                                                        <Plus size={12} />
                                                    </button>
                                                </div>
                                            </td>

                                            {/* Code Content */}
                                            <td className="py-1 px-4 font-mono text-sm leading-relaxed whitespace-pre">
                                                <SynthwaveLine line={stuLine} />
                                            </td>
                                        </tr>

                                        {/* Inline Comments & Composer Row */}
                                        {(lineComments.length > 0 || isComposerActive) && (
                                            <tr className="bg-violet-50 dark:bg-[#211833]/90">
                                                <td className={`border-r ${GUTTER_BORDER}`} />
                                                <td className="p-3">
                                                    <div className="space-y-2.5">
                                                        {lineComments.map((comment) => (
                                                            <div
                                                                key={comment.id}
                                                                className="p-3 bg-white dark:bg-[#2a1f42] border-l-4 border-fuchsia-500 rounded-r-xl font-sans text-sm shadow-md relative group/box whitespace-normal"
                                                            >
                                                                <div className="flex items-center justify-between text-xs mb-1">
                                                                    <div className="flex items-center gap-2">
                                                                        <span className="font-bold text-fuchsia-700 dark:text-fuchsia-300">
                                                                            {comment.autor_nombre || "Docente"}
                                                                        </span>
                                                                        <span className="text-slate-400">•</span>
                                                                        <span className="text-slate-500 dark:text-slate-400">Línea {lineNum}</span>
                                                                    </div>
                                                                    <button
                                                                        onClick={() => onDeleteComment(comment.id)}
                                                                        className="text-slate-500 hover:text-rose-500 opacity-0 group-hover/box:opacity-100 focus-visible:opacity-100 transition-opacity"
                                                                        title="Eliminar observación"
                                                                        aria-label="Eliminar observación"
                                                                    >
                                                                        <Trash2 size={14} />
                                                                    </button>
                                                                </div>
                                                                <p className="text-slate-800 dark:text-slate-200 leading-relaxed whitespace-pre-wrap">
                                                                    {comment.contenido}
                                                                </p>
                                                            </div>
                                                        ))}

                                                        {/* Inline Composer */}
                                                        {isComposerActive && (
                                                            <div className="p-3 bg-white dark:bg-[#2a1f42] border border-violet-500/40 rounded-xl font-sans text-sm whitespace-normal">
                                                                <div className="flex items-center justify-between mb-1.5 text-slate-700 dark:text-slate-300 text-sm font-bold">
                                                                    <span>Observación para la línea {lineNum}</span>
                                                                    <button
                                                                        onClick={() => setActiveCommentLine(null)}
                                                                        aria-label="Cerrar redactor"
                                                                        className="text-slate-500 hover:text-slate-900 dark:text-slate-400 dark:hover:text-white"
                                                                    >
                                                                        <X size={14} />
                                                                    </button>
                                                                </div>
                                                                <textarea
                                                                    value={commentText}
                                                                    onChange={(e) => setCommentText(e.target.value)}
                                                                    placeholder="Escribe tu observación o sugerencia para esta línea..."
                                                                    className="w-full h-20 p-2.5 bg-slate-50 dark:bg-[#1a1427] border border-slate-300 dark:border-[#3d2f5a] rounded-lg text-slate-900 dark:text-slate-200 text-sm placeholder-slate-500 focus:outline-none focus:border-violet-500 transition-all resize-none"
                                                                />
                                                                <div className="flex justify-end gap-2 mt-2">
                                                                    <button
                                                                        onClick={() => setActiveCommentLine(null)}
                                                                        className="px-3 py-1 text-sm text-slate-600 hover:text-slate-900 dark:text-slate-400 dark:hover:text-white"
                                                                    >
                                                                        Cancelar
                                                                    </button>
                                                                    <button
                                                                        onClick={() => handleSaveLineComment(lineNum)}
                                                                        disabled={isSubmittingComment || !commentText.trim()}
                                                                        className="flex items-center gap-1.5 px-3 py-1 rounded-md bg-gradient-to-r from-fuchsia-500 to-indigo-600 text-white text-sm font-bold hover:opacity-90 active:scale-95 disabled:opacity-50"
                                                                    >
                                                                        <Send size={13} />
                                                                        <span>Guardar nota</span>
                                                                    </button>
                                                                </div>
                                                            </div>
                                                        )}
                                                    </div>
                                                </td>
                                            </tr>
                                        )}
                                    </React.Fragment>
                                );
                            })}
                        </tbody>
                    </table>
                </div>

                {/* Right Side: Reference */}
                <div
                    className={`overflow-auto ${SCROLLBAR} bg-slate-50/70 dark:bg-[#1a1427] select-text h-full min-h-0`}
                    style={paneStyle}
                >
                    <table className="w-full border-collapse">
                        <tbody>
                            {refLines.map((refLine, index) => (
                                <tr key={`ref-${index + 1}`} className="group transition-colors hover:bg-slate-100 dark:hover:bg-[#251d38]/50">
                                    <td className={`w-14 py-1 px-3 text-right text-slate-500 dark:text-slate-400 font-mono text-[13px] select-none border-r ${GUTTER_BORDER}`}>
                                        {index + 1}
                                    </td>
                                    <td className="py-1 px-4 font-mono text-sm leading-relaxed whitespace-pre">
                                        <SynthwaveLine line={refLine} />
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            </div>

            {tip && evidence.get(tip.line) && createPortal(
                <LineTooltip id={tipId} tip={tip} items={evidence.get(tip.line)!} />,
                document.body
            )}
        </div>
    );
}

/** Floating explanation for a highlighted line; rendered in a portal so no scroll container clips it. */
function LineTooltip({ id, tip, items }: { id: string; tip: LineTip; items: LineEvidence[] }) {
    const margin = 8;
    const left = Math.max(margin, Math.min(tip.left + 56, window.innerWidth - TIP_WIDTH - margin));
    const placeAbove = tip.bottom + 180 > window.innerHeight && tip.top > 180;
    const style: React.CSSProperties = placeAbove
        ? { left, bottom: window.innerHeight - tip.top + 4, width: TIP_WIDTH }
        : { left, top: tip.bottom + 4, width: TIP_WIDTH };

    return (
        <div
            id={id}
            role="tooltip"
            style={style}
            className="pointer-events-none fixed z-[300] max-w-[calc(100vw-16px)] space-y-2 rounded-xl border border-violet-400/50 bg-slate-900/95 p-3 font-sans text-sm text-slate-200 shadow-2xl"
        >
            {items.map((item) => (
                <div key={`${item.title}-${item.text}`}>
                    <p className="font-bold text-violet-300">{item.title}</p>
                    <p className="mt-0.5 leading-relaxed text-slate-300">{item.text}</p>
                </div>
            ))}
            <p className="border-t border-white/10 pt-2 text-xs text-slate-400">
                Indicio orientativo: ayuda a revisar la línea, no es una conclusión.
            </p>
        </div>
    );
}
