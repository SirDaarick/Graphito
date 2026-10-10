import { useState, useRef, useEffect } from "react";
import { X, Users, BookOpen, Calendar, AlignLeft, Loader2, CheckCircle2 } from "lucide-react";
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
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
            <div
                ref={backdropRef}
                onClick={onClose}
                className="absolute inset-0 bg-background/80 backdrop-blur-md"
            />

            <div
                ref={contentRef}
                className="relative w-full max-w-lg z-10"
            >
                <AuthCard>
                    <div className="flex items-center justify-between pb-4 border-b border-line-subtle">
                        <div className="flex items-center gap-3">
                            <div className="w-10 h-10 rounded-xl bg-cyan-500/10 border border-cyan-500/20 flex items-center justify-center text-cyan-400">
                                <Users size={20} />
                            </div>
                            <div>
                                <h2 className="text-lg font-bold text-content-primary">
                                    Nuevo Curso / Grupo Académico
                                </h2>
                                <p className="text-xs text-content-secondary">
                                    Organiza tus entregas por semestre y salón escolar.
                                </p>
                            </div>
                        </div>
                        <button
                            type="button"
                            onClick={onClose}
                            className="p-1.5 rounded-lg text-content-muted hover:text-content-primary hover:bg-surface-elevated transition-colors"
                        >
                            <X size={18} />
                        </button>
                    </div>

                    <form onSubmit={handleSubmit} className="space-y-4 pt-4">
                        {error && (
                            <div className="p-3 rounded-xl bg-rose-500/10 border border-rose-500/20 text-xs text-rose-400">
                                {error}
                            </div>
                        )}

                        <div className="grid grid-cols-3 gap-3">
                            <div className="col-span-2 space-y-1.5">
                                <label className="text-xs font-semibold text-content-secondary flex items-center gap-1.5">
                                    <BookOpen size={13} className="text-cyan-400" />
                                    Materia o Asignatura
                                </label>
                                <input
                                    type="text"
                                    value={nombre}
                                    onChange={(e) => setNombre(e.target.value)}
                                    placeholder="Ej. Estructuras de Datos"
                                    className="w-full px-3.5 py-2.5 rounded-xl bg-surface border border-line-subtle text-content-primary placeholder-content-muted text-xs focus:outline-none focus:border-cyan-500 transition-colors"
                                    disabled={isLoading}
                                />
                            </div>

                            <div className="space-y-1.5">
                                <label className="text-xs font-semibold text-content-secondary">
                                    Código Grupo
                                </label>
                                <input
                                    type="text"
                                    value={codigoGrupo}
                                    onChange={(e) => setCodigoGrupo(e.target.value)}
                                    placeholder="Ej. 2CM1"
                                    className="w-full px-3.5 py-2.5 rounded-xl bg-surface border border-line-subtle text-content-primary placeholder-content-muted text-xs font-mono uppercase focus:outline-none focus:border-cyan-500 transition-colors"
                                    disabled={isLoading}
                                />
                            </div>
                        </div>

                        <div className="space-y-1.5">
                            <label className="text-xs font-semibold text-content-secondary flex items-center gap-1.5">
                                <Calendar size={13} className="text-purple-400" />
                                Periodo Escolar
                            </label>
                            <input
                                type="text"
                                value={periodo}
                                onChange={(e) => setPeriodo(e.target.value)}
                                placeholder="Ej. 2026-B o 2026-1"
                                className="w-full px-3.5 py-2.5 rounded-xl bg-surface border border-line-subtle text-content-primary placeholder-content-muted text-xs font-mono focus:outline-none focus:border-cyan-500 transition-colors"
                                disabled={isLoading}
                            />
                        </div>

                        <div className="space-y-1.5">
                            <label className="text-xs font-semibold text-content-secondary flex items-center gap-1.5">
                                <AlignLeft size={13} className="text-content-muted" />
                                Descripción o Notas (Opcional)
                            </label>
                            <textarea
                                value={descripcion}
                                onChange={(e) => setDescripcion(e.target.value)}
                                placeholder="Horario matutino, criterios de entrega, laboratorio asignado..."
                                rows={3}
                                className="w-full px-3.5 py-2.5 rounded-xl bg-surface border border-line-subtle text-content-primary placeholder-content-muted text-xs focus:outline-none focus:border-cyan-500 transition-colors resize-none"
                                disabled={isLoading}
                            />
                        </div>

                        <div className="flex items-center justify-end gap-3 pt-3 border-t border-line-subtle">
                            <button
                                type="button"
                                onClick={onClose}
                                disabled={isLoading}
                                className="px-4 py-2 rounded-xl text-xs font-semibold text-content-secondary hover:text-content-primary transition-colors"
                            >
                                Cancelar
                            </button>
                            <GradientButton
                                type="submit"
                                disabled={isLoading}
                                className="text-xs px-5 py-2"
                            >
                                {isLoading ? (
                                    <span className="flex items-center gap-2">
                                        <Loader2 size={14} className="animate-spin" />
                                        Creando grupo...
                                    </span>
                                ) : (
                                    "Crear Curso"
                                )}
                            </GradientButton>
                        </div>
                    </form>
                </AuthCard>
            </div>
        </div>
    );
}
