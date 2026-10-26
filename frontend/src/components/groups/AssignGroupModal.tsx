import { useEffect, useRef, useState } from "react";
import { Users, Loader2 } from "lucide-react";
import { Modal } from "../ui/Modal";
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

    // Keep the last problem title and id in ref so during exit animation the modal content does not jump to empty
    const lastProblemTitleRef = useRef(problemTitle);
    if (problemTitle) {
        lastProblemTitleRef.current = problemTitle;
    }
    const displayTitle = problemTitle || lastProblemTitleRef.current;

    const lastProblemIdRef = useRef(problemId);
    if (problemId !== null) {
        lastProblemIdRef.current = problemId;
    }
    const activeProblemId = problemId ?? lastProblemIdRef.current;

    useEffect(() => {
        if (isOpen) {
            setGroupId(available[0]?.id ?? null);
            setError(null);
            setDone(null);
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [isOpen]);

    const handleAssign = async () => {
        if (groupId === null || activeProblemId === null) {
            setError("Selecciona un grupo para continuar.");
            return;
        }
        setIsLoading(true);
        setError(null);
        try {
            await api.groups.assignProblem(groupId, activeProblemId);
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
        <Modal
            isOpen={isOpen}
            onClose={onClose}
            title="Asignar a un grupo"
            description={displayTitle}
            maxWidth="md"
            fixedHeight="h-[380px] max-h-[85vh]"
            bodyClassName="space-y-4"
            footer={
                <div className="flex items-center justify-end gap-6">
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
            }
        >
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
        </Modal>
    );
}
