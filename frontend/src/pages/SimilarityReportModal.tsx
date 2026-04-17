import { useState, useEffect } from "react";
import { ArrowLeft, CheckCircle2, Download, PlayCircle, Settings, Sparkles } from "lucide-react";
import { AuthCard } from "../components/layout/AuthCard";

// Helper hook for the typewriter effect (optimized for performance)
function useTypewriter(text: string, speed: number = 15) {
    const [displayedText, setDisplayedText] = useState("");

    useEffect(() => {
        setDisplayedText(""); // Reset when text changes
        if (!text) return;
        
        let i = 0;
        const interval = setInterval(() => {
            if (i < text.length) {
                setDisplayedText(text.slice(0, i + 1));
                i++;
            } else {
                clearInterval(interval);
            }
        }, speed);

        return () => clearInterval(interval);
    }, [text, speed]);

    return displayedText;
}

interface ComparisonData {
    id: string;
    title: string;          // Used as project name/author here
    subtitle: string;
    similarity: number;
}

interface SimilarityReportModalProps {
    isOpen: boolean;
    onClose: () => void;
    comparison: ComparisonData | null;
}

export function SimilarityReportModal({ isOpen, onClose, comparison }: SimilarityReportModalProps) {
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

    // Typewriter effect description
    const fullInterpretationText = `Basado en el análisis profundo de Graphito, los resultados sugieren una probabilidad muy alta de que el código haya sido adaptado de la misma fuente original o que exista una colaboración no declarada. Aunque los nombres de algunas funciones fueron modificados, la estructura lógica central se mantiene intacta.

Se recomienda revisar especialmente los módulos de conexión a base de datos, donde los patrones de optimización son virtualmente gemelos, algo poco probable en implementaciones independientes.`;

    const typewriterText = useTypewriter(isOpen ? fullInterpretationText : "", 3);

    if (!shouldRender || !comparison) return null;

    // SVG Circle Graphic calculations
    const radius = 90;
    const circumference = 2 * Math.PI * radius;
    // Dash offset calculations: percentage is comparison.similarity
    // Start offset at full circumference, then animate to actual similarity
    const strokeDashoffset = isAnimating ? circumference - (comparison.similarity / 100) * circumference : circumference;

    return (
        <div className={`fixed inset-0 z-[100] flex items-center justify-center p-4 transition-all duration-300 ${isAnimating ? 'visible' : 'invisible'}`}>
            {/* Backdrop */}
            <div
                className={`absolute inset-0 bg-black/80 backdrop-blur-md transition-opacity duration-300 ${isAnimating ? 'opacity-100' : 'opacity-0'}`}
                onClick={onClose}
            />

            {/* Modal Content */}
            <div className={`w-full max-w-5xl transition-all duration-300 transform ${isAnimating ? 'opacity-100 scale-100' : 'opacity-0 translate-y-8 scale-95'}`}>
                <AuthCard className="w-full p-0 overflow-hidden border-[#2b3346]/60 backdrop-blur-2xl bg-[#0f1522]/90">

                    <div className="flex flex-col h-full max-h-[90vh]">
                        {/* Top Navigation Bar */}
                        <div className="flex items-center justify-between px-8 py-4 border-b border-[#2b3346]/40 bg-black/20">
                            <button
                                onClick={onClose}
                                className="flex items-center gap-2 text-sm font-medium text-slate-400 hover:text-white transition-colors"
                            >
                                <ArrowLeft size={16} />
                                Volver a la biblioteca
                            </button>
                        </div>

                        {/* Header */}
                        <div className="px-10 pt-8 pb-6 flex items-start justify-between">
                            <div>
                                <h2 className="text-3xl font-display font-black text-white tracking-tight">
                                    Reporte de similitud
                                </h2>
                                <div className="flex items-center gap-4 mt-2 text-sm text-slate-400 font-medium">
                                    <span>Proyecto: {comparison.title}</span>
                                    <span className="w-1 h-1 rounded-full bg-slate-600"></span>
                                    <span>14 de Abril, 2026</span>
                                </div>
                            </div>
                            <div className="flex items-center gap-2 bg-[#1a2031] border border-[#2b3346] px-4 py-2 rounded-full">
                                <div className="w-2 h-2 rounded-full bg-graphito-blue"></div>
                                <span className="text-xs font-bold text-slate-300">Análisis completado</span>
                            </div>
                        </div>

                        {/* Body */}
                        <div className="flex-1 overflow-y-auto px-10 pb-8 scrollbar-thin scrollbar-thumb-[#2b3346] scrollbar-track-transparent">
                            <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">

                                {/* Left Column: Big Chart */}
                                <div className="lg:col-span-4 flex flex-col items-center justify-center p-8 bg-[#121827]/40 border border-[#2b3346]/60 rounded-3xl h-full">

                                    {/* Circular Graph */}
                                    <div className="relative w-64 h-64 flex items-center justify-center">
                                        {/* Background Circle */}
                                        <svg className="w-full h-full transform -rotate-90">
                                            <circle
                                                cx="128"
                                                cy="128"
                                                r={radius}
                                                className="stroke-[#2b3346] fill-none"
                                                strokeWidth="16"
                                            />

                                            {/* Gradient defs */}
                                            <defs>
                                                <linearGradient id="scoreGradient" x1="0%" y1="0%" x2="100%" y2="100%">
                                                    <stop offset="0%" stopColor="#3b82f6" />
                                                    <stop offset="100%" stopColor="#a78bfa" />
                                                </linearGradient>
                                            </defs>

                                            {/* Foreground Circle - Animated */}
                                            <circle
                                                cx="128"
                                                cy="128"
                                                r={radius}
                                                className="fill-none transition-all duration-1000 ease-out"
                                                stroke="url(#scoreGradient)"
                                                strokeWidth="16"
                                                strokeLinecap="round"
                                                strokeDasharray={circumference}
                                                strokeDashoffset={strokeDashoffset}
                                            />
                                        </svg>

                                        {/* Score Text */}
                                        <div className="absolute flex flex-col items-center justify-center text-center">
                                            <span className="text-5xl font-black text-white tracking-tight">
                                                {comparison.similarity}%
                                            </span>
                                            <span className={`text-xs font-bold uppercase tracking-widest mt-1 ${comparison.similarity > 70 ? 'text-orange-400' :
                                                comparison.similarity > 30 ? 'text-yellow-400' : 'text-emerald-400'
                                                }`}>
                                                {comparison.similarity > 70 ? 'ALTO' : comparison.similarity > 30 ? 'MEDIO' : 'BAJO'}
                                            </span>
                                        </div>
                                    </div>

                                    <h3 className="text-lg font-bold text-white mt-8 mb-2">Similitud total</h3>
                                    <p className="text-sm text-center text-slate-400">
                                        Se detectó una coincidencia {comparison.similarity > 50 ? 'significativa' : 'menor'} en la estructura lógica central del código analizado.
                                    </p>
                                </div>

                                {/* Right Column: Breakdown & Interpretation */}
                                <div className="lg:col-span-8 flex flex-col gap-6">

                                    {/* Top row: Two metric cards */}
                                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6 p-1">

                                        {/* Stylometry Card */}
                                        <div className="bg-[#121827]/40 border border-[#2b3346]/60 rounded-3xl p-6 hover:bg-[#121827]/60 transition-colors">
                                            <div className="flex items-center gap-3 mb-6">
                                                <div className="w-10 h-10 rounded-xl bg-graphito-violet/10 flex items-center justify-center text-graphito-violet">
                                                    <Settings size={20} />
                                                </div>
                                                <h4 className="font-bold text-white">Análisis estilométrico</h4>
                                            </div>

                                            <div className="space-y-4">
                                                <div>
                                                    <div className="flex justify-between text-xs font-bold text-slate-400 mb-2">
                                                        <span>Coincidencia de sintaxis</span>
                                                        <span className="text-white">85%</span>
                                                    </div>
                                                    <div className="h-1.5 w-full bg-[#2b3346]/60 rounded-full overflow-hidden">
                                                        <div
                                                            className="h-full bg-graphito-violet rounded-full transition-all duration-1000 ease-out"
                                                            style={{ width: isAnimating ? '85%' : '0%' }}
                                                        ></div>
                                                    </div>
                                                </div>

                                                <ul className="space-y-3 mt-6">
                                                    <li className="flex items-start gap-2.5 text-xs text-slate-300">
                                                        <CheckCircle2 size={16} className="text-slate-500 shrink-0" />
                                                        <span>Nomenclatura de variables idéntica en funciones principales.</span>
                                                    </li>
                                                    <li className="flex items-start gap-2.5 text-xs text-slate-300">
                                                        <CheckCircle2 size={16} className="text-slate-500 shrink-0" />
                                                        <span>Estructura de comentarios y espaciado consistente.</span>
                                                    </li>
                                                </ul>
                                            </div>
                                        </div>

                                        {/* Semantic Card */}
                                        <div className="bg-[#121827]/40 border border-[#2b3346]/60 rounded-3xl p-6 hover:bg-[#121827]/60 transition-colors">
                                            <div className="flex items-center gap-3 mb-6">
                                                <div className="w-10 h-10 rounded-xl bg-graphito-blue/10 flex items-center justify-center text-graphito-blue">
                                                    <PlayCircle size={20} />
                                                </div>
                                                <h4 className="font-bold text-white">Análisis semántico</h4>
                                            </div>

                                            <div className="space-y-4">
                                                <div>
                                                    <div className="flex justify-between text-xs font-bold text-slate-400 mb-2">
                                                        <span>Flujo algorítmico</span>
                                                        <span className="text-white">62%</span>
                                                    </div>
                                                    <div className="h-1.5 w-full bg-[#2b3346]/60 rounded-full overflow-hidden">
                                                        <div
                                                            className="h-full bg-graphito-blue rounded-full transition-all duration-1000 ease-out"
                                                            style={{ width: isAnimating ? '62%' : '0%' }}
                                                        ></div>
                                                    </div>
                                                </div>

                                                <ul className="space-y-3 mt-6">
                                                    <li className="flex items-start gap-2.5 text-xs text-slate-300">
                                                        <CheckCircle2 size={16} className="text-slate-500 shrink-0" />
                                                        <span>Uso de estructuras de control (loops) en secuencia idéntica.</span>
                                                    </li>
                                                    <li className="flex items-start gap-2.5 text-xs text-slate-300">
                                                        <CheckCircle2 size={16} className="text-slate-500 shrink-0" />
                                                        <span>Mismo enfoque para el manejo de excepciones de red.</span>
                                                    </li>
                                                </ul>
                                            </div>
                                        </div>

                                    </div>

                                    {/* Bottom row: AI Interpretation (Typewriter) */}
                                    <div className="bg-[#121827]/60 border border-[#2b3346]/60 rounded-3xl p-6 flex-1 hover:border-[#334155] transition-colors relative overflow-hidden group">
                                        <div className="absolute top-0 right-0 w-64 h-64 bg-graphito-blue/5 rounded-full blur-3xl -translate-y-1/2 translate-x-1/2 opacity-0 group-hover:opacity-100 transition-opacity duration-700"></div>

                                        <div className="flex items-center gap-4 mb-4">
                                            <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-graphito-blue to-graphito-violet flex items-center justify-center text-white shadow-lg shadow-graphito-blue/20">
                                                <Sparkles size={24} />
                                            </div>
                                            <h4 className="text-lg font-bold text-white">Interpretación del análisis</h4>
                                        </div>

                                        <div className="text-sm font-medium text-slate-300 leading-relaxed max-w-3xl whitespace-pre-line break-words format-text min-h-[120px]">
                                            {typewriterText}
                                            {/* Blinking cursor */}
                                            <span className="inline-block w-1.5 h-4 bg-graphito-blue ml-1 animate-pulse align-middle"></span>
                                        </div>
                                    </div>

                                </div>
                            </div>
                        </div>

                        {/* Footer */}
                        <div className="flex items-center justify-between px-10 py-6 border-t border-[#2b3346]/40 bg-black/40 mt-auto shrink-0">
                            <div className="text-xs font-medium text-slate-500">
                                Documento: ID_8829-X
                            </div>
                            <div className="flex items-center gap-4">
                                <button className="flex items-center gap-2 px-6 py-2.5 rounded-xl border border-[#2b3346] text-sm font-bold text-white hover:bg-white/5 transition-colors">
                                    <Download size={16} />
                                    <span>Descargar reporte PDF</span>
                                </button>
                                <button
                                    onClick={onClose}
                                    className="px-6 py-2.5 rounded-xl bg-gradient-to-r from-graphito-blue to-graphito-violet text-sm font-bold text-white hover:opacity-90 transition-opacity"
                                >
                                    Volver a la biblioteca
                                </button>
                            </div>
                        </div>

                    </div>
                </AuthCard>
            </div>
        </div>
    );
}
