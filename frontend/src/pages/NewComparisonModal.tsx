import React, { useState, useEffect, useRef } from "react";
import { Upload, Loader2 } from "lucide-react";
import { Modal } from "../components/ui/Modal";
import { Button } from "../components/ui/Button";
import { api, Problema, IS_DEMO_MODE } from "../lib/api";
import { toComparison } from "../lib/dictamen";
import { cn } from "../lib/utils";

export interface PreselectedProblem {
    id: number;
    title: string;
    lenguaje?: string;
}

interface NewComparisonModalProps {
    isOpen: boolean;
    onClose: () => void;
    onAnalysisComplete?: (report: any) => void;
    preselectedProblem?: PreselectedProblem | null;
}

export function NewComparisonModal({ isOpen, onClose, onAnalysisComplete, preselectedProblem }: NewComparisonModalProps) {
    const [problems, setProblems] = useState<Problema[]>([]);
    const [selectedProblemId, setSelectedProblemId] = useState<number | null>(preselectedProblem?.id ?? null);
    const [isChangingProblem, setIsChangingProblem] = useState(false);
    const [author, setAuthor] = useState("");
    const [code, setCode] = useState("");
    const [fileName, setFileName] = useState<string | null>(null);
    const [isLoading, setIsLoading] = useState(false);
    const [loadingMessage, setLoadingMessage] = useState<string>("Iniciando análisis bimodal...");
    const [error, setError] = useState<string | null>(null);

    const fileInputRef = useRef<HTMLInputElement>(null);

    useEffect(() => {
        if (isOpen) {
            setError(null);
            setIsChangingProblem(false);
            if (preselectedProblem?.id) {
                setSelectedProblemId(preselectedProblem.id);
            }
            // Cargar lista de problemas disponibles
            api.problems
                .list()
                .then((res) => {
                    setProblems(res);
                    if (res.length > 0 && !selectedProblemId && !preselectedProblem?.id) {
                        setSelectedProblemId(res[0].id);
                    }
                })
                .catch(() => {});
        }
    }, [isOpen, preselectedProblem]);

    const activeProblem =
        problems.find((p) => p.id === selectedProblemId) ||
        (preselectedProblem && preselectedProblem.id === selectedProblemId ? preselectedProblem : null);

    const activeLanguage = (
        (activeProblem as Problema)?.lenguaje ||
        (activeProblem as PreselectedProblem)?.lenguaje ||
        ""
    ).toLowerCase();
    const isCpp = activeLanguage.includes("cpp") || activeLanguage === "c++";

    const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0];
        if (!file) return;

        setFileName(file.name);
        const reader = new FileReader();
        reader.onload = (event) => {
            const content = event.target?.result as string;
            setCode(content);
        };
        reader.readAsText(file);
    };

    const handleStartAnalysis = async () => {
        if (IS_DEMO_MODE) {
            setError("El análisis de nuevas entregas y subida de archivos está deshabilitado en el Modo Demostración.");
            return;
        }

        if (!selectedProblemId) {
            setError("Debes seleccionar un problema para comparar.");
            return;
        }
        if (!author.trim()) {
            setError("Debes ingresar el nombre o identificador del autor.");
            return;
        }
        if (!code.trim()) {
            setError("Debes ingresar o cargar el código fuente.");
            return;
        }

        setError(null);
        setIsLoading(true);
        setLoadingMessage("Guardando entrega del estudiante...");
        try {
            // 1. Registrar entrega del alumno
            const submission = await api.problems.addSubmission(
                selectedProblemId,
                author,
                code,
                activeLanguage || problems.find((p) => p.id === selectedProblemId)?.lenguaje || "c"
            );
            // 2. Disparar análisis bimodal en segundo plano (asíncrono)
            setLoadingMessage("Iniciando inferencia bimodal en segundo plano...");
            // Los umbrales los fija el servidor desde los artefactos de calibración.
            const initialReport = await api.analysis.run(submission.id, undefined, true);

            let report = initialReport;
            if (initialReport.estado === "PROCESANDO") {
                setLoadingMessage("Analizando similitud léxica (Canal A) y estilo CharCNN (Canal B)...");
                report = await api.analysis.pollUntilComplete(initialReport.id);
            }

            // Adaptar para visualización en SimilarityReportModal (campos del reporte tal cual).
            const adaptedComparison = toComparison(report, `${author} — Entrega`);

            onAnalysisComplete?.(adaptedComparison);
            onClose();
        } catch (err: any) {
            setError(err.message || "Error al ejecutar el análisis bimodal.");
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <Modal
            isOpen={isOpen}
            onClose={onClose}
            title="Nueva Comparación de Código"
            maxWidth="xl"
            footer={
                <div className="flex items-center justify-between">
                    <Button
                        type="button"
                        variant="ghost"
                        onClick={onClose}
                        disabled={isLoading}
                    >
                        Cancelar
                    </Button>
                    <Button
                        type="button"
                        variant="gradient"
                        onClick={handleStartAnalysis}
                        disabled={isLoading || problems.length === 0}
                        isLoading={isLoading}
                        className="!py-3.5 !px-8 !rounded-2xl"
                    >
                        {isLoading ? loadingMessage : "Iniciar Análisis"}
                    </Button>
                </div>
            }
        >
            {/* Hidden file input */}
            <input
                type="file"
                ref={fileInputRef}
                className="hidden"
                accept=".c,.cpp,.h,.hpp"
                onChange={handleFileChange}
            />

            {IS_DEMO_MODE && (
                <div className="p-4 bg-amber-500/10 border border-amber-500/30 rounded-xl text-amber-800 dark:text-amber-300 text-xs flex items-start gap-2.5">
                    <span className="text-base leading-none">ℹ️</span>
                    <div>
                        <span className="font-bold">Modo Demostración (Solo Lectura):</span> El análisis de nuevas entregas y subida de archivos está desactivado. Puedes explorar los análisis y reportes detallados ya procesados en la biblioteca.
                    </div>
                </div>
            )}

            {error && (
                <div className="p-3 bg-red-500/10 border border-red-500/30 rounded-xl text-red-600 dark:text-red-300 text-xs font-medium">
                    {error}
                </div>
            )}

            {isLoading && (
                <div className="p-4 rounded-2xl bg-gradient-to-r from-graphito-blue/15 to-graphito-violet/15 border border-graphito-blue/30 space-y-3 shadow-sm">
                    <div className="flex items-center gap-3">
                        <Loader2 className="w-5 h-5 text-graphito-blue animate-spin shrink-0" />
                        <div className="min-w-0 flex-1">
                            <p className="text-xs font-bold text-slate-900 dark:text-white">
                                {loadingMessage}
                            </p>
                            <p className="text-[11px] text-slate-500 dark:text-slate-400">
                                Ejecutando evaluación bimodal en segundo plano (Canal A léxico + Canal B CharCNN).
                            </p>
                        </div>
                    </div>
                    <div className="h-1.5 w-full bg-slate-200/60 dark:bg-white/10 rounded-full overflow-hidden">
                        <div className="h-full bg-gradient-to-r from-graphito-blue to-graphito-violet rounded-full w-3/4 animate-pulse" />
                    </div>
                </div>
            )}

            {/* Código de referencia seleccionado / selector */}
            <div className="space-y-1.5">
                <label className="text-[10px] uppercase font-black tracking-widest text-slate-600 dark:text-slate-400">
                    Código de referencia seleccionado
                </label>
                {activeProblem && !isChangingProblem ? (
                    <div className="flex items-center justify-between p-3.5 rounded-2xl border border-slate-200 dark:border-graphito-border bg-slate-50 dark:bg-graphito-surface transition-colors">
                        <div className="flex items-center gap-3 min-w-0">
                            <span className="font-display font-bold text-sm text-slate-900 dark:text-white truncate">
                                {(activeProblem as PreselectedProblem).title || (activeProblem as Problema).titulo}
                            </span>
                            <span
                                className={cn(
                                    "px-2.5 py-0.5 rounded text-[10px] font-black uppercase tracking-wider border shrink-0",
                                    isCpp
                                        ? "bg-pink-500/10 text-pink-600 dark:text-pink-400 border-pink-500/30"
                                        : "bg-blue-500/10 text-blue-600 dark:text-blue-400 border-blue-500/30"
                                )}
                            >
                                {isCpp ? "C++" : "C"}
                            </span>
                        </div>
                        {problems.length > 1 && (
                            <button
                                type="button"
                                onClick={() => setIsChangingProblem(true)}
                                className="text-xs text-graphito-blue hover:underline font-semibold ml-3 shrink-0"
                            >
                                Cambiar
                            </button>
                        )}
                    </div>
                ) : problems.length > 0 ? (
                    <div className="space-y-2">
                        <div className="flex items-center gap-2">
                            <select
                                value={selectedProblemId || ""}
                                onChange={(e) => {
                                    setSelectedProblemId(Number(e.target.value));
                                }}
                                className="w-full bg-slate-50 dark:bg-[#121827] border border-slate-200 dark:border-[#2b3346] text-slate-900 dark:text-white rounded-xl py-3 px-4 focus:outline-none focus:border-graphito-blue text-sm cursor-pointer"
                            >
                                {problems.map((p) => (
                                    <option key={p.id} value={p.id}>
                                        {p.titulo} ({p.lenguaje.toUpperCase()})
                                    </option>
                                ))}
                            </select>
                            {selectedProblemId && (
                                <button
                                    type="button"
                                    onClick={() => setIsChangingProblem(false)}
                                    className="px-3.5 py-3 text-xs font-bold text-graphito-blue bg-graphito-blue/10 hover:bg-graphito-blue/20 rounded-xl transition-colors shrink-0"
                                >
                                    Listo
                                </button>
                            )}
                        </div>
                    </div>
                ) : (
                    <p className="text-xs text-orange-500 font-medium">
                        Primero crea al menos un problema en la biblioteca para comparar entregas.
                    </p>
                )}
            </div>

            {/* Student Author */}
            <div className="space-y-1.5">
                <label className="text-[10px] uppercase font-black tracking-widest text-slate-600 dark:text-slate-400">
                    Alumno / Identificador de la Entrega
                </label>
                <input
                    type="text"
                    value={author}
                    onChange={(e) => setAuthor(e.target.value)}
                    disabled={isLoading}
                    placeholder="Ej. Carlos López - Boleta 2021630987"
                    className="w-full bg-slate-50 dark:bg-[#121827]/40 border border-slate-200 dark:border-[#2b3346] text-slate-900 dark:text-white placeholder:text-slate-400 dark:placeholder:text-slate-600 rounded-xl py-3 px-4 focus:outline-none focus:border-graphito-blue text-sm disabled:opacity-60"
                />
            </div>

            {/* Upload Zone */}
            <div className="space-y-1.5">
                <label className="text-[10px] uppercase font-black tracking-widest text-slate-600 dark:text-slate-400">
                    Código de la Entrega {fileName && <span className="text-graphito-blue">({fileName})</span>}
                </label>
                <div
                    onClick={() => fileInputRef.current?.click()}
                    className="border-2 border-dashed border-slate-300 dark:border-[#2b3346] rounded-2xl p-6 flex flex-col items-center justify-center gap-3 bg-slate-50/50 hover:bg-slate-100/50 dark:bg-[#121827]/30 dark:hover:bg-[#121827]/50 transition-colors cursor-pointer group"
                >
                    <div className="w-10 h-10 rounded-xl bg-graphito-blue/10 flex items-center justify-center text-graphito-blue group-hover:scale-110 transition-transform">
                        <Upload size={20} />
                    </div>
                    <div className="text-center">
                        <p className="text-xs font-bold text-slate-700 dark:text-slate-200">
                            {fileName ? "Archivo seleccionado (clic para cambiar)" : "Haz clic para subir archivo .c o .cpp"}
                        </p>
                    </div>
                    <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        leftIcon={<Upload size={14} />}
                        disabled={isLoading}
                        onClick={(e) => {
                            e.stopPropagation();
                            fileInputRef.current?.click();
                        }}
                    >
                        {fileName ? "Cambiar archivo" : "Seleccionar archivo"}
                    </Button>
                </div>
                <textarea
                    value={code}
                    onChange={(e) => setCode(e.target.value)}
                    disabled={isLoading}
                    className="w-full h-[100px] bg-slate-50 dark:bg-[#121827]/40 border border-slate-200 dark:border-[#2b3346] rounded-xl p-3 text-xs text-slate-900 dark:text-white placeholder:text-slate-400 dark:placeholder:text-slate-600 focus:outline-none focus:border-graphito-blue font-mono resize-none mt-2 disabled:opacity-60"
                    placeholder="O pega el código fuente del alumno aquí..."
                />
            </div>
        </Modal>
    );
}
