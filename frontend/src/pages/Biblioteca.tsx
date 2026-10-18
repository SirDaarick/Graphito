import { useState, useEffect } from "react";
import { ReferenceCard, Comparison } from "../components/layout/ReferenceCard";
import { PaginationControls } from "../components/ui/PaginationControls";
import { SearchBar } from "../components/layout/SearchBar";
import { api, Grupo, CodigoFuente } from "../lib/api";
import { toComparison } from "../lib/dictamen";
import { Loader2, UploadCloud, BookOpen, Archive } from "lucide-react";
import { GroupFilterDropdown } from "../components/groups/GroupFilterDropdown";
import { CreateGroupModal } from "../components/groups/CreateGroupModal";
import { BulkUploadModal } from "../components/batch/BulkUploadModal";
import { AssignGroupModal } from "../components/groups/AssignGroupModal";
import { ConfirmDialog } from "../components/ui/ConfirmDialog";

type PendingAction =
    | { kind: "delete-problem"; id: number; title: string }
    | { kind: "delete-group"; group: Grupo };

interface Reference {
    id: string;
    problemId: number;
    archived: boolean;
    title: string;
    category: string;
    categoryColor: string;
    description: string;
    updatedAt: string;
    activeComparisons: number;
    comparisons: Comparison[];
}

