import React, { useId, useState, useRef } from "react";
import { Upload, Database, Plus, Loader2, Info, X } from "lucide-react";
import { Modal } from "../components/ui/Modal";
import { Button } from "../components/ui/Button";
import { api, IS_DEMO_MODE } from "../lib/api";
import { downloadTextFile } from "../lib/downloadTextFile";

/** Keep in sync with the backend's MAX_REFERENCE_VARIANTS (it enforces the limit too). */
const MAX_VARIANTS = 3;

interface VariantDraft {
    titulo: string;
    instrucciones: string;
}

interface NewReferenceModalProps {
    isOpen: boolean;
    onClose: () => void;
    /** Called after the problem and its reference were saved; receives the new problem id. */
    onSuccess?: (problemId: number) => void;
}

export function NewReferenceModal({ isOpen, onClose, onSuccess }: NewReferenceModalProps) {
    const [title, setTitle] = useState("");
    const [description, setDescription] = useState("");
    const [code, setCode] = useState("");
    const [language, setLanguage] = useState<"c" | "cpp">("c");
    const [fileName, setFileName] = useState<string | null>(null);
    const [isLoading, setIsLoading] = useState(false);
    const [loadingStep, setLoadingStep] = useState<"creating" | "indexing" | "generating" | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [isLoadingExample, setIsLoadingExample] = useState(false);

    // AI variants: an optional short title plus the instructions the LLM follows for that implementation.
    const [variants, setVariants] = useState<VariantDraft[]>([{ titulo: "", instrucciones: "" }]);
    // Set once the problem and its reference exist, so a retry after a failed variant never duplicates them.
    const [createdProblemId, setCreatedProblemId] = useState<number | null>(null);
    const fileInputRef = useRef<HTMLInputElement>(null);
    const uid = useId();
    const ids = {
        title: `ref-title-${uid}`,
        language: `ref-lang-${uid}`,
        code: `ref-code-${uid}`,
        description: `ref-desc-${uid}`,
        variant: (i: number, field: "title" | "prompt") => `ref-variant-${field}-${i}-${uid}`,
    };

    // Closing abandons a half-created problem's retry state, so the next open starts from scratch.
    const handleClose = () => {
        setCreatedProblemId(null);
        setVariants([{ titulo: "", instrucciones: "" }]);
        setError(null);
        onClose();
    };

    const updateVariant = (i: number, patch: Partial<VariantDraft>) =>
        setVariants((rows) => rows.map((row, idx) => (idx === i ? { ...row, ...patch } : row)));

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

    // Gives someone without a program a catalog one to download and upload themselves.
    const handleUseExample = async () => {
        setError(null);
        setIsLoadingExample(true);
        try {
            const subjects = await api.catalog.list();
            const first = subjects.flatMap((s) => s.unidades).flatMap((u) => u.programas)[0];
            if (!first) throw new Error("No hay programas de ejemplo disponibles.");
            const program = await api.catalog.get(first.id);
            downloadTextFile(program.nombre_archivo, program.codigo);
        } catch (err: any) {
            setError(err.message || "No se pudo cargar el código de ejemplo.");
        } finally {
            setIsLoadingExample(false);
        }
    };

    const handleSubmit = async () => {
        if (IS_DEMO_MODE) {
            setError("La creación de códigos de referencia está deshabilitada en el Modo Demostración.");
            return;
        }

        if (!title.trim()) {
            setError("Por favor ingresa un título para el ejercicio.");
            return;
        }
        if (!code.trim()) {
            setError("Por favor sube o escribe el código fuente de referencia.");
            return;
        }

        // Rows left completely blank are ignored; a half-filled row is a mistake worth stopping on.
        const filled = variants.filter((v) => v.titulo.trim() || v.instrucciones.trim());
        if (filled.some((v) => !v.titulo.trim() || !v.instrucciones.trim())) {
            setError("Cada implementación necesita un título corto y sus instrucciones.");
            return;
        }

        setError(null);
        setIsLoading(true);
        setLoadingStep("creating");
        try {
            let problemId = createdProblemId;
            if (problemId === null) {
                const prob = await api.problems.create(title, description || "Solución de referencia", language);
                problemId = prob.id;
                setLoadingStep("indexing");
                await api.problems.addReference(problemId, "Docente", code, language);
                setCreatedProblemId(problemId);
            }

            // One call per variant so a failure names the implementation; the rest still get created.
            const failed: VariantDraft[] = [];
            const failures: string[] = [];
            for (const v of filled) {
                setLoadingStep("generating");
                try {
                    await api.problems.addVariant(problemId, v.titulo.trim(), v.instrucciones.trim());
                } catch (err: any) {
                    failed.push(v);
                    failures.push(`"${v.titulo.trim()}": ${err.message || "error al generar"}`);
                }
            }
            if (failed.length > 0) {
                onSuccess?.(problemId); // the problem and its reference exist already: refresh the library
                setVariants(failed);
                setError(`La referencia se guardó, pero no se generaron: ${failures.join("; ")}. Puedes reintentar o cerrar.`);
                return;
            }

            setTitle("");
            setDescription("");
            setCode("");
            setFileName(null);
            setVariants([{ titulo: "", instrucciones: "" }]);
            setCreatedProblemId(null);
            onSuccess?.(problemId);
            onClose();
        } catch (err: any) {
            setError(err.message || "Error al agregar la referencia.");
        } finally {
            setIsLoading(false);
            setLoadingStep(null);
        }
    };

    return (
        <Modal
            isOpen={isOpen}
            onClose={handleClose}
            title="Agregar código de referencia"
            maxWidth="4xl"
            fixedHeight="h-auto max-h-[94vh]"
            footer={
                <div className="flex items-center justify-end gap-4">
                    <Button
                        type="button"
                        variant="ghost"
                        onClick={handleClose}
                        disabled={isLoading}
                    >
                        Cancelar
                    </Button>
                    <Button
                        type="button"
                        variant="gradient"
                        data-tour="ref-submit"
                        onClick={handleSubmit}
                        disabled={isLoading || IS_DEMO_MODE}
                        isLoading={isLoading}
                        title={IS_DEMO_MODE ? "No disponible en el Modo Demostración" : undefined}
                        leftIcon={!isLoading ? <Database size={16} /> : undefined}
                        className="!py-3 !px-8"
                    >
                        {isLoading
                            ? loadingStep === "creating"
                                ? "Registrando problema..."
                                : loadingStep === "generating"
                                    ? "Generando variantes con IA..."
                                    : "Indexando en ChromaDB..."
                            : "Agregar código de referencia"}
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

            {isLoading && (
                <div className="p-4 rounded-2xl bg-gradient-to-r from-graphito-blue/15 to-graphito-violet/15 border border-graphito-blue/30 flex items-center gap-3.5 shadow-sm">
                    <Loader2 className="w-5 h-5 text-graphito-blue animate-spin shrink-0" />
                    <div className="min-w-0 flex-1">
                        <p className="text-xs font-bold text-slate-900 dark:text-white">
                            {loadingStep === "creating"
                                ? "Registrando problema de referencia..."
                                : loadingStep === "generating"
                                    ? "Generando implementaciones alternativas con IA..."
                                    : "Generando embeddings vectoriales e indexando en ChromaDB..."}
                        </p>
                        <p className="text-[11px] text-slate-500 dark:text-slate-400">
                            {loadingStep === "creating"
                                ? "Guardando metadatos y código fuente canónico en la base de datos."
                                : loadingStep === "generating"
                                    ? "Cada variante se genera, se vectoriza y se guarda; puede tardar unos segundos."
                                    : "Calculando vectores para comparaciones y búsquedas semánticas inmediatas."}
                        </p>
                    </div>
                </div>
            )}

            {IS_DEMO_MODE && (
                <div className="p-4 bg-amber-500/10 border border-amber-500/30 rounded-xl text-amber-800 dark:text-amber-300 text-xs flex items-start gap-2.5">
                    <Info size={16} className="shrink-0 mt-0.5" aria-hidden="true" />
                    <div>
                        <span className="font-bold">Modo Demostración (Solo Lectura):</span> La creación de nuevos problemas y subida de archivos está desactivada en esta versión de muestra. Puedes explorar los ejercicios precargados en la biblioteca.
                    </div>
                </div>
            )}

            {error && (
                <div className="p-3 bg-red-500/10 border border-red-500/30 rounded-xl text-red-600 dark:text-red-300 text-xs font-medium">
                    {error}
                </div>
            )}

            {/* Row: Title & Language */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="md:col-span-2 space-y-1.5" data-tour="ref-title">
                    <label htmlFor={ids.title} className="text-[10px] uppercase font-black tracking-widest text-slate-500 dark:text-slate-400">
                        Título del Problema / Ejercicio <span aria-hidden="true" className="text-rose-500">*</span>
                    </label>
                    <input
                        id={ids.title}
                        type="text"
                        required
                        value={title}
                        onChange={(e) => setTitle(e.target.value)}
                        disabled={isLoading}
                        placeholder="Ej. Búsqueda Binaria en Arreglos"
                        className="w-full bg-slate-50 dark:bg-[#121827]/40 border border-slate-200 dark:border-[#2b3346] text-slate-900 dark:text-white placeholder:text-slate-400 dark:placeholder:text-slate-600 rounded-xl py-3 px-4 focus:outline-none focus:border-graphito-blue text-sm transition-colors disabled:opacity-60"
                    />
                </div>
                <div className="space-y-1.5">
                    <label htmlFor={ids.language} className="text-[10px] uppercase font-black tracking-widest text-slate-500 dark:text-slate-400">
                        Lenguaje
                    </label>
                    <select
                        id={ids.language}
                        value={language}
                        onChange={(e) => setLanguage(e.target.value as "c" | "cpp")}
                        disabled={isLoading}
                        className="w-full bg-slate-50 dark:bg-[#121827] border border-slate-200 dark:border-[#2b3346] text-slate-900 dark:text-white rounded-xl py-3 px-4 focus:outline-none focus:border-graphito-blue text-sm cursor-pointer transition-colors disabled:opacity-60"
                    >
                        <option value="c" className="bg-white dark:bg-slate-900 text-slate-900 dark:text-white">C (Estándar C99/C11)</option>
                        <option value="cpp" className="bg-white dark:bg-slate-900 text-slate-900 dark:text-white">C++ (C++14/C++17)</option>
                    </select>
                </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                {/* Left Column: Source Code */}
                <div className="space-y-4" data-tour="ref-code">
                    <label htmlFor={ids.code} className="text-[10px] uppercase font-black tracking-widest text-slate-500 dark:text-slate-400">
                        Código Fuente <span aria-hidden="true" className="text-rose-500">*</span> {fileName && <span className="text-graphito-blue">({fileName})</span>}
                    </label>
                    <div
                        onClick={() => fileInputRef.current?.click()}
                        className="border-2 border-dashed border-slate-200 dark:border-[#2b3346] rounded-2xl p-6 flex flex-col items-center justify-center gap-3 bg-slate-50 dark:bg-[#121827]/30 hover:bg-slate-100 dark:hover:bg-[#121827]/50 transition-colors cursor-pointer group"
                    >
                        <div className="w-10 h-10 rounded-xl bg-graphito-blue/10 flex items-center justify-center text-graphito-blue group-hover:scale-110 transition-transform">
                            <Upload size={20} />
                        </div>
                        <div className="text-center">
                            <p className="text-xs font-bold text-slate-700 dark:text-slate-200">
                                {fileName ? "Archivo seleccionado (clic para cambiar)" : "Haz clic para seleccionar o arrastra"}
                            </p>
                            <p className="text-[11px] text-slate-500 mt-0.5">
                                Archivos .c o .cpp
                            </p>
                        </div>
                        <Button
                            type="button"
                            variant="outline"
                            size="sm"
                            leftIcon={<Upload size={14} />}
                            onClick={(e) => {
                                e.stopPropagation();
                                fileInputRef.current?.click();
                            }}
                        >
                            {fileName ? "Cambiar archivo" : "Seleccionar archivo"}
                        </Button>
                    </div>
                    <button
                        type="button"
                        onClick={handleUseExample}
                        disabled={isLoading || isLoadingExample}
                        className="text-xs font-bold text-graphito-blue hover:underline disabled:opacity-60 focus:outline-none focus-visible:ring-2 focus-visible:ring-graphito-blue rounded"
                    >
                        {isLoadingExample ? "Preparando archivo…" : "¿No tienes un código? Haz clic aquí para descargar uno"}
                    </button>
                    <textarea
                        id={ids.code}
                        required
                        value={code}
                        onChange={(e) => setCode(e.target.value)}
                        disabled={isLoading}
                        className="w-full h-[120px] bg-slate-50 dark:bg-[#121827]/40 border border-slate-200 dark:border-[#2b3346] rounded-xl p-3 text-xs text-slate-900 dark:text-white placeholder:text-slate-400 dark:placeholder:text-slate-600 focus:outline-none focus:border-graphito-blue font-mono resize-none transition-colors disabled:opacity-60"
                        placeholder="O pega directamente el código fuente aquí..."
                    />
                </div>

                {/* Right Column: Description */}
                <div className="space-y-4">
                    <div className="flex items-center justify-between">
                        <label htmlFor={ids.description} className="text-[10px] uppercase font-black tracking-widest text-slate-500 dark:text-slate-400">
                            Enunciado / Descripción
                        </label>
                    </div>
                    <textarea
                        id={ids.description}
                        value={description}
                        onChange={(e) => setDescription(e.target.value)}
                        disabled={isLoading}
                        className="w-full h-[200px] bg-slate-50 dark:bg-[#121827]/40 border border-slate-200 dark:border-[#2b3346] rounded-2xl p-4 text-sm text-slate-900 dark:text-white placeholder:text-slate-400 dark:placeholder:text-slate-600 focus:outline-none focus:border-graphito-blue/50 transition-all resize-none font-body disabled:opacity-60"
                        placeholder="Escribe el enunciado del ejercicio y restricciones esperadas..."
                    />
                </div>
            </div>

            {/* Bottom Section: other implementations generated with AI */}
            <div className="bg-slate-50 dark:bg-[#121827]/50 border border-slate-200 dark:border-[#2b3346]/40 rounded-2xl p-6 space-y-4 transition-colors">
                <div>
                    <h3 className="text-xs font-bold text-slate-800 dark:text-white">
                        ¿Quieres comparar también contra otras implementaciones?
                    </h3>
                    <p className="text-[11px] text-slate-500 dark:text-slate-400 mt-1">
                        Opcional. Describe cada variante y la IA la generará a partir de tu referencia (máximo {MAX_VARIANTS}).
                        Las entregas se compararán también contra ellas, sin reemplazar tu referencia.
                    </p>
                </div>

                {variants.map((variant, i) => (
                    <div key={i} className="grid grid-cols-1 md:grid-cols-3 gap-3 items-start">
                        <div className="space-y-1.5">
                            <label htmlFor={ids.variant(i, "title")} className="text-[10px] uppercase font-black tracking-widest text-slate-500 dark:text-slate-400 ml-1">
                                Título de la implementación {i + 1}
                            </label>
                            <input
                                id={ids.variant(i, "title")}
                                type="text"
                                maxLength={120}
                                value={variant.titulo}
                                onChange={(e) => updateVariant(i, { titulo: e.target.value })}
                                disabled={isLoading}
                                placeholder="Ej: Usando factorial"
                                className="w-full bg-white dark:bg-[#121827]/40 border border-slate-200 dark:border-[#2b3346] rounded-xl py-2.5 px-3 text-xs text-slate-900 dark:text-white placeholder:text-slate-400 dark:placeholder:text-slate-600 focus:outline-none focus:border-graphito-blue/50 transition-all disabled:opacity-60"
                            />
                        </div>
                        <div className="md:col-span-2 space-y-1.5">
                            <label htmlFor={ids.variant(i, "prompt")} className="text-[10px] uppercase font-black tracking-widest text-slate-500 dark:text-slate-400 ml-1">
                                Instrucciones para la IA
                            </label>
                            <div className="flex gap-2">
                                <textarea
                                    id={ids.variant(i, "prompt")}
                                    maxLength={2000}
                                    value={variant.instrucciones}
                                    onChange={(e) => updateVariant(i, { instrucciones: e.target.value })}
                                    disabled={isLoading}
                                    placeholder="Ej: Resuelve el problema usando recursión con una función factorial."
                                    className="w-full h-20 bg-white dark:bg-[#121827]/40 border border-slate-200 dark:border-[#2b3346] rounded-xl p-3 text-xs text-slate-900 dark:text-white placeholder:text-slate-400 dark:placeholder:text-slate-600 focus:outline-none focus:border-graphito-blue/50 transition-all resize-none disabled:opacity-60"
                                />
                                {variants.length > 1 && (
                                    <button
                                        type="button"
                                        aria-label={`Quitar implementación ${i + 1}`}
                                        disabled={isLoading}
                                        onClick={() => setVariants((rows) => rows.filter((_, idx) => idx !== i))}
                                        className="h-8 w-8 shrink-0 rounded-lg flex items-center justify-center text-slate-500 hover:bg-slate-200/60 dark:hover:bg-white/5 focus:outline-none focus-visible:ring-2 focus-visible:ring-graphito-blue disabled:opacity-50"
                                    >
                                        <X size={16} />
                                    </button>
                                )}
                            </div>
                        </div>
                    </div>
                ))}

                <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    leftIcon={<Plus size={14} />}
                    disabled={isLoading || variants.length >= MAX_VARIANTS}
                    onClick={() => setVariants((rows) => [...rows, { titulo: "", instrucciones: "" }])}
                >
                    Agregar otra implementación ({variants.length}/{MAX_VARIANTS})
                </Button>
            </div>        </Modal>
    );
}
