import { useState, useEffect, useRef } from "react";
import { X, Loader2, Plus, CheckCircle2, BookOpen } from "lucide-react";
import { useGSAP } from "@gsap/react";
import gsap from "gsap";
import { AuthCard } from "../layout/AuthCard";
import { GradientButton } from "../ui/GradientButton";
import { SynthwaveLine } from "../code/SynthwaveHighlighter";
import { api, CatalogProgramDetail, Problema } from "../../lib/api";

interface CatalogProgramModalProps {
    isOpen: boolean;
    programId: string | null;
    /** True when the teacher already has this program in their library. */
    alreadyAdded: boolean;
    onClose: () => void;
    /** Called with the created problem after the program was added to the library. */
    onAdded: (problem: Problema) => void;
    /** Closes the modal and navigates to the library. */
    onGoToBiblioteca: () => void;
}

export function CatalogProgramModal({
    isOpen,
    programId,
    alreadyAdded,
    onClose,
    onAdded,
    onGoToBiblioteca,
}: CatalogProgramModalProps) {
    const [program, setProgram] = useState<CatalogProgramDetail | null>(null);
    const [isLoadingProgram, setIsLoadingProgram] = useState(false);
    const [isAdding, setIsAdding] = useState(false);
    const [justAdded, setJustAdded] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const [shouldRender, setShouldRender] = useState(isOpen);
    const backdropRef = useRef<HTMLDivElement>(null);
    const contentRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        if (!isOpen || !programId) return;
        setShouldRender(true);
        setError(null);
        setIsAdding(false);
        setJustAdded(false);
        setProgram(null);
        setIsLoadingProgram(true);

        let cancelled = false;
        api.catalog
            .get(programId)
            .then((res) => {
                if (!cancelled) setProgram(res);
            })
            .catch((err: any) => {
                if (!cancelled) setError(err.message || "No se pudo cargar el programa del catálogo.");
            })
            .finally(() => {
                if (!cancelled) setIsLoadingProgram(false);
            });
        return () => {
            cancelled = true;
        };
    }, [isOpen, programId]);

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

    const handleAdd = async () => {
        if (!program || isAdding) return;
        setError(null);
        setIsAdding(true);
        try {
            const problem = await api.catalog.use(program.id);
            setJustAdded(true);
            onAdded(problem);
        } catch (err: any) {
            setError(err.message || "No se pudo agregar el programa a tu biblioteca.");
        } finally {
            setIsAdding(false);
        }
    };

    if (!shouldRender) return null;

    const lines = program ? program.codigo.split("\n") : [];
    const isInLibrary = justAdded || alreadyAdded;

    return (
        <div className="fixed inset-0 z-[100] flex items-center justify-center p-4">
            {/* Backdrop */}
            <div
                ref={backdropRef}
                className="absolute inset-0 bg-black/60 backdrop-blur-sm opacity-0"
                onClick={onClose}
            />

            {/* Modal Content */}
            <div ref={contentRef} className="w-full max-w-3xl opacity-0 transform scale-95">
                <AuthCard className="w-full p-0 overflow-hidden border-slate-200 dark:border-[#2b3346]/60">
                    {/* Header */}
                    <div className="flex items-start justify-between gap-4 px-8 py-6 border-b border-slate-200 dark:border-[#2b3346]/40">
                        <div className="min-w-0">
                            <h2 className="text-xl font-display font-bold text-slate-900 dark:text-white truncate">
                                {program?.titulo ?? "Programa del catálogo"}
                            </h2>
                            {program && (
                                <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                                    {program.materia_nombre} · {program.unidad_nombre}
                                </p>
                            )}
                        </div>
                        <button
                            onClick={onClose}
                            aria-label="Cerrar"
                            className="p-1 text-slate-400 hover:text-slate-700 dark:hover:text-white active:scale-95 focus:outline-none focus-visible:ring-2 focus-visible:ring-slate-400 rounded-md transition-all"
                        >
                            <X size={20} />
                        </button>
                    </div>

                    {/* Body */}
                    <div className="p-8 space-y-4">
                        {error && (
                            <div className="p-3 bg-red-500/10 border border-red-500/30 rounded-xl text-red-600 dark:text-red-300 text-xs font-medium">
                                {error}
                            </div>
                        )}

                        {isLoadingProgram ? (
                            <div className="flex flex-col items-center justify-center py-16 text-slate-500 dark:text-slate-400">
                                <Loader2 className="w-8 h-8 animate-spin text-graphito-blue mb-3" />
                                <p className="text-sm font-medium">Cargando programa...</p>
                            </div>
                        ) : program ? (
                            <>
                                <div className="flex items-center gap-3 text-xs text-slate-600 dark:text-slate-400">
                                    <span
                                        className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-widest border ${
                                            program.lenguaje === "cpp"
                                                ? "bg-graphito-violet/10 text-graphito-violet border-graphito-violet/20"
                                                : "bg-graphito-blue/10 text-graphito-blue border-graphito-blue/20"
                                        }`}
                                    >
                                        {program.lenguaje === "cpp" ? "C++" : "C"}
                                    </span>
                                    <span className="font-mono">{program.nombre_archivo}</span>
                                </div>

                                {justAdded && (
                                    <div
                                        role="status"
                                        className="flex items-center gap-2 p-3 bg-emerald-500/10 border border-emerald-500/30 rounded-xl text-emerald-700 dark:text-emerald-300 text-sm font-bold"
                                    >
                                        <CheckCircle2 size={18} className="shrink-0" />
                                        Agregado a tu biblioteca
                                    </div>
                                )}

                                {program.descripcion && (
                                    <p className="text-sm text-slate-700 dark:text-slate-300 leading-relaxed">
                                        {program.descripcion}
                                    </p>
                                )}

                                <div className="max-h-[360px] overflow-auto rounded-xl border border-slate-200 dark:border-[#2b3346] bg-slate-50 dark:bg-[#0b1020] py-3">
                                    <pre className="text-xs font-mono leading-relaxed text-slate-800 dark:text-slate-200">
                                        {lines.map((line, idx) => (
                                            <div key={idx} className="flex px-3">
                                                <span className="select-none w-8 shrink-0 pr-3 text-right text-slate-400 dark:text-slate-600">
                                                    {idx + 1}
                                                </span>
                                                <code className="whitespace-pre">
                                                    <SynthwaveLine line={line} />
                                                </code>
                                            </div>
                                        ))}
                                    </pre>
                                </div>
                            </>
                        ) : null}
                    </div>

                    {/* Footer */}
                    {/* Footer */}
                    <div className="flex flex-wrap items-center justify-between gap-3 px-8 py-6 border-t border-slate-200 dark:border-[#2b3346]/40 bg-slate-50/50 dark:bg-black/5">
                        <button
                            type="button"
                            onClick={onClose}
                            className="text-sm font-bold text-slate-500 hover:text-slate-900 dark:text-slate-400 dark:hover:text-white active:scale-95 focus:outline-none focus-visible:ring-2 focus-visible:ring-slate-400 rounded-lg px-4 py-2 transition-all"
                        >
                            {justAdded ? "Cerrar" : "Cancelar"}
                        </button>
                        <div className="flex flex-wrap items-center gap-3">
                            {isInLibrary ? (
                                <>
                                    {!justAdded && (
                                        <span className="flex items-center gap-1.5 text-sm font-bold text-emerald-600 dark:text-emerald-400">
                                            <CheckCircle2 size={16} />
                                            Ya está en tu biblioteca
                                        </span>
                                    )}
                                    <GradientButton onClick={onGoToBiblioteca} className="!py-3 !px-6 !rounded-2xl">
                                        <div className="flex items-center gap-2">
                                            <BookOpen size={16} />
                                            <span>Ir a la biblioteca</span>
                                        </div>
                                    </GradientButton>
                                </>
                            ) : (
                                <GradientButton
                                    onClick={handleAdd}
                                    disabled={!program || isAdding}
                                    className="!py-3 !px-6 !rounded-2xl"
                                >
                                    <div className="flex items-center gap-2">
                                        {isAdding ? (
                                            <>
                                                <Loader2 size={16} className="animate-spin" />
                                                <span>Agregando...</span>
                                            </>
                                        ) : (
                                            <>
                                                <Plus size={16} />
                                                <span>Agregar a mi biblioteca</span>
                                            </>
                                        )}
                                    </div>
                                </GradientButton>
                            )}
                        </div>
                    </div>
                </AuthCard>
            </div>
        </div>
    );
}