export function Biblioteca({
    refreshTrigger = 0,
    onCompare,
    onComparisonClick,
    onGoToCatalog
}: {
    refreshTrigger?: number,
    onCompare?: () => void,
    onGoToCatalog?: () => void,
    onComparisonClick?: (comparison: Comparison, allComparisons?: Comparison[]) => void
}) {
    const [currentPage, setCurrentPage] = useState(1);
    const [searchTerm, setSearchTerm] = useState("");
    const [references, setReferences] = useState<Reference[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [groups, setGroups] = useState<Grupo[]>([]);
    const [selectedGroupId, setSelectedGroupId] = useState<number | null>(null);
    const [isCreateGroupOpen, setIsCreateGroupOpen] = useState(false);
    const [isBulkUploadOpen, setIsBulkUploadOpen] = useState(false);
    const [bulkUploadProblemId, setBulkUploadProblemId] = useState<number | null>(null);
    const [showArchived, setShowArchived] = useState(false);
    const [assignTarget, setAssignTarget] = useState<{ id: number; title: string } | null>(null);
    const [pendingAction, setPendingAction] = useState<PendingAction | null>(null);
    const [isActing, setIsActing] = useState(false);
    const [actionError, setActionError] = useState<string | null>(null);
    const itemsPerPage = 10;

    const fetchGroups = async () => {
        try {
            const data = await api.groups.list(showArchived);
            setGroups(data);
        } catch (err) {
            console.warn("Error al cargar grupos académicos:", err);
        }
    };

    const fetchProblems = async () => {
        // Solo activamos spinner si no hay referencias cargadas todavía
        if (references.length === 0) {
            setIsLoading(true);
        }
        try {
            const problems = await api.problems.list(showArchived);
            if (problems && problems.length > 0) {
                const mapped = await Promise.all(
                    problems.map(async (p) => {
                        let subs: CodigoFuente[] = [];
                        try {
                            subs = await api.problems.listSubmissions(p.id);
                        } catch {
                            // ok
                        }
                        return {
                            id: String(p.id),
                            problemId: p.id,
                            archived: Boolean(p.archivado),
                            title: p.titulo,
                            category: p.lenguaje.toUpperCase(),
                            categoryColor: p.lenguaje === "cpp" ? "purple" : "cyan",
                            description: p.enunciado,
                            updatedAt: new Date(p.fecha_creacion).toLocaleDateString("es-MX", {
                                day: "2-digit",
                                month: "short",
                                year: "numeric",
                            }),
                            activeComparisons: subs.length,
                            comparisons: subs.map((s, idx) => {
                                const rep = s.reporte;
                                if (rep) {
                                    const view = toComparison(rep, `${s.autor}`, s.grupo_id);
                                    return { ...view, subtitle: `${view.subtitle} (${s.lenguaje})` };
                                }
                                // Sin reporte todavía: sin puntaje (nunca 0%) y sin estado de similitud.
                                return {
                                    id: String(s.id),
                                    title: `${s.autor}`,
                                    subtitle: `Entrega #${idx + 1} (${s.lenguaje})`,
                                    similarity: null,
                                    grupo_id: s.grupo_id,
                                };
                            }),
                        } as Reference;
                    })
                );
                setReferences(mapped);
            } else {
                setReferences([]);
            }
        } catch (err) {
            console.error("Error al cargar problemas:", err);
        } finally {
            setIsLoading(false);
        }
    };

    useEffect(() => {
        fetchGroups();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [showArchived]);

    useEffect(() => {
        fetchProblems();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [refreshTrigger, showArchived]);

    const reportError = (err: unknown) => {
        setActionError(err instanceof Error ? err.message : "No se pudo completar la acción.");
    };

    const handleToggleProblemArchive = async (ref: Reference) => {
        try {
            if (ref.archived) await api.problems.unarchive(ref.problemId);
            else await api.problems.archive(ref.problemId);
            await fetchProblems();
        } catch (err) {
            reportError(err);
        }
    };

    const handleToggleGroupArchive = async (group: Grupo, archive: boolean) => {
        try {
            if (archive) await api.groups.archive(group.id);
            else await api.groups.unarchive(group.id);
            if (archive && group.id === selectedGroupId) setSelectedGroupId(null);
            await fetchGroups();
        } catch (err) {
            reportError(err);
        }
    };

    const closePending = () => {
        if (isActing) return;
        setPendingAction(null);
        setActionError(null);
    };

    const confirmPending = async () => {
        if (!pendingAction) return;
        setIsActing(true);
        setActionError(null);
        try {
            if (pendingAction.kind === "delete-problem") {
                await api.problems.delete(pendingAction.id);
                await Promise.all([fetchProblems(), fetchGroups()]);
            } else {
                await api.groups.delete(pendingAction.group.id);
                if (pendingAction.group.id === selectedGroupId) setSelectedGroupId(null);
                await Promise.all([fetchGroups(), fetchProblems()]);
            }
            setPendingAction(null);
        } catch (err) {
            reportError(err);
        } finally {
            setIsActing(false);
        }
    };

    const handleGroupCreated = (newGroup: Grupo) => {
        setGroups((prev) => [newGroup, ...prev]);
        setSelectedGroupId(newGroup.id);
        setIsCreateGroupOpen(false);
    };

    const handleBatchComplete = () => {
        fetchProblems();
        fetchGroups();
    };

    // Filtrar entregas por grupo seleccionado
    const displayedReferences = references.map((ref) => {
        if (selectedGroupId === null) return ref;
        const groupComparisons = ref.comparisons.filter((c) => c.grupo_id === selectedGroupId);
        return {
            ...ref,
            activeComparisons: groupComparisons.length,
            comparisons: groupComparisons,
        };
    });

    // Filtrar referencias según el término de búsqueda
    const filteredReferences = displayedReferences.filter((ref) => {
        const term = searchTerm.toLowerCase();
        return (
            ref.title.toLowerCase().includes(term) ||
            ref.description.toLowerCase().includes(term) ||
            ref.category.toLowerCase().includes(term)
        );
    });

    const totalItems = filteredReferences.length;
    const totalPages = Math.ceil(totalItems / itemsPerPage);

    const startIndex = (currentPage - 1) * itemsPerPage;
    const paginatedReferences = filteredReferences.slice(startIndex, startIndex + itemsPerPage);

    const handleSearchChange = (value: string) => {
        setSearchTerm(value);
        setCurrentPage(1); // Resetear a la primera página al buscar
    };

    return (
        <main id="main-content" className="max-w-7xl mx-auto p-8 flex-1 w-full flex flex-col transition-colors duration-200" tabIndex={-1}>
            <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 mb-8">
                <div>
                    <h2 className="text-3xl font-display font-black text-slate-900 dark:text-white transition-colors">
                        Mi Biblioteca
                    </h2>
                    <p className="text-slate-600 dark:text-slate-400 font-body mt-2 transition-colors">
                        Gestiona tus soluciones de referencia en C/C++ y supervisa el análisis de similitud entre entregas del curso.
                    </p>
                </div>

                {/* Acciones de Cursos y Carga Masiva */}
                <div className="flex items-center gap-3 shrink-0 flex-wrap">
                    <GroupFilterDropdown
                        groups={groups}
                        selectedGroupId={selectedGroupId}
                        onSelectGroup={setSelectedGroupId}
                        onCreateGroupClick={() => setIsCreateGroupOpen(true)}
                        onArchiveGroup={(g) => handleToggleGroupArchive(g, true)}
                        onUnarchiveGroup={(g) => handleToggleGroupArchive(g, false)}
                        onDeleteGroup={(g) => {
                            setActionError(null);
                            setPendingAction({ kind: "delete-group", group: g });
                        }}
                    />
                    <button
                        type="button"
                        onClick={() => setShowArchived(!showArchived)}
                        aria-pressed={showArchived}
                        className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold border active:scale-95 transition-all ${
                            showArchived
                                ? "bg-graphito-violet/10 border-graphito-violet/40 text-graphito-violet"
                                : "bg-slate-100 dark:bg-graphito-dark border-slate-200 dark:border-graphito-border text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white"
                        }`}
                    >
                        <Archive size={16} />
                        <span>{showArchived ? "Ocultar archivados" : "Mostrar archivados"}</span>
                    </button>
                    <button
                        type="button"
                        onClick={() => {
                            setBulkUploadProblemId(null);
                            setIsBulkUploadOpen(true);
                        }}
                        className="flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold text-white bg-gradient-to-r from-graphito-blue to-graphito-violet hover:opacity-95 shadow-md shadow-graphito-blue/20 active:scale-95 transition-all"
                    >
                        <UploadCloud size={16} />
                        <span>Carga Masiva</span>
                    </button>
                </div>
            </div>

            <SearchBar searchTerm={searchTerm} onSearchChange={handleSearchChange} />

            {actionError && !pendingAction && (
                <div className="mb-4 p-3 bg-red-500/10 border border-red-500/30 rounded-xl text-red-600 dark:text-red-300 text-xs font-medium">
                    {actionError}
                </div>
            )}

            {isLoading ? (
                <div className="flex flex-col items-center justify-center py-20 text-slate-500 dark:text-slate-400">
                    <Loader2 className="w-8 h-8 animate-spin text-graphito-blue mb-3" />
                    <p className="text-sm font-medium">Cargando soluciones de referencia...</p>
                </div>
            ) : references.length === 0 && !showArchived ? (
                <div className="flex flex-col items-center justify-center border border-graphito-blue/30 rounded-2xl p-10 text-center my-4 bg-gradient-to-br from-graphito-blue/10 to-graphito-violet/10 transition-colors">
                    <div className="w-12 h-12 rounded-2xl bg-graphito-blue/15 text-graphito-blue flex items-center justify-center mb-4">
                        <BookOpen size={24} />
                    </div>
                    <p className="text-slate-900 dark:text-white font-display font-bold text-xl mb-2">
                        ¿No sabes por dónde empezar?
                    </p>
                    <p className="text-slate-600 dark:text-slate-400 text-sm max-w-md mb-6">
                        Agrega un código precargado del catálogo y empieza a comparar entregas sin subir tu propio código.
                    </p>
                    <button
                        type="button"
                        onClick={() => onGoToCatalog?.()}
                        className="flex items-center gap-2 px-6 py-3 rounded-2xl text-sm font-bold text-white bg-gradient-to-r from-graphito-blue to-graphito-violet hover:opacity-95 shadow-md shadow-graphito-blue/20 active:scale-95 focus:outline-none focus-visible:ring-2 focus-visible:ring-graphito-blue/50 transition-all"
                    >
                        <BookOpen size={16} />
                        <span>Ir al catálogo</span>
                    </button>
                </div>
            ) : filteredReferences.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-20 border border-dashed border-slate-300 dark:border-[#2b3346] rounded-2xl p-8 text-center my-4 bg-white/60 dark:bg-[#121827]/20 transition-colors">
                    <p className="text-slate-800 dark:text-slate-300 font-bold text-lg mb-1">
                        {selectedGroupId !== null
                            ? "No hay entregas para el grupo académico seleccionado"
                            : "No hay soluciones de referencia registradas"}
                    </p>
                    <p className="text-slate-600 dark:text-slate-500 text-sm max-w-md">
                        {selectedGroupId !== null
                            ? "Utiliza 'Carga Masiva' para procesar el lote de entregas de este curso o asigna problemas a este grupo."
                            : "Comienza agregando tu primera solución de referencia en C o C++ haciendo clic en 'Nuevo Código' en la esquina superior."}
                    </p>
                </div>
            ) : (
                <div className="flex flex-col">
                    {paginatedReferences.map((ref) => (
                        <ReferenceCard
                            key={ref.id}
                            title={ref.title}
                            category={ref.category}
                            categoryColor={ref.categoryColor as "cyan" | "purple" | "orange"}
                            description={ref.description}
                            updatedAt={ref.updatedAt}
                            activeComparisons={ref.activeComparisons}
                            comparisons={ref.comparisons}
                            onCompare={onCompare}
                            onComparisonClick={onComparisonClick}
                            archived={ref.archived}
                            onAssignToGroup={() => setAssignTarget({ id: ref.problemId, title: ref.title })}
                            onToggleArchive={() => handleToggleProblemArchive(ref)}
                            onDelete={() => {
                                setActionError(null);
                                setPendingAction({ kind: "delete-problem", id: ref.problemId, title: ref.title });
                            }}
                        />
                    ))}
                </div>
            )}

            {totalItems > itemsPerPage && (
                <PaginationControls
                    currentPage={currentPage}
                    totalPages={totalPages}
                    totalItems={totalItems}
                    itemsPerPage={itemsPerPage}
                    onPageChange={setCurrentPage}
                />
            )}

            {/* Modales de Gestión de Cursos y Carga Masiva */}
            <CreateGroupModal
                isOpen={isCreateGroupOpen}
                onClose={() => setIsCreateGroupOpen(false)}
                onGroupCreated={handleGroupCreated}
            />

            <AssignGroupModal
                isOpen={assignTarget !== null}
                problemId={assignTarget?.id ?? null}
                problemTitle={assignTarget?.title ?? ""}
                groups={groups}
                onClose={() => setAssignTarget(null)}
                onAssigned={fetchGroups}
            />

            <ConfirmDialog
                isOpen={pendingAction !== null}
                title={pendingAction?.kind === "delete-group" ? "Eliminar grupo" : "Eliminar problema"}
                message={
                    pendingAction?.kind === "delete-group" ? (
                        <>
                            Se eliminará el grupo <strong>[{pendingAction.group.codigo_grupo}] {pendingAction.group.nombre}</strong> y sus
                            asignaciones. Los problemas y las entregas se conservan, solo quedan sin grupo. Esta acción no se puede deshacer.
                            Si solo quieres ocultarlo, archívalo.
                        </>
                    ) : pendingAction ? (
                        <>
                            Se eliminará <strong>{pendingAction.title}</strong> junto con sus entregas, análisis y referencias indexadas.
                            Esta acción no se puede deshacer. Si solo quieres ocultarlo, archívalo.
                        </>
                    ) : null
                }
                confirmLabel="Eliminar"
                loadingLabel="Eliminando..."
                isLoading={isActing}
                error={actionError}
                onConfirm={confirmPending}
                onCancel={closePending}
            />

            <BulkUploadModal
                isOpen={isBulkUploadOpen}
                onClose={() => setIsBulkUploadOpen(false)}
                onBatchComplete={handleBatchComplete}
                preselectedProblemId={bulkUploadProblemId}
                preselectedGroupId={selectedGroupId}
            />
        </main>
    );
}