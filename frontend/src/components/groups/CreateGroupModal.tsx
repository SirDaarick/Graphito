import { useState, useRef, useEffect } from "react";
import { X, Users, BookOpen, Calendar, AlignLeft, Loader2 } from "lucide-react";
import { useGSAP } from "@gsap/react";
import gsap from "gsap";
import { AuthCard } from "../layout/AuthCard";
import { GradientButton } from "../ui/GradientButton";
import { api, Grupo } from "../../lib/api";

interface CreateGroupModalProps {
    isOpen: boolean;
    onClose: () => void;
    onGroupCreated: (newGroup: Grupo) => void;
}

export function CreateGroupModal({ isOpen, onClose, onGroupCreated }: CreateGroupModalProps) {
    const [nombre, setNombre] = useState("");
    const [codigoGrupo, setCodigoGrupo] = useState("");
    const [periodo, setPeriodo] = useState("2026-B");
    const [descripcion, setDescripcion] = useState("");
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const [shouldRender, setShouldRender] = useState(isOpen);
    const backdropRef = useRef<HTMLDivElement>(null);
    const contentRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        if (isOpen) {
            setShouldRender(true);
            setError(null);
        }
    }, [isOpen]);

    useGSAP(() => {
        if (!shouldRender) return;

        if (isOpen) {
            gsap.fromTo(
                backdropRef.current,
                { opacity: 0 },
                { opacity: 1, duration: 0.25, ease: "power2.out" }
            );
            gsap.fromTo(
                contentRef.current,
                { opacity: 0, scale: 0.95, y: 15 },
                { opacity: 1, scale: 1, y: 0, duration: 0.35, ease: "back.out(1.2)" }
            );
        } else {
            gsap.to(backdropRef.current, { opacity: 0, duration: 0.2, ease: "power2.in" });
            gsap.to(contentRef.current, {
                opacity: 0,
                scale: 0.95,
                y: 10,
                duration: 0.2,
                ease: "power2.in",
                onComplete: () => setShouldRender(false),
            });
        }
    }, [isOpen, shouldRender]);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!nombre.trim() || !codigoGrupo.trim() || !periodo.trim()) {
            setError("Nombre, código de grupo y periodo son campos obligatorios.");
            return;
        }

        setIsLoading(true);
        setError(null);
        try {
            const created = await api.groups.create({
                nombre: nombre.trim(),
                codigo_grupo: codigoGrupo.trim().toUpperCase(),
                periodo: periodo.trim(),
                descripcion: descripcion.trim() || undefined,
            });
            onGroupCreated(created);
            // Reset
            setNombre("");
            setCodigoGrupo("");
            setDescripcion("");
            onClose();
        } catch (err: any) {
            setError(err.message || "Error al crear el grupo académico.");
        } finally {
            setIsLoading(false);
        }
    };

    if (!shouldRender) return null;

    return (
        <div className="fixed inset-0 z-[100] flex items-center justify-center p-4">
            <div
                ref={backdropRef}
                onClick={onClose}
                className="absolute inset-0 bg-black/60 backdrop-blur-sm"
            />

            <div ref={contentRef} className="relative w-full max-w-lg z-10 max-h-[90vh] flex flex-col">
                <AuthCard className="w-full p-0 overflow-hidden flex flex-col max-h-[90vh] bg-white dark:bg-graphito-card border border-slate-200 dark:border-[#2b3346]/60 shadow-2xl rounded-2xl transition-colors">
                    <div className="flex items-center justify-between px-8 py-6 border-b border-slate-200 dark:border-[#2b3346]/40 shrink-0">
                        <div className="flex items-center gap-3">
                            <div className="w-10 h-10 rounded-xl bg-graphito-blue/10 border border-graphito-blue/20 flex items-center justify-center text-graphito-blue">
                                <Users size={20} />
                            </div>
                            <div>
                                <h2 className="text-xl font-display font-bold text-slate-900 dark:text-white">
                                    Nuevo curso o grupo
                                </h2>
                                <p className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">
                                    Organiza tus entregas por semestre y salón escolar.
                                </p>
                            </div>
                        </div>
                        <button
                            type="button"
                            onClick={onClose}
                            aria-label="Cerrar"
                            className="p-1 text-slate-400 hover:text-slate-700 dark:text-slate-500 dark:hover:text-white active:scale-95 focus:outline-none focus-visible:ring-2 focus-visible:ring-slate-400 rounded-md transition-all"
                        >
                            <X size={20} />
                        </button>
                    </div>

                    <form onSubmit={handleSubmit} className="flex flex-col flex-1 min-h-0">
                    <div className="p-8 space-y-6 overflow-y-auto flex-1">
                        {error && (
                            <div className="p-3 bg-red-500/10 border border-red-500/30 rounded-xl text-red-600 dark:text-red-300 text-xs font-medium">
                                {error}
                            </div>
                        )}

                        <div className="grid grid-cols-3 gap-3">
                            <div className="col-span-2 space-y-1.5">
                                <label className="text-[10px] uppercase font-black tracking-widest text-slate-500 dark:text-slate-400 flex items-center gap-1.5">
                                    <BookOpen size={13} className="text-graphito-blue" />
                                    Materia o Asignatura
                                </label>
                                <input
                                    type="text"
                                    value={nombre}
                                    onChange={(e) => setNombre(e.target.value)}
                                    placeholder="Ej. Estructuras de Datos"
                                    className="w-full bg-slate-50 dark:bg-[#121827]/40 border border-slate-200 dark:border-[#2b3346] text-slate-900 dark:text-white placeholder:text-slate-400 dark:placeholder:text-slate-600 rounded-xl py-3 px-4 text-sm focus:outline-none focus:border-graphito-blue transition-colors"
                                    disabled={isLoading}
                                />
                            </div>

                            <div className="space-y-1.5">
                                <label className="text-[10px] uppercase font-black tracking-widest text-slate-500 dark:text-slate-400">
                                    Código Grupo
                                </label>
                                <input
                                    type="text"
                                    value={codigoGrupo}
                                    onChange={(e) => setCodigoGrupo(e.target.value)}
                                    placeholder="Ej. 2CM1"
                                    className="w-full bg-slate-50 dark:bg-[#121827]/40 border border-slate-200 dark:border-[#2b3346] text-slate-900 dark:text-white placeholder:text-slate-400 dark:placeholder:text-slate-600 rounded-xl py-3 px-4 text-sm font-mono uppercase focus:outline-none focus:border-graphito-blue transition-colors"
                                    disabled={isLoading}
                                />
                            </div>
                        </div>

                        <div className="space-y-1.5">
                            <label className="text-[10px] uppercase font-black tracking-widest text-slate-500 dark:text-slate-400 flex items-center gap-1.5">
                                <Calendar size={13} className="text-graphito-violet" />
                                Periodo Escolar
                            </label>
                            <input
                                type="text"
                                value={periodo}
                                onChange={(e) => setPeriodo(e.target.value)}
                                placeholder="Ej. 2026-B o 2026-1"
                                className="w-full bg-slate-50 dark:bg-[#121827]/40 border border-slate-200 dark:border-[#2b3346] text-slate-900 dark:text-white placeholder:text-slate-400 dark:placeholder:text-slate-600 rounded-xl py-3 px-4 text-sm font-mono focus:outline-none focus:border-graphito-blue transition-colors"
                                disabled={isLoading}
                            />
                        </div>

                        <div className="space-y-1.5">
                            <label className="text-[10px] uppercase font-black tracking-widest text-slate-500 dark:text-slate-400 flex items-center gap-1.5">
                                <AlignLeft size={13} className="text-slate-400" />
                                Descripción o Notas (Opcional)
                            </label>
                            <textarea
                                value={descripcion}
                                onChange={(e) => setDescripcion(e.target.value)}
                                placeholder="Horario matutino, criterios de entrega, laboratorio asignado..."
                                rows={3}
                                className="w-full bg-slate-50 dark:bg-[#121827]/40 border border-slate-200 dark:border-[#2b3346] text-slate-900 dark:text-white placeholder:text-slate-400 dark:placeholder:text-slate-600 rounded-xl py-3 px-4 text-sm focus:outline-none focus:border-graphito-blue transition-colors resize-none"
                                disabled={isLoading}
                            />
                        </div>

                    </div>

                    <div className="flex items-center justify-end gap-6 px-8 py-6 border-t border-slate-200 dark:border-[#2b3346]/40 bg-slate-50 dark:bg-black/10 shrink-0 transition-colors">
                        <button
                            type="button"
                            onClick={onClose}
                            disabled={isLoading}
                            className="text-sm font-bold text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white active:scale-95 focus:outline-none focus-visible:ring-2 focus-visible:ring-slate-400 rounded-lg px-4 py-2 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
                        >
                            Cancelar
                        </button>
                        <GradientButton type="submit" disabled={isLoading} className="!py-3 !px-8 disabled:opacity-50">
                            <div className="flex items-center gap-2">
                                {isLoading ? (
                                    <>
                                        <Loader2 size={16} className="animate-spin" />
                                        <span>Creando grupo...</span>
                                    </>
                                ) : (
                                    <span>Crear curso</span>
                                )}
                            </div>
                        </GradientButton>
                    </div>
                    </form>
                </AuthCard>
            </div>
        </div>
    );
}
