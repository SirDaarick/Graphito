import { useEffect, useRef, useState } from "react";
import { Users, Loader2, Plus } from "lucide-react";
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

    const [creatingNew, setCreatingNew] = useState(false);
    const [newNombre, setNewNombre] = useState("");
    const [newCodigo, setNewCodigo] = useState("");
    const [newPeriodo, setNewPeriodo] = useState("2026-B");

    useEffect(() => {
        if (isOpen) {
            setGroupId(available[0]?.id ?? null);
            setError(null);
            setDone(null);
            setCreatingNew(false);
            setNewNombre("");
            setNewCodigo("");
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [isOpen]);

    // With no groups yet, creating one is the only way forward.
    const showNewForm = creatingNew || available.length === 0;

    const handleAssign = async () => {
        if (activeProblemId === null) return;
        if (!showNewForm && groupId === null) {
            setError("Selecciona un grupo para continuar.");
            return;
        }
        if (showNewForm && (!newNombre.trim() || !newCodigo.trim() || !newPeriodo.trim())) {
            setError("Nombre, código de grupo y periodo son obligatorios.");
            return;
        }
        setIsLoading(true);
        setError(null);
        try {
            let group: Grupo | undefined;
            if (showNewForm) {
                group = await api.groups.create({
                    nombre: newNombre.trim(),
                    codigo_grupo: newCodigo.trim().toUpperCase(),
                    periodo: newPeriodo.trim(),
                });
                await api.groups.assignProblem(group.id, activeProblemId);
            } else {
                await api.groups.assignProblem(groupId as number, activeProblemId);
                group = available.find((g) => g.id === groupId);
            }
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
            fixedHeight={showNewForm ? "h-[500px] max-h-[85vh]" : "h-[400px] max-h-[85vh]"}
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
                            disabled={isLoading}
                            className="!py-3 !px-6 !rounded-2xl"
                        >
                            <div className="flex items-center gap-2">
                                {isLoading ? (
                                    <>
                                        <Loader2 size={16} className="animate-spin" />
                                        <span>Asignando...</span>
                                    </>
                                ) : (
                                    <span>{showNewForm ? "Crear y asignar" : "Asignar"}</span>
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

            {showNewForm ? (
                <div className="space-y-4">
                    {available.length === 0 ? (
                        <p className="text-sm text-slate-600 dark:text-slate-400">
                            Aún no tienes grupos. Crea uno y se asignará este problema.
                        </p>
                    ) : (
                        <p className="text-sm font-bold text-slate-800 dark:text-slate-200 flex items-center gap-1.5">
                            <Plus size={14} className="text-graphito-blue" aria-hidden="true" />
                            Nuevo grupo
                        </p>
                    )}
                    <div className="grid grid-cols-3 gap-3">
                        <div className="col-span-2 space-y-1.5">
                            <label htmlFor="assign-new-nombre" className="text-[10px] uppercase font-black tracking-widest text-slate-500 dark:text-slate-400">
                                Materia
                            </label>
                            <input
                                id="assign-new-nombre"
                                type="text"
                                value={newNombre}
                                onChange={(e) => setNewNombre(e.target.value)}
                                disabled={isLoading || done !== null}
                                placeholder="Ej. Estructuras de Datos"
                                className="w-full bg-slate-50 dark:bg-[#121827]/40 border border-slate-200 dark:border-[#2b3346] text-slate-900 dark:text-white placeholder:text-slate-400 dark:placeholder:text-slate-600 rounded-xl py-3 px-4 text-sm focus:outline-none focus:border-graphito-blue transition-colors"
                            />
                        </div>
                        <div className="space-y-1.5">
                            <label htmlFor="assign-new-codigo" className="text-[10px] uppercase font-black tracking-widest text-slate-500 dark:text-slate-400">
                                Código
                            </label>
                            <input
                                id="assign-new-codigo"
                                type="text"
                                value={newCodigo}
                                onChange={(e) => setNewCodigo(e.target.value)}
                                disabled={isLoading || done !== null}
                                placeholder="2CM1"
                                className="w-full bg-slate-50 dark:bg-[#121827]/40 border border-slate-200 dark:border-[#2b3346] text-slate-900 dark:text-white placeholder:text-slate-400 dark:placeholder:text-slate-600 rounded-xl py-3 px-4 text-sm font-mono uppercase focus:outline-none focus:border-graphito-blue transition-colors"
                            />
                        </div>
                    </div>
                    <div className="space-y-1.5">
                        <label htmlFor="assign-new-periodo" className="text-[10px] uppercase font-black tracking-widest text-slate-500 dark:text-slate-400">
                            Periodo escolar
                        </label>
                        <input
                            id="assign-new-periodo"
                            type="text"
                            value={newPeriodo}
                            onChange={(e) => setNewPeriodo(e.target.value)}
                            disabled={isLoading || done !== null}
                            placeholder="Ej. 2026-B"
                            className="w-full bg-slate-50 dark:bg-[#121827]/40 border border-slate-200 dark:border-[#2b3346] text-slate-900 dark:text-white placeholder:text-slate-400 dark:placeholder:text-slate-600 rounded-xl py-3 px-4 text-sm font-mono focus:outline-none focus:border-graphito-blue transition-colors"
                        />
                    </div>
                    {available.length > 0 && !done && (
                        <button
                            type="button"
                            onClick={() => {
                                setCreatingNew(false);
                                setError(null);
                            }}
                            className="text-xs font-bold text-graphito-blue hover:underline"
                        >
                            Elegir un grupo existente
                        </button>
                    )}
                </div>
            ) : (
                <div className="space-y-3">
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
                    {!done && (
                        <button
                            type="button"
                            onClick={() => {
                                setCreatingNew(true);
                                setError(null);
                            }}
                            disabled={isLoading}
                            className="inline-flex items-center gap-1.5 text-xs font-bold text-graphito-blue hover:underline disabled:opacity-50"
                        >
                            <Plus size={13} aria-hidden="true" />
                            Crear grupo nuevo
                        </button>
                    )}
                </div>
            )}
        </Modal>
    );
}
