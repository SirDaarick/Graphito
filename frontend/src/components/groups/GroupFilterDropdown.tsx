import { useState, useRef, useEffect } from "react";
import { Users, ChevronDown, Check, Plus, FolderKanban, Archive, ArchiveRestore, Trash2 } from "lucide-react";
import { Grupo } from "../../lib/api";

interface GroupFilterDropdownProps {
    groups: Grupo[];
    selectedGroupId: number | null; // null = Todos los grupos
    onSelectGroup: (groupId: number | null) => void;
    onCreateGroupClick: () => void;
    /** Archive, unarchive and delete are offered only when the matching handler is given. */
    onArchiveGroup?: (group: Grupo) => void;
    onUnarchiveGroup?: (group: Grupo) => void;
    onDeleteGroup?: (group: Grupo) => void;
}

export function GroupFilterDropdown({
    groups,
    selectedGroupId,
    onSelectGroup,
    onCreateGroupClick,
    onArchiveGroup,
    onUnarchiveGroup,
    onDeleteGroup,
}: GroupFilterDropdownProps) {
    const [isOpen, setIsOpen] = useState(false);
    const dropdownRef = useRef<HTMLDivElement>(null);

    const selectedGroup = groups.find((g) => g.id === selectedGroupId);

    // Cerrar al hacer click fuera
    useEffect(() => {
        const handleClickOutside = (event: MouseEvent) => {
            if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
                setIsOpen(false);
            }
        };
        document.addEventListener("mousedown", handleClickOutside);
        return () => document.removeEventListener("mousedown", handleClickOutside);
    }, []);

    return (
        <div className="relative inline-block text-left" ref={dropdownRef}>
            <button
                type="button"
                onClick={() => setIsOpen(!isOpen)}
                className={`flex items-center gap-2.5 px-3.5 py-2 min-h-[44px] rounded-xl text-xs font-semibold transition-all duration-200 border backdrop-blur-md shadow-sm ${
                    selectedGroupId !== null
                        ? "bg-cyan-500/15 border-cyan-500/40 text-cyan-600 dark:text-cyan-300 shadow-sm shadow-cyan-500/10"
                        : "bg-white/25 dark:bg-graphito-card/15 border-slate-200/60 dark:border-white/10 text-slate-700 dark:text-slate-300 hover:text-slate-900 dark:hover:text-white hover:border-graphito-blue/40"
                }`}
                title="Filtrar biblioteca por curso o grupo académico"
            >
                <Users size={15} className={selectedGroupId !== null ? "text-cyan-400" : "text-content-muted"} />
                <span className="max-w-[160px] truncate">
                    {selectedGroup ? (
                        <>
                            <span className="font-mono font-bold mr-1 text-cyan-400">[{selectedGroup.codigo_grupo}]</span>
                            {selectedGroup.nombre}
                        </>
                    ) : (
                        "Todos los cursos"
                    )}
                </span>
                <ChevronDown size={14} className={`transition-transform duration-200 text-content-muted ${isOpen ? "rotate-180" : ""}`} />
            </button>

            {isOpen && (
                <div className="absolute right-0 z-50 mt-2 w-72 origin-top-right rounded-2xl bg-white/90 dark:bg-graphito-card/90 backdrop-blur-xl border border-slate-200/80 dark:border-white/[0.08] shadow-2xl p-2 space-y-1 animate-in fade-in zoom-in-95 duration-150">
                    <div className="px-2.5 py-1.5 text-[10px] font-bold uppercase tracking-wider text-content-muted flex items-center justify-between">
                        <span>Filtrar por Curso</span>
                        <FolderKanban size={12} />
                    </div>

                    {/* Opción global */}
                    <button
                        type="button"
                        onClick={() => {
                            onSelectGroup(null);
                            setIsOpen(false);
                        }}
                        className={`w-full flex items-center justify-between px-3 py-2 rounded-xl text-xs font-medium transition-colors ${
                            selectedGroupId === null
                                ? "bg-cyan-500/15 text-cyan-400 font-semibold"
                                : "text-content-secondary hover:text-content-primary hover:bg-surface-elevated"
                        }`}
                    >
                        <span>Vista Global (Todos los problemas)</span>
                        {selectedGroupId === null && <Check size={14} className="text-cyan-400" />}
                    </button>

                    <div className="h-px bg-line-subtle my-1" />

                    {/* Lista de grupos */}
                    <div className="max-h-48 overflow-y-auto space-y-0.5 custom-scrollbar">
                        {groups.length === 0 ? (
                            <div className="px-3 py-3 text-center text-xs text-content-muted">
                                No tienes grupos registrados.
                            </div>
                        ) : (
                            groups.map((group) => {
                                const isSelected = group.id === selectedGroupId;
                                const archived = Boolean(group.archivado);
                                return (
                                    <div
                                        key={group.id}
                                        className={`group/row flex items-center rounded-xl transition-colors ${
                                            isSelected
                                                ? "bg-cyan-500/15"
                                                : "hover:bg-surface-elevated"
                                        } ${archived ? "opacity-70" : ""}`}
                                    >
                                        <button
                                            type="button"
                                            onClick={() => {
                                                onSelectGroup(group.id);
                                                setIsOpen(false);
                                            }}
                                            className={`flex-1 min-w-0 flex items-center justify-between px-3 py-2 text-xs text-left ${
                                                isSelected
                                                    ? "text-cyan-400 font-semibold"
                                                    : "text-content-secondary hover:text-content-primary"
                                            }`}
                                        >
                                            <div className="truncate pr-2">
                                                <div className="flex items-center gap-1.5">
                                                    <span className="font-mono font-bold text-[11px] text-cyan-400">
                                                        [{group.codigo_grupo}]
                                                    </span>
                                                    <span className="truncate font-medium">{group.nombre}</span>
                                                    {archived && (
                                                        <span className="shrink-0 px-1.5 py-0.5 rounded text-[9px] font-bold uppercase tracking-wider border bg-slate-500/10 text-content-muted border-slate-500/30">
                                                            Archivado
                                                        </span>
                                                    )}
                                                </div>
                                                <span className="text-[10px] text-content-muted block mt-0.5">
                                                    Periodo: {group.periodo} • {group.total_entregas || 0} entregas
                                                </span>
                                            </div>
                                            {isSelected && <Check size={14} className="text-cyan-400 shrink-0" />}
                                        </button>
                                        <div className="flex items-center gap-0.5 pr-1.5 shrink-0">
                                            {archived && onUnarchiveGroup && (
                                                <button
                                                    type="button"
                                                    onClick={() => onUnarchiveGroup(group)}
                                                    title="Desarchivar grupo"
                                                    aria-label={`Desarchivar ${group.nombre}`}
                                                    className="p-1.5 rounded-lg text-content-muted hover:text-cyan-400 transition-colors"
                                                >
                                                    <ArchiveRestore size={14} />
                                                </button>
                                            )}
                                            {!archived && onArchiveGroup && (
                                                <button
                                                    type="button"
                                                    onClick={() => onArchiveGroup(group)}
                                                    title="Archivar grupo"
                                                    aria-label={`Archivar ${group.nombre}`}
                                                    className="p-1.5 rounded-lg text-content-muted hover:text-cyan-400 transition-colors"
                                                >
                                                    <Archive size={14} />
                                                </button>
                                            )}
                                            {onDeleteGroup && (
                                                <button
                                                    type="button"
                                                    onClick={() => onDeleteGroup(group)}
                                                    title="Eliminar grupo"
                                                    aria-label={`Eliminar ${group.nombre}`}
                                                    className="p-1.5 rounded-lg text-content-muted hover:text-rose-400 transition-colors"
                                                >
                                                    <Trash2 size={14} />
                                                </button>
                                            )}
                                        </div>
                                    </div>
                                );
                            })
                        )}
                    </div>

                    <div className="h-px bg-line-subtle my-1" />

                    {/* Botón de crear nuevo grupo */}
                    <button
                        type="button"
                        onClick={() => {
                            setIsOpen(false);
                            onCreateGroupClick();
                        }}
                        className="w-full flex items-center justify-center gap-2 px-3 py-2 rounded-xl text-xs font-semibold text-cyan-400 hover:text-cyan-300 hover:bg-cyan-500/10 transition-colors"
                    >
                        <Plus size={14} />
                        <span>Crear nuevo curso o grupo</span>
                    </button>
                </div>
            )}
        </div>
    );
}
