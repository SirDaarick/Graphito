import { useState, useEffect } from "react";
import { X, Upload, CheckCircle2 } from "lucide-react";
import { AuthCard } from "../components/layout/AuthCard";
import { GradientButton } from "../components/ui/GradientButton";

interface NewComparisonModalProps {
    isOpen: boolean;
    onClose: () => void;
}

export function NewComparisonModal({ isOpen, onClose }: NewComparisonModalProps) {
    const [isAnimating, setIsAnimating] = useState(false);
    const [shouldRender, setShouldRender] = useState(isOpen);

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

    if (!shouldRender) return null;

    return (
        <div className={`fixed inset-0 z-[100] flex items-center justify-center p-4 transition-all duration-300 ${isAnimating ? 'visible' : 'invisible'}`}>
            {/* Backdrop */}
            <div
                className={`absolute inset-0 bg-black/60 backdrop-blur-sm transition-opacity duration-300 ${isAnimating ? 'opacity-100' : 'opacity-0'}`}
                onClick={onClose}
            />

            {/* Modal Content */}
            <div className={`w-full max-w-xl transition-all duration-300 transform ${isAnimating ? 'opacity-100 scale-100' : 'opacity-0 scale-95'}`}>
                <AuthCard className="w-full p-0 overflow-hidden border-[#2b3346]/60">
                    {/* Header */}
                    <div className="flex items-center justify-between px-8 py-6 border-b border-[#2b3346]/40">
                        <h2 className="text-xl font-display font-bold text-white">
                            Agregar comparación
                        </h2>
                        <div className="flex items-center gap-4">
                            <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">
                                65% completado
                            </span>
                            <button
                                onClick={onClose}
                                className="p-1 text-slate-500 hover:text-white transition-colors"
                            >
                                <X size={20} />
                            </button>
                        </div>
                    </div>

                    {/* Body */}
                    <div className="p-10 space-y-6">
                        {/* Upload Zone */}
                        <div className="relative group">
                            {/* Decorative stacked cards effect (subtle) */}
                            <div className="absolute -inset-2 bg-[#2b3346]/20 rounded-3xl blur-xl group-hover:bg-graphito-blue/5 transition-colors"></div>

                            <div className="relative border-2 border-dashed border-[#2b3346] rounded-3xl p-12 flex flex-col items-center justify-center gap-6 bg-[#121827]/30 hover:bg-[#121827]/50 transition-all cursor-pointer">
                                <div className="w-16 h-16 rounded-full bg-[#2b3346]/40 flex items-center justify-center text-slate-400">
                                    <Upload size={32} />
                                </div>

                                <div className="text-center">
                                    <p className="text-lg font-bold text-slate-200">
                                        Arrastra aquí el archivo
                                    </p>
                                    <p className="text-xs text-slate-500 mt-2 font-medium">
                                        Soporta .zip, .js, .py, .java hasta 20MB
                                    </p>
                                </div>

                                <button className="bg-[#2b3346]/60 hover:bg-[#2b3346] text-white text-sm font-bold py-2.5 px-6 rounded-xl border border-[#334155] transition-colors">
                                    Seleccionar archivo
                                </button>
                            </div>
                        </div>

                        {/* Validated File Item */}
                        <div className="flex items-center justify-between p-5 bg-[#121827]/40 border border-[#2b3346] rounded-2xl group hover:border-[#334155] transition-colors">
                            <div className="flex items-center gap-4">
                                <div className="w-10 h-10 rounded-xl bg-emerald-500/10 flex items-center justify-center text-emerald-500">
                                    <CheckCircle2 size={24} />
                                </div>
                                <div>
                                    <p className="text-sm font-bold text-white">
                                        algoritmo_validacion_v2.py
                                    </p>
                                    <p className="text-[11px] text-slate-500 font-medium mt-0.5">
                                        428 KB • Archivo validado correctamente
                                    </p>
                                </div>
                            </div>
                            <button className="text-xs font-bold text-slate-400 hover:text-white transition-colors">
                                Cambiar archivo
                            </button>
                        </div>
                    </div>

                    {/* Footer */}
                    <div className="flex items-center justify-between px-10 py-8 border-t border-[#2b3346]/40 bg-black/5">
                        <button
                            onClick={onClose}
                            className="text-sm font-bold text-slate-400 hover:text-white transition-colors"
                        >
                            Cancelar
                        </button>
                        <GradientButton className="!py-4 !px-12 !rounded-2xl">
                            <span className="text-base">Iniciar Análisis</span>
                        </GradientButton>
                    </div>
                </AuthCard>
            </div>
        </div>
    );
}
