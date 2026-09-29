import React, { useState, useRef, useEffect, useMemo } from "react";
import { MessageSquare, Plus, Trash2, X, Send, User, Sparkles, Check, ChevronDown, ChevronUp } from "lucide-react";
import { SynthwaveLine } from "./SynthwaveHighlighter";

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
}

export function SideBySideDiffViewer({
    referenceCode,
    studentCode,
    referenceAuthor = "Docente (Referencia Canónica)",
    studentAuthor = "Estudiante (Entrega)",
    language = "c",
    reportId,
    comments,
    onAddComment,
    onDeleteComment,
    isSubmittingComment = false,
}: SideBySideDiffViewerProps) {
    // Sincronización de scroll
    const leftScrollRef = useRef<HTMLDivElement>(null);
    const rightScrollRef = useRef<HTMLDivElement>(null);
    const isScrollingRef = useRef<"left" | "right" | null>(null);

    // Estado para nueva nota en línea
    const [activeCommentLine, setActiveCommentLine] = useState<number | null>(null);
    const [commentText, setCommentText] = useState("");
    // Estado para nueva nota general
    const [showGeneralComposer, setShowGeneralComposer] = useState(false);
    const [generalCommentText, setGeneralCommentText] = useState("");
    const [showGeneralCommentsTray, setShowGeneralCommentsTray] = useState(true);

    const refLines = useMemo(() => referenceCode.split("\n"), [referenceCode]);
    const stuLines = useMemo(() => studentCode.split("\n"), [studentCode]);
    const maxLines = Math.max(refLines.length, stuLines.length);

    // Agrupar comentarios por línea
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

    // Comentarios generales
    const generalComments = useMemo(
        () => comments.filter((c) => c.numero_linea === null),
        [comments]
    );

    // Manejar scroll sincronizado
    const handleScroll = (source: "left" | "right") => {
        if (isScrollingRef.current && isScrollingRef.current !== source) return;
        isScrollingRef.current = source;

        const src = source === "left" ? leftScrollRef.current : rightScrollRef.current;
        const target = source === "left" ? rightScrollRef.current : leftScrollRef.current;

        if (src && target) {
            target.scrollTop = src.scrollTop;
            target.scrollLeft = src.scrollLeft;
        }

        setTimeout(() => {
            isScrollingRef.current = null;
        }, 30);
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

    return (
        <div className="flex flex-col h-full bg-[#181324] rounded-2xl overflow-hidden border border-fuchsia-500/20 shadow-2xl font-mono text-[13px]">
            {/* Top Synthwave Bar */}
            <div className="h-1 bg-gradient-to-r from-[#ff7edb] via-[#36f9f6] to-[#fede5d] shadow-[0_0_12px_rgba(255,126,219,0.7)]" />

            {/* Sub-Header con Acciones */}
            <div className="flex items-center justify-between px-6 py-2.5 bg-[#201830] border-b border-[#2d2244] shrink-0">
                <div className="flex items-center gap-3">
                    <span className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-[#2d2244] text-[#36f9f6] text-xs font-bold border border-[#36f9f6]/30">
                        <Sparkles size={13} className="text-[#36f9f6]" />
                        Synthwave '84
                    </span>
                    <span className="text-xs text-slate-400 font-sans">
                        Lado a lado con alineación de flujo
                    </span>
                </div>

                <div className="flex items-center gap-3">
                    <button
                        onClick={() => setShowGeneralComposer(!showGeneralComposer)}
                        className="flex items-center gap-1.5 px-3 py-1 rounded-lg bg-fuchsia-600/20 border border-fuchsia-500/40 text-fuchsia-300 hover:bg-fuchsia-600/30 text-xs font-sans font-semibold transition-all active:scale-95"
                    >
                        <MessageSquare size={13} />
                        <span>{showGeneralComposer ? "Ocultar anotación" : "+ Nota general"}</span>
                    </button>
                    {comments.length > 0 && (
                        <span className="text-[11px] font-sans text-slate-400 bg-[#291e3d] px-2 py-0.5 rounded-full border border-slate-700">
                            {comments.length} {comments.length === 1 ? "observación" : "observaciones"}
                        </span>
                    )}
                </div>
            </div>

            {/* General Comment Composer Dropdown */}
            {showGeneralComposer && (
                <div className="p-4 bg-[#231a38] border-b border-fuchsia-500/30 text-sans">
                    <div className="flex items-center justify-between mb-2">
                        <span className="text-xs font-bold text-fuchsia-300 flex items-center gap-1.5 font-sans">
                            <MessageSquare size={14} /> Nueva Observación General del Docente
                        </span>
                        <button
                            onClick={() => setShowGeneralComposer(false)}
                            className="text-slate-400 hover:text-white"
                        >
                            <X size={14} />
                        </button>
                    </div>
                    <textarea
                        value={generalCommentText}
                        onChange={(e) => setGeneralCommentText(e.target.value)}
                        placeholder="Escribe una conclusión o justificación técnica general para este análisis..."
                        className="w-full h-20 p-3 bg-[#181324] border border-[#3d2f5a] rounded-xl text-slate-200 text-xs font-sans placeholder-slate-500 focus:outline-none focus:border-[#36f9f6] transition-all resize-none"
                    />
                    <div className="flex justify-end gap-2 mt-2 font-sans">
                        <button
                            onClick={() => setShowGeneralComposer(false)}
                            className="px-3 py-1 text-xs text-slate-400 hover:text-white"
                        >
                            Cancelar
                        </button>
                        <button
                            onClick={handleSaveGeneralComment}
                            disabled={isSubmittingComment || !generalCommentText.trim()}
                            className="flex items-center gap-1.5 px-4 py-1.5 rounded-lg bg-gradient-to-r from-fuchsia-500 to-indigo-600 text-white text-xs font-bold hover:opacity-90 active:scale-95 disabled:opacity-50"
                        >
                            <Send size={12} />
                            <span>Guardar Nota General</span>
                        </button>
                    </div>
                </div>
            )}

            {/* General Comments Display */}
            {generalComments.length > 0 && (
                <div className="px-6 py-2.5 bg-[#1e1730] border-b border-[#2d2244] font-sans">
                    <button
                        onClick={() => setShowGeneralCommentsTray(!showGeneralCommentsTray)}
                        className="flex items-center justify-between w-full text-xs font-bold text-slate-300 hover:text-white py-1"
                    >
                        <span className="flex items-center gap-2">
                            <span className="w-2 h-2 rounded-full bg-fuchsia-400" />
                            Notas Generales del Docente ({generalComments.length})
                        </span>
                        {showGeneralCommentsTray ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                    </button>

                    {showGeneralCommentsTray && (
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mt-2">
                            {generalComments.map((gc) => (
                                <div
                                    key={gc.id}
                                    className="p-3 bg-[#261d3c] border border-fuchsia-500/20 rounded-xl relative group text-xs"
                                >
                                    <div className="flex items-center justify-between mb-1 text-[11px] text-slate-400">
                                        <span className="font-semibold text-fuchsia-300 flex items-center gap-1">
                                            <User size={12} /> {gc.autor_nombre || "Docente"}
                                        </span>
                                        <button
                                            onClick={() => onDeleteComment(gc.id)}
                                            className="text-slate-500 hover:text-rose-400 opacity-0 group-hover:opacity-100 transition-opacity"
                                            title="Eliminar comentario"
                                        >
                                            <Trash2 size={13} />
                                        </button>
                                    </div>
                                    <p className="text-slate-200 whitespace-pre-wrap leading-relaxed">{gc.contenido}</p>
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            )}

            {/* Column Headers */}
            <div className="grid grid-cols-2 border-b border-[#2d2244] bg-[#1e1730] text-xs font-sans font-bold shrink-0">
                <div className="px-6 py-2.5 flex items-center justify-between border-r border-[#2d2244]">
                    <span className="text-[#36f9f6] flex items-center gap-2">
                        <span className="w-2 h-2 rounded-full bg-[#36f9f6] shadow-[0_0_6px_#36f9f6]" />
                        {referenceAuthor}
                    </span>
                    <span className="text-[10px] uppercase tracking-wider text-slate-500 font-mono">
                        {language.toUpperCase()} CANÓNICO
                    </span>
                </div>
                <div className="px-6 py-2.5 flex items-center justify-between">
                    <span className="text-[#ff7edb] flex items-center gap-2">
                        <span className="w-2 h-2 rounded-full bg-[#ff7edb] shadow-[0_0_6px_#ff7edb]" />
                        {studentAuthor}
                    </span>
                    <span className="text-[10px] uppercase tracking-wider text-slate-500 font-mono">
                        ENTREGA
                    </span>
                </div>
            </div>

            {/* Side by Side Scrolling Area */}
            <div className="grid grid-cols-2 flex-1 overflow-hidden relative">
                {/* Left Side: Teacher / Canonical Reference */}
                <div
                    ref={leftScrollRef}
                    onScroll={() => handleScroll("left")}
                    className="overflow-y-auto overflow-x-auto border-r border-[#2d2244] bg-[#1a1427] scrollbar-thin scrollbar-thumb-[#3d2f5a] scrollbar-track-transparent select-text"
                    style={{ height: "calc(93vh - 270px)", minHeight: "480px" }}
                >
                    <table className="w-full border-collapse">
                        <tbody>
                            {Array.from({ length: maxLines }).map((_, index) => {
                                const lineNum = index + 1;
                                const refLine = refLines[index] ?? "";
                                const stuLine = stuLines[index] ?? "";
                                const isDiff = refLine !== stuLine;

                                return (
                                    <tr
                                        key={`ref-${lineNum}`}
                                        className={`group transition-colors ${
                                            isDiff
                                                ? "bg-cyan-950/20 hover:bg-cyan-950/30"
                                                : "hover:bg-[#251d38]/50"
                                        }`}
                                    >
                                        {/* Line Number */}
                                        <td className="w-12 sm:w-14 py-1 px-3 text-right text-slate-500 font-mono text-[12px] sm:text-[13px] select-none border-r border-[#291e3e]">
                                            {index < refLines.length ? lineNum : ""}
                                        </td>
                                        {/* Code Content */}
                                        <td className={`py-1 px-4 font-mono text-[13px] sm:text-[13.5px] leading-relaxed whitespace-pre ${isDiff ? "border-l-2 border-[#36f9f6]/40" : ""}`}>
                                            {index < refLines.length ? (
                                                <SynthwaveLine line={refLine} />
                                            ) : (
                                                <span className="text-slate-700 italic select-none">~</span>
                                            )}
                                        </td>
                                    </tr>
                                );
                            })}
                        </tbody>
                    </table>
                </div>

                {/* Right Side: Student Submission + Inline Comments */}
                <div
                    ref={rightScrollRef}
                    onScroll={() => handleScroll("right")}
                    className="overflow-y-auto overflow-x-auto bg-[#181324] scrollbar-thin scrollbar-thumb-[#3d2f5a] scrollbar-track-transparent select-text"
                    style={{ height: "calc(93vh - 270px)", minHeight: "480px" }}
                >
                    <table className="w-full border-collapse">
                        <tbody>
                            {Array.from({ length: maxLines }).map((_, index) => {
                                const lineNum = index + 1;
                                const refLine = refLines[index] ?? "";
                                const stuLine = stuLines[index] ?? "";
                                const isDiff = refLine !== stuLine;
                                const lineComments = commentsByLine.get(lineNum) || [];
                                const isComposerActive = activeCommentLine === lineNum;

                                return (
                                    <React.Fragment key={`stu-frag-${lineNum}`}>
                                        <tr
                                            className={`group transition-colors ${
                                                isDiff
                                                    ? "bg-fuchsia-950/20 hover:bg-fuchsia-950/30"
                                                    : "hover:bg-[#251d38]/50"
                                            }`}
                                        >
                                            {/* Line Number & Comment Trigger Button */}
                                            <td className="w-14 sm:w-16 py-1 px-2 text-right text-slate-500 font-mono text-[12px] sm:text-[13px] select-none border-r border-[#291e3e] relative">
                                                {index < stuLines.length && (
                                                    <div className="flex items-center justify-end gap-1">
                                                        {lineComments.length > 0 && (
                                                            <span
                                                                className="w-2 h-2 rounded-full bg-fuchsia-400 shadow-[0_0_5px_#ff7edb]"
                                                                title={`${lineComments.length} comentarios`}
                                                            />
                                                        )}
                                                        <span className="group-hover:hidden">{lineNum}</span>
                                                        <button
                                                            onClick={() => {
                                                                setActiveCommentLine(isComposerActive ? null : lineNum);
                                                                setCommentText("");
                                                            }}
                                                            className="hidden group-hover:flex items-center justify-center w-5 h-5 rounded-md bg-fuchsia-500/20 text-fuchsia-300 hover:bg-fuchsia-500 hover:text-white transition-all shadow-[0_0_6px_rgba(255,126,219,0.5)]"
                                                            title="Agregar observación en esta línea"
                                                        >
                                                            <Plus size={11} />
                                                        </button>
                                                    </div>
                                                )}
                                            </td>

                                            {/* Code Content */}
                                            <td className={`py-1 px-4 font-mono text-[13px] sm:text-[13.5px] leading-relaxed whitespace-pre ${isDiff ? "border-l-2 border-[#ff7edb]/40" : ""}`}>
                                                {index < stuLines.length ? (
                                                    <SynthwaveLine line={stuLine} />
                                                ) : (
                                                    <span className="text-slate-700 italic select-none">~</span>
                                                )}
                                            </td>
                                        </tr>

                                        {/* Inline Comments & Composer Row */}
                                        {(lineComments.length > 0 || isComposerActive) && (
                                            <tr className="bg-[#211833]/90">
                                                <td className="border-r border-[#291e3e]" />
                                                <td className="p-3">
                                                    <div className="space-y-2.5">
                                                        {/* Existing Comments */}
                                                        {lineComments.map((comment) => (
                                                            <div
                                                                key={comment.id}
                                                                className="p-3 bg-[#2a1f42] border-l-4 border-fuchsia-500 rounded-r-xl font-sans text-xs shadow-md relative group/box"
                                                            >
                                                                <div className="flex items-center justify-between text-[11px] text-fuchsia-300/80 mb-1">
                                                                    <div className="flex items-center gap-2">
                                                                        <span className="font-bold text-fuchsia-300">
                                                                            {comment.autor_nombre || "Docente"}
                                                                        </span>
                                                                        <span className="text-slate-500">•</span>
                                                                        <span className="text-slate-400">Línea {lineNum}</span>
                                                                    </div>
                                                                    <button
                                                                        onClick={() => onDeleteComment(comment.id)}
                                                                        className="text-slate-500 hover:text-rose-400 opacity-0 group-hover/box:opacity-100 transition-opacity"
                                                                        title="Eliminar observación"
                                                                    >
                                                                        <Trash2 size={13} />
                                                                    </button>
                                                                </div>
                                                                <p className="text-slate-200 leading-relaxed whitespace-pre-wrap">
                                                                    {comment.contenido}
                                                                </p>
                                                            </div>
                                                        ))}

                                                        {/* Inline Composer */}
                                                        {isComposerActive && (
                                                            <div className="p-3 bg-[#2a1f42] border border-[#36f9f6]/40 rounded-xl font-sans text-xs">
                                                                <div className="flex items-center justify-between mb-1.5 text-slate-300 text-xs font-bold">
                                                                    <span>Anotación para la Línea {lineNum}</span>
                                                                    <button
                                                                        onClick={() => setActiveCommentLine(null)}
                                                                        className="text-slate-400 hover:text-white"
                                                                    >
                                                                        <X size={13} />
                                                                    </button>
                                                                </div>
                                                                <textarea
                                                                    autoFocus
                                                                    value={commentText}
                                                                    onChange={(e) => setCommentText(e.target.value)}
                                                                    placeholder="Escribe la observación sobre esta línea..."
                                                                    className="w-full h-16 p-2.5 bg-[#181324] border border-[#3d2f5a] rounded-lg text-slate-200 text-xs focus:outline-none focus:border-[#36f9f6] resize-none"
                                                                />
                                                                <div className="flex justify-end gap-2 mt-2">
                                                                    <button
                                                                        onClick={() => setActiveCommentLine(null)}
                                                                        className="px-2.5 py-1 text-slate-400 hover:text-white text-xs"
                                                                    >
                                                                        Cancelar
                                                                    </button>
                                                                    <button
                                                                        onClick={() => handleSaveLineComment(lineNum)}
                                                                        disabled={isSubmittingComment || !commentText.trim()}
                                                                        className="flex items-center gap-1.5 px-3 py-1 rounded-lg bg-gradient-to-r from-fuchsia-500 to-[#36f9f6] text-black font-bold text-xs hover:opacity-90 active:scale-95 disabled:opacity-50"
                                                                    >
                                                                        <Send size={11} />
                                                                        <span>Guardar Nota</span>
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
            </div>
        </div>
    );
}
