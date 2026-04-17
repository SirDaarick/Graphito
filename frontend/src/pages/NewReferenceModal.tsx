import { useState, useEffect } from "react";
import { X, Upload, Sparkles, Minus, Plus, Database } from "lucide-react";
import { AuthCard } from "../components/layout/AuthCard";
import { GradientButton } from "../components/ui/GradientButton";

interface NewReferenceModalProps {
    isOpen: boolean;
    onClose: () => void;
}

export function NewReferenceModal({ isOpen, onClose }: NewReferenceModalProps) {
    const [variations, setVariations] = useState(3);
    const [generateAI, setGenerateAI] = useState(true);
    const [isAnimating, setIsAnimating] = useState(false);
    const [shouldRender, setShouldRender] = useState(isOpen);

    useEffect(() => {
        if (isOpen) {
            setShouldRender(true);
            // Pequeño delay para permitir que el DOM se monte antes de la animación
            const timer = setTimeout(() => setIsAnimating(true), 10);
            return () => clearTimeout(timer);
        } else {
            setIsAnimating(false);
            // Esperar a que termine la animación de salida (300ms) antes de desmontar
            const timer = setTimeout(() => setShouldRender(false), 300);
            return () => clearTimeout(timer);
        }
    }, [isOpen]);

    if (!shouldRender) return null;

    return (
        <div className={`fixed inset-0 z-[100] flex items-center justify-center p-4 transition-all duration-300 ${isAnimating ? 'visible' : 'invisible'}`}>
            {/* Backdrop */}
            <div
                className={`absolute inset-0 bg-black/60 backdrop-blur-sm transition-opacity duration-300 ${isAnimating ? 'opacity-100' : 'opacity-0'}`}
                onClick={onClose}
            />

            {/* Modal Content */}
            <div className={`w-full max-w-4xl transition-all duration-300 transform ${isAnimating ? 'opacity-100 scale-100' : 'opacity-0 scale-95'}`}>
                <AuthCard className="w-full p-0 overflow-hidden border-[#2b3346]/60">
                    {/* Header */}
                    <div className="flex items-center justify-between px-8 py-6 border-b border-[#2b3346]/40">
                        <h2 className="text-xl font-display font-bold text-white">
                            Agregar código de referencia
                        </h2>
                        <button
                            onClick={onClose}
                            className="p-1 text-slate-500 hover:text-white transition-colors"
                        >
                            <X size={20} />
                        </button>
                    </div>

                    {/* Body */}
                    <div className="p-8 space-y-8">
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                            {/* Left Column: Source Code */}
                            <div className="space-y-4">
                                <label className="text-[10px] uppercase font-black tracking-widest text-slate-500">
                                    Código Fuente
                                </label>
                                <div className="border-2 border-dashed border-[#2b3346] rounded-2xl p-10 flex flex-col items-center justify-center gap-4 bg-[#121827]/30 hover:bg-[#121827]/50 transition-colors cursor-pointer group">
                                    <div className="w-12 h-12 rounded-xl bg-graphito-blue/10 flex items-center justify-center text-graphito-blue group-hover:scale-110 transition-transform">
                                        <Upload size={24} />
                                    </div>
                                    <div className="text-center">
                                        <p className="text-sm font-bold text-slate-200">
                                            Suelta tus archivos aquí o haz clic para buscar
                                        </p>
                                        <p className="text-xs text-slate-500 mt-1">
                                            Archivos .c o .cpp (Máx. 5MB)
                                        </p>
                                    </div>
                                </div>
                            </div>

                            {/* Right Column: Description */}
                            <div className="space-y-4">
                                <div className="flex items-center justify-between">
                                    <label className="text-[10px] uppercase font-black tracking-widest text-slate-500">
                                        Descripción
                                    </label>
                                    <button className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-graphito-card/60 border border-[#2b3346] text-[10px] font-bold text-slate-400 hover:text-white transition-colors">
                                        <Sparkles size={12} className="text-graphito-blue" />
                                        Generar descripción con IA
                                    </button>
                                </div>
                                <textarea
                                    className="w-full h-[180px] bg-[#121827]/40 border border-[#2b3346] rounded-2xl p-4 text-sm text-white placeholder:text-slate-600 focus:outline-none focus:border-graphito-blue/50 transition-all resize-none"
                                    placeholder="Escribe una breve explicación de lo que este código resuelve..."
                                />
                            </div>
                        </div>

                        {/* Bottom Section: AI Variations */}
                        <div className="bg-[#121827]/50 border border-[#2b3346]/40 rounded-2xl p-6 space-y-6">
                            <div className="flex items-center gap-3">
                                <div
                                    className={`w-5 h-5 rounded flex items-center justify-center cursor-pointer transition-colors ${generateAI ? 'bg-graphito-blue' : 'bg-[#121827]'}`}
                                    onClick={() => setGenerateAI(!generateAI)}
                                >
                                    {generateAI && <Check size={14} className="text-white" />}
                                </div>
                                <span className="text-xs font-bold text-white">
                                    Generar variaciones mediante inteligencia artificial
                                </span>
                            </div>

                            <div className="grid grid-cols-1 md:grid-cols-3 gap-6 items-end">
                                <div className="md:col-span-2 space-y-2">
                                    <label className="text-[10px] uppercase font-black tracking-widest text-slate-500 ml-1">
                                        Instrucciones para la IA
                                    </label>
                                    <textarea
                                        className="w-full h-24 bg-[#121827]/40 border border-[#2b3346] rounded-xl p-3 text-xs text-white placeholder:text-slate-600 focus:outline-none focus:border-graphito-blue/50 transition-all resize-none font-medium"
                                        placeholder="Ej: Generar una versión más optimizada y otra con comentarios detallados..."
                                    />
                                </div>
                                <div className="space-y-2">
                                    <label className="text-[10px] uppercase font-black tracking-widest text-slate-500 ml-1">
                                        Número de variaciones
                                    </label>
                                    <div className="flex items-center bg-[#121827]/60 border border-[#2b3346] rounded-xl overflow-hidden h-24">
                                        <button
                                            onClick={() => setVariations(Math.max(1, variations - 1))}
                                            className="flex-1 h-full flex items-center justify-center text-slate-400 hover:bg-white/5 transition-colors"
                                        >
                                            <Minus size={18} />
                                        </button>
                                        <div className="w-12 text-center text-2xl font-black text-white">
                                            {variations}
                                        </div>
                                        <button
                                            onClick={() => setVariations(Math.min(10, variations + 1))}
                                            className="flex-1 h-full flex items-center justify-center text-slate-400 hover:bg-white/5 transition-colors"
                                        >
                                            <Plus size={18} />
                                        </button>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>

                    {/* Footer */}
                    <div className="flex items-center justify-end gap-6 px-8 py-6 border-t border-[#2b3346]/40 bg-black/10">
                        <button
                            onClick={onClose}
                            className="text-sm font-bold text-slate-400 hover:text-white transition-colors"
                        >
                            Cancelar
                        </button>
                        <GradientButton className="!py-3 !px-8">
                            <div className="flex items-center gap-2">
                                <Database size={16} />
                                <span>Agregar código de referencia</span>
                            </div>
                        </GradientButton>
                    </div>
                </AuthCard>
            </div>
        </div>
    );
}

// Check icon for the custom checkbox
function Check({ size, className }: { size: number, className?: string }) {
    return (
        <svg
            width={size}
            height={size}
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="4"
            strokeLinecap="round"
            strokeLinejoin="round"
            className={className}
        >
            <polyline points="20 6 9 17 4 12" />
        </svg>
    );
}
