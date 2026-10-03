import { useState, useEffect, useRef } from "react";
import { X, Upload, Database, Loader2, Check, Minus, Plus } from "lucide-react";
import { useGSAP } from "@gsap/react";
import gsap from "gsap";
import { AuthCard } from "../components/layout/AuthCard";
import { GradientButton } from "../components/ui/GradientButton";
import { api, IS_DEMO_MODE } from "../lib/api";

interface NewReferenceModalProps {
    isOpen: boolean;
    onClose: () => void;
    onSuccess?: () => void;
}

export function NewReferenceModal({ isOpen, onClose, onSuccess }: NewReferenceModalProps) {
    const [title, setTitle] = useState("");
    const [description, setDescription] = useState("");
    const [code, setCode] = useState("");
    const [language, setLanguage] = useState<"c" | "cpp">("c");
    const [fileName, setFileName] = useState<string | null>(null);
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const [variations, setVariations] = useState(3);
    const [generateAI, setGenerateAI] = useState(true);
    const [shouldRender, setShouldRender] = useState(isOpen);
    const backdropRef = useRef<HTMLDivElement>(null);
    const contentRef = useRef<HTMLDivElement>(null);
    const fileInputRef = useRef<HTMLInputElement>(null);

    useEffect(() => {
        if (isOpen) {
            setShouldRender(true);
        }
    }, [isOpen]);

    useGSAP(() => {
        if (!shouldRender) return;

        if (isOpen) {
            gsap.fromTo(backdropRef.current, 
                { opacity: 0 }, 
                { opacity: 1, duration: 0.3, ease: "power2.out" }
            );
            gsap.fromTo(contentRef.current, 
                { opacity: 0, scale: 0.95 }, 
                { opacity: 1, scale: 1, duration: 0.4, ease: "back.out(1.2)" }
            );
        } else {
            gsap.to(backdropRef.current, { opacity: 0, duration: 0.3, ease: "power2.in" });
            gsap.to(contentRef.current, { 
                opacity: 0, 
                scale: 0.95, 
                duration: 0.3, 
                ease: "power2.in",
                onComplete: () => setShouldRender(false) 
            });
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

        setError(null);
        setIsLoading(true);
        try {
            const prob = await api.problems.create(title, description || "Solución de referencia", language);
            await api.problems.addReference(prob.id, "Docente", code, language);
            setTitle("");
            setDescription("");
            setCode("");
            setFileName(null);
            onSuccess?.();
            onClose();
        } catch (err: any) {
            setError(err.message || "Error al agregar la referencia.");
        } finally {
            setIsLoading(false);
        }
    };

    if (!shouldRender) return null;

    return (
        <div className="fixed inset-0 z-[100] flex items-center justify-center p-4">
            {/* Backdrop */}
            <div
                ref={backdropRef}
                className="absolute inset-0 bg-black/60 backdrop-blur-sm opacity-0"
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
            <div ref={contentRef} className="w-full max-w-4xl opacity-0 transform scale-95 max-h-[90vh] flex flex-col">
                <AuthCard className="w-full p-0 overflow-hidden flex flex-col max-h-[90vh] bg-white dark:bg-graphito-card border border-slate-200 dark:border-[#2b3346]/60 shadow-2xl rounded-2xl transition-colors">
                    {/* Header (Fijo en la parte superior) */}
                    <div className="flex items-center justify-between px-8 py-6 border-b border-slate-200 dark:border-[#2b3346]/40 shrink-0">
                        <h2 className="text-xl font-display font-bold text-slate-900 dark:text-white">
                            Agregar código de referencia
                        </h2>
                        <button
                            onClick={onClose}
                            className="p-1 text-slate-400 hover:text-slate-700 dark:text-slate-500 dark:hover:text-white active:scale-95 focus:outline-none focus-visible:ring-2 focus-visible:ring-slate-400 rounded-md disabled:opacity-50 disabled:cursor-not-allowed transition-all"
                        >
                            <X size={20} />
                        </button>
                    </div>

                    {/* Body (Con scroll vertical si sobrepasa la pantalla) */}
                    <div className="p-8 space-y-6 overflow-y-auto flex-1">
                        {IS_DEMO_MODE && (
                            <div className="p-4 bg-amber-500/10 border border-amber-500/30 rounded-xl text-amber-800 dark:text-amber-300 text-xs flex items-start gap-2.5">
                                <span className="text-base leading-none">ℹ️</span>
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
                            <div className="md:col-span-2 space-y-1.5">
                                <label className="text-[10px] uppercase font-black tracking-widest text-slate-500 dark:text-slate-400">
                                    Título del Problema / Ejercicio
                                </label>
                                <input
                                    type="text"
                                    value={title}
                                    onChange={(e) => setTitle(e.target.value)}
                                    placeholder="Ej. Búsqueda Binaria en Arreglos"
                                    className="w-full bg-slate-50 dark:bg-[#121827]/40 border border-slate-200 dark:border-[#2b3346] text-slate-900 dark:text-white placeholder:text-slate-400 dark:placeholder:text-slate-600 rounded-xl py-3 px-4 focus:outline-none focus:border-graphito-blue text-sm transition-colors"
                                />
                            </div>
                            <div className="space-y-1.5">
                                <label className="text-[10px] uppercase font-black tracking-widest text-slate-500 dark:text-slate-400">
                                    Lenguaje
                                </label>
                                <select
                                    value={language}
                                    onChange={(e) => setLanguage(e.target.value as "c" | "cpp")}
                                    className="w-full bg-slate-50 dark:bg-[#121827] border border-slate-200 dark:border-[#2b3346] text-slate-900 dark:text-white rounded-xl py-3 px-4 focus:outline-none focus:border-graphito-blue text-sm cursor-pointer transition-colors"
                                >
                                    <option value="c" className="bg-white dark:bg-slate-900 text-slate-900 dark:text-white">C (Estándar C99/C11)</option>
                                    <option value="cpp" className="bg-white dark:bg-slate-900 text-slate-900 dark:text-white">C++ (C++14/C++17)</option>
                                </select>
                            </div>
                        </div>

                        <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                            {/* Left Column: Source Code */}
                            <div className="space-y-4">
                                <label className="text-[10px] uppercase font-black tracking-widest text-slate-500">
                                    Código Fuente {fileName && <span className="text-graphito-blue">({fileName})</span>}
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
                                </div>
                                <textarea
                                    value={code}
                                    onChange={(e) => setCode(e.target.value)}
                                    className="w-full h-[120px] bg-slate-50 dark:bg-[#121827]/40 border border-slate-200 dark:border-[#2b3346] rounded-xl p-3 text-xs text-slate-900 dark:text-white placeholder:text-slate-400 dark:placeholder:text-slate-600 focus:outline-none focus:border-graphito-blue font-mono resize-none transition-colors"
                                    placeholder="O pega directamente el código fuente aquí..."
                                />
                            </div>

                            {/* Right Column: Description */}
                            <div className="space-y-4">
                                <div className="flex items-center justify-between">
                                    <label className="text-[10px] uppercase font-black tracking-widest text-slate-500">
                                        Enunciado / Descripción
                                    </label>
                                </div>
                                <textarea
                                    value={description}
                                    onChange={(e) => setDescription(e.target.value)}
                                    className="w-full h-[200px] bg-slate-50 dark:bg-[#121827]/40 border border-slate-200 dark:border-[#2b3346] rounded-2xl p-4 text-sm text-slate-900 dark:text-white placeholder:text-slate-400 dark:placeholder:text-slate-600 focus:outline-none focus:border-graphito-blue/50 transition-all resize-none font-body"
                                    placeholder="Escribe el enunciado del ejercicio y restricciones esperadas..."
                                />
                            </div>
                        </div>

                        {/* Bottom Section: AI Variations */}
                        <div className="bg-slate-50 dark:bg-[#121827]/50 border border-slate-200 dark:border-[#2b3346]/40 rounded-2xl p-6 space-y-6 transition-colors">
                            <div className="flex items-center gap-3">
                                <div
                                    className={`w-5 h-5 rounded flex items-center justify-center cursor-pointer transition-all active:scale-95 ${generateAI ? 'bg-graphito-blue' : 'bg-slate-200 dark:bg-[#121827]'}`}
                                    onClick={() => setGenerateAI(!generateAI)}
                                >
                                    {generateAI && <Check size={14} className="text-white" />}
                                </div>
                                <span className="text-xs font-bold text-slate-800 dark:text-white">
                                    Generar variaciones mediante inteligencia artificial
                                </span>
                            </div>

                            <div className="grid grid-cols-1 md:grid-cols-3 gap-6 items-end">
                                <div className="md:col-span-2 space-y-2">
                                    <label className="text-[10px] uppercase font-black tracking-widest text-slate-500 ml-1">
                                        Instrucciones para la IA
                                    </label>
                                    <textarea
                                        className="w-full h-24 bg-white dark:bg-[#121827]/40 border border-slate-200 dark:border-[#2b3346] rounded-xl p-3 text-xs text-slate-900 dark:text-white placeholder:text-slate-400 dark:placeholder:text-slate-600 focus:outline-none focus:border-graphito-blue/50 transition-all resize-none font-medium"
                                        placeholder="Ej: Generar una versión más optimizada y otra con comentarios detallados..."
                                    />
                                </div>
                                <div className="space-y-2">
                                    <label className="text-[10px] uppercase font-black tracking-widest text-slate-500 ml-1">
                                        Número de variaciones
                                    </label>
                                    <div className="flex items-center bg-white dark:bg-[#121827]/60 border border-slate-200 dark:border-[#2b3346] rounded-xl overflow-hidden h-24 transition-colors">
                                        <button
                                            onClick={() => setVariations(Math.max(1, variations - 1))}
                                            className="flex-1 h-full flex items-center justify-center text-slate-500 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-white/5 active:scale-95 focus:outline-none disabled:opacity-50 disabled:cursor-not-allowed transition-all"
                                        >
                                            <Minus size={18} />
                                        </button>
                                        <div className="w-12 text-center text-2xl font-black text-slate-900 dark:text-white">
                                            {variations}
                                        </div>
                                        <button
                                            onClick={() => setVariations(Math.min(10, variations + 1))}
                                            className="flex-1 h-full flex items-center justify-center text-slate-500 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-white/5 active:scale-95 focus:outline-none disabled:opacity-50 disabled:cursor-not-allowed transition-all"
                                        >
                                            <Plus size={18} />
                                        </button>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>

                    {/* Footer (Fijo en la parte inferior) */}
                    <div className="flex items-center justify-end gap-6 px-8 py-6 border-t border-slate-200 dark:border-[#2b3346]/40 bg-slate-50 dark:bg-black/10 shrink-0 transition-colors">
                        <button
                            type="button"
                            onClick={onClose}
                            className="text-sm font-bold text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white active:scale-95 focus:outline-none focus-visible:ring-2 focus-visible:ring-slate-400 rounded-lg px-4 py-2 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
                        >
                            Cancelar
                        </button>
                        <GradientButton
                            onClick={handleSubmit}
                            disabled={isLoading}
                            className="!py-3 !px-8 disabled:opacity-50"
                        >
                            <div className="flex items-center gap-2">
                                {isLoading ? (
                                    <>
                                        <Loader2 size={16} className="animate-spin" />
                                        <span>Indexando en ChromaDB...</span>
                                    </>
                                ) : (
                                    <>
                                        <Database size={16} />
                                        <span>Agregar código de referencia</span>
                                    </>
                                )}
                            </div>
                        </GradientButton>
                    </div>
                </AuthCard>
            </div>
        </div>
    );
}