import { useEffect, useState } from "react";
import { X, Users, Loader2 } from "lucide-react";
import { AuthCard } from "../layout/AuthCard";
import { GradientButton } from "../ui/GradientButton";
import { api, Grupo } from "../../lib/api";

interface AssignGroupModalProps {
    isOpen: boolean;
    problemId: number | null;
    problemTitle: string;
    groups: Grupo[];
    onClose: () => void;
    onAssigned: () => void;
}

/** Assigns one library problem to one of the teacher's (non-archived) groups. */
export function AssignGroupModal({
    isOpen,
    problemId,
    problemTitle,
    groups,
    onClose,
    onAssigned,
}: AssignGroupModalProps) {
    const available = groups.filter((g) => !g.archivado);
    const [groupId, setGroupId] = useState<number | null>(null);
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [done, setDone] = useState<string | null>(null);

    useEffect(() => {
        if (isOpen) {
            setGroupId(available[0]?.id ?? null);
            setError(null);
            setDone(null);
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [isOpen]);

    if (!isOpen || problemId === null) return null;

    const handleAssign = async () => {
        if (groupId === null) {
            setError("Selecciona un grupo para continuar.");
            return;
        }
        setIsLoading(true);
        setError(null);
        try {
            await api.groups.assignProblem(groupId, problemId);
            const group = available.find((g) => g.id === groupId);
            setDone(group ? `Asignado a [${group.codigo_grupo}] ${group.nombre}.` : "Problema asignado.");
            onAssigned();
        } catch (err: unknown) {
            setError(err instanceof Error ? err.message : "Error al asignar el problema al grupo.");
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <div className="fixed inset-0 z-[100] flex items-center justify-center p-4">
            <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onClose} />

            <div className="relative w-full max-w-lg">
                <AuthCard className="w-full p-0 overflow-hidden bg-white dark:bg-graphito-card border border-slate-200 dark:border-[#2b3346]/60 shadow-2xl rounded-2xl transition-colors">
                    <div className="flex items-start justify-between gap-4 px-8 py-6 border-b border-slate-200 dark:border-[#2b3346]/40">
                        <div className="min-w-0">
                            <h2 className="text-xl font-display font-bold text-slate-900 dark:text-white">
                                Asignar a un grupo
                            </h2>
                            <p className="mt-1 text-xs text-slate-500 dark:text-slate-400 truncate">{problemTitle}</p>
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

                    <div className="p-8 space-y-4">
                        {error && (
                            <div className="p-3 bg-red-500/10 border border-red-500/30 rounded-xl text-red-600 dark:text-red-300 text-xs font-medium">
                                {error}
                            </div>
                        )}
                        {done && (
                            <div className="p-3 bg-emerald-500/10 border border-emerald-500/30 rounded-xl text-emerald-700 dark:text-emerald-300 text-sm font-bold">
                                {done}
                            </div>
                        )}

                        {available.length === 0 ? (
                            <p className="text-sm text-slate-600 dark:text-slate-400">
                                No tienes grupos disponibles. Crea uno desde el filtro de cursos de la biblioteca.
                            </p>
                        ) : (
                            <div className="space-y-1.5">
                                <label
                                    htmlFor="assign-group-select"
                                    className="text-[10px] uppercase font-black tracking-widest text-slate-500 dark:text-slate-400 flex items-center gap-1.5"
                                >
                                    <Users size={13} className="text-graphito-blue" />
                                    Curso o grupo
                                </label>
                                <select
                                    id="assign-group-select"
                                    value={groupId ?? ""}
                                    onChange={(e) => setGroupId(e.target.value ? Number(e.target.value) : null)}
                                    disabled={isLoading || done !== null}
                                    className="w-full bg-slate-50 dark:bg-[#121827] border border-slate-200 dark:border-[#2b3346] text-slate-900 dark:text-white rounded-xl py-3 px-4 focus:outline-none focus:border-graphito-blue text-sm cursor-pointer transition-colors"
                                >
                                    {available.map((g) => (
                                        <option
                                            key={g.id}
                                            value={g.id}
                                            className="bg-white dark:bg-slate-900 text-slate-900 dark:text-white"
                                        >
                                            [{g.codigo_grupo}] {g.nombre} · {g.periodo}
                                        </option>
                                    ))}
                                </select>
                            </div>
                        )}
                    </div>

                    <div className="flex items-center justify-end gap-6 px-8 py-6 border-t border-slate-200 dark:border-[#2b3346]/40 bg-slate-50 dark:bg-black/10 transition-colors">
                        <button
                            type="button"
                            onClick={onClose}
                            className="text-sm font-bold text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white active:scale-95 focus:outline-none focus-visible:ring-2 focus-visible:ring-slate-400 rounded-lg px-4 py-2 transition-all"
                        >
                            {done ? "Cerrar" : "Cancelar"}
                        </button>
                        {!done && (
                            <GradientButton
                                onClick={handleAssign}
                                disabled={isLoading || available.length === 0}
                                className="!py-3 !px-6 !rounded-2xl"
                            >
                                <div className="flex items-center gap-2">
                                    {isLoading ? (
                                        <>
                                            <Loader2 size={16} className="animate-spin" />
                                            <span>Asignando...</span>
                                        </>
                                    ) : (
                                        <span>Asignar</span>
                                    )}
                                </div>
                            </GradientButton>
                        )}
                    </div>
                </AuthCard>
            </div>
        </div>
    );
}
