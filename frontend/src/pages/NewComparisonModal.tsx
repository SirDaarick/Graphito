import { useState, useEffect, useRef } from "react";
import { X, Upload, CheckCircle2, Loader2 } from "lucide-react";
import { useGSAP } from "@gsap/react";
import gsap from "gsap";
import { AuthCard } from "../components/layout/AuthCard";
import { GradientButton } from "../components/ui/GradientButton";
import { api, Problema } from "../lib/api";

interface NewComparisonModalProps {
    isOpen: boolean;
    onClose: () => void;
    onAnalysisComplete?: (report: any) => void;
}

export function NewComparisonModal({ isOpen, onClose, onAnalysisComplete }: NewComparisonModalProps) {
    const [problems, setProblems] = useState<Problema[]>([]);
    const [selectedProblemId, setSelectedProblemId] = useState<number | null>(null);
    const [author, setAuthor] = useState("");
    const [code, setCode] = useState("");
    const [fileName, setFileName] = useState<string | null>(null);
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const [shouldRender, setShouldRender] = useState(isOpen);
    const backdropRef = useRef<HTMLDivElement>(null);
    const contentRef = useRef<HTMLDivElement>(null);
    const fileInputRef = useRef<HTMLInputElement>(null);

    useEffect(() => {
        if (isOpen) {
            setShouldRender(true);
            setError(null);
            // Cargar lista de problemas disponibles
            api.problems.list().then((res) => {
                setProblems(res);
                if (res.length > 0 && !selectedProblemId) {
                    setSelectedProblemId(res[0].id);
                }
            }).catch(() => {});
        }
    }, [isOpen]);

    useGSAP(() => {
        if (!shouldRender) return;

        if (isOpen) {
            gsap.fromTo(backdropRef.current, { opacity: 0 }, { opacity: 1, duration: 0.3, ease: "power2.out" });
            gsap.fromTo(contentRef.current, { opacity: 0, scale: 0.95 }, { opacity: 1, scale: 1, duration: 0.4, ease: "back.out(1.2)" });
        } else {
            gsap.to(backdropRef.current, { opacity: 0, duration: 0.3, ease: "power2.in" });
            gsap.to(contentRef.current, { opacity: 0, scale: 0.95, duration: 0.3, ease: "power2.in", onComplete: () => setShouldRender(false) });
        }
    }, [isOpen, shouldRender]);

    const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0];
        if (file) {
            setFileName(file.name);
            const reader = new FileReader();
            reader.onload = (event) => {
                setCode(event.target?.result as string);
            };
            reader.readAsText(file);
        }
    };

    const handleStartAnalysis = async () => {
        if (!selectedProblemId) {
            setError("Por favor selecciona un ejercicio/problema de referencia.");
            return;
        }
        if (!author.trim()) {
            setError("Por favor ingresa el nombre o boleta del alumno.");
            return;
        }
        if (!code.trim()) {
            setError("Por favor selecciona o escribe el código de la entrega del alumno.");
            return;
        }

        setError(null);
        setIsLoading(true);
        try {
            // 1. Registrar entrega del alumno
            const submission = await api.problems.addSubmission(
                selectedProblemId,
                author,
                code,
                "c"
            );
            // 2. Ejecutar análisis bimodal (Canal A + Canal B + Fusión + ChromaDB)
            const report = await api.analysis.run(submission.id);

            // Adaptar para visualización en SimilarityReportModal
            const adaptedComparison = {
                id: String(report.id),
                title: `${author} — Entrega`,
                subtitle: `Dictamen: ${report.dictamen}`,
                similarity: Math.round(report.similitud_semantica * 100),
                similitud_semantica: report.similitud_semantica,
                probabilidad_ia: report.probabilidad_ia,
                discrepancia_score: report.discrepancia_score,
                dictamen: report.dictamen,
                indicadores: report.indicadores,
            };

            onAnalysisComplete?.(adaptedComparison);
            onClose();
        } catch (err: any) {
            setError(err.message || "Error al ejecutar el análisis bimodal.");
        } finally {
            setIsLoading(false);
        }
    };

    if (!shouldRender) return null;

    return (
        <div className={`fixed inset-0 z-[100] flex items-center justify-center p-4`}>
            {/* Backdrop */}
            <div
                ref={backdropRef}
                className={`absolute inset-0 bg-black/60 backdrop-blur-sm opacity-0`}
                onClick={onClose}
            />

            {/* Hidden file input */}
            <input
                type="file"
                ref={fileInputRef}
                className="hidden"
                accept=".c,.cpp,.h,.hpp"
                onChange={handleFileChange}
            />

            {/* Modal Content */}
            <div ref={contentRef} className={`w-full max-w-xl opacity-0 transform scale-95`}>
                <AuthCard className="w-full p-0 overflow-hidden border-[#2b3346]/60">
                    {/* Header */}
                    <div className="flex items-center justify-between px-8 py-6 border-b border-[#2b3346]/40">
                        <h2 className="text-xl font-display font-bold text-white">
                            Nueva Comparación de Código
                        </h2>
                        <button
                            onClick={onClose}
                            className="p-1 text-slate-500 hover:text-white active:scale-95 focus:outline-none focus-visible:ring-2 focus-visible:ring-slate-400 rounded-md disabled:opacity-50 disabled:cursor-not-allowed transition-all"
                        >
                            <X size={20} />
                        </button>
                    </div>

                    {/* Body */}
                    <div className="p-8 space-y-6">
                        {error && (
                            <div className="p-3 bg-red-500/10 border border-red-500/30 rounded-xl text-red-300 text-xs font-medium">
                                {error}
                            </div>
                        )}

                        {/* Select Problem */}
                        <div className="space-y-1.5">
                            <label className="text-[10px] uppercase font-black tracking-widest text-slate-400">
                                Ejercicio / Problema de Referencia
                            </label>
                            {problems.length > 0 ? (
                                <select
                                    value={selectedProblemId || ""}
                                    onChange={(e) => setSelectedProblemId(Number(e.target.value))}
                                    className="w-full bg-[#121827] border border-[#2b3346] text-white rounded-xl py-3 px-4 focus:outline-none focus:border-graphito-blue text-sm cursor-pointer"
                                >
                                    {problems.map((p) => (
                                        <option key={p.id} value={p.id}>
                                            {p.titulo} ({p.lenguaje.toUpperCase()})
                                        </option>
                                    ))}
                                </select>
                            ) : (
                                <p className="text-xs text-orange-400 font-medium">
                                    Primero crea al menos un problema en la biblioteca para comparar entregas.
                                </p>
                            )}
                        </div>

                        {/* Student Author */}
                        <div className="space-y-1.5">
                            <label className="text-[10px] uppercase font-black tracking-widest text-slate-400">
                                Alumno / Identificador de la Entrega
                            </label>
                            <input
                                type="text"
                                value={author}
                                onChange={(e) => setAuthor(e.target.value)}
                                placeholder="Ej. Carlos López - Boleta 2021630987"
                                className="w-full bg-[#121827]/40 border border-[#2b3346] text-white rounded-xl py-3 px-4 focus:outline-none focus:border-graphito-blue text-sm"
                            />
                        </div>

                        {/* Upload Zone */}
                        <div className="space-y-1.5">
                            <label className="text-[10px] uppercase font-black tracking-widest text-slate-400">
                                Código de la Entrega {fileName && <span className="text-graphito-blue">({fileName})</span>}
                            </label>
                            <div
                                onClick={() => fileInputRef.current?.click()}
                                className="border-2 border-dashed border-[#2b3346] rounded-2xl p-6 flex flex-col items-center justify-center gap-3 bg-[#121827]/30 hover:bg-[#121827]/50 transition-colors cursor-pointer group"
                            >
                                <div className="w-10 h-10 rounded-xl bg-graphito-blue/10 flex items-center justify-center text-graphito-blue group-hover:scale-110 transition-transform">
                                    <Upload size={20} />
                                </div>
                                <div className="text-center">
                                    <p className="text-xs font-bold text-slate-200">
                                        {fileName ? "Archivo seleccionado (clic para cambiar)" : "Haz clic para subir archivo .c o .cpp"}
                                    </p>
                                </div>
                            </div>
                            <textarea
                                value={code}
                                onChange={(e) => setCode(e.target.value)}
                                className="w-full h-[100px] bg-[#121827]/40 border border-[#2b3346] rounded-xl p-3 text-xs text-white placeholder:text-slate-600 focus:outline-none focus:border-graphito-blue font-mono resize-none mt-2"
                                placeholder="O pega el código fuente del alumno aquí..."
                            />
                        </div>
                    </div>

                    {/* Footer */}
                    <div className="flex items-center justify-between px-8 py-6 border-t border-[#2b3346]/40 bg-black/5">
                        <button
                            type="button"
                            onClick={onClose}
                            className="text-sm font-bold text-slate-400 hover:text-white active:scale-95 focus:outline-none focus-visible:ring-2 focus-visible:ring-slate-400 focus-visible:ring-offset-2 focus-visible:ring-offset-[#121827] rounded-lg px-4 py-2 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
                        >
                            Cancelar
                        </button>
                        <GradientButton
                            onClick={handleStartAnalysis}
                            disabled={isLoading || problems.length === 0}
                            className="!py-3.5 !px-8 !rounded-2xl disabled:opacity-50"
                        >
                            <div className="flex items-center gap-2">
                                {isLoading ? (
                                    <>
                                        <Loader2 size={16} className="animate-spin" />
                                        <span>Procesando análisis dual...</span>
                                    </>
                                ) : (
                                    <span>Iniciar Análisis</span>
                                )}
                            </div>
                        </GradientButton>
                    </div>
                </AuthCard>
            </div>
        </div>
    );
}
