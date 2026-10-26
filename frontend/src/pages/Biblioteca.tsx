import { useState, useEffect } from "react";
import { ReferenceCard, Comparison } from "../components/layout/ReferenceCard";
import { PaginationControls } from "../components/ui/PaginationControls";
import { SearchBar } from "../components/layout/SearchBar";
import { api, Grupo, CodigoFuente } from "../lib/api";
import { toComparison } from "../lib/dictamen";
import { navigate } from "../lib/router";
import {
    Loader2,
    UploadCloud,
    BookOpen,
    Archive,
    ArrowUpDown,
    FolderKanban,
    Layers,
    ChevronDown,
} from "lucide-react";
import { GroupFilterDropdown } from "../components/groups/GroupFilterDropdown";
import { CreateGroupModal } from "../components/groups/CreateGroupModal";
import { BulkUploadModal } from "../components/batch/BulkUploadModal";
import { AssignGroupModal } from "../components/groups/AssignGroupModal";
import { ConfirmDialog } from "../components/ui/ConfirmDialog";

type PendingAction =
    | { kind: "delete-problem"; id: number; title: string }
    | { kind: "delete-group"; group: Grupo };

type SortOption = "recientes" | "similitud" | "entregas" | "alfabetico";

interface Reference {
    id: string;
    problemId: number;
    archived: boolean;
    title: string;
    lenguaje: string;
    category: string;
    categoryColor: string;
    description: string;
    updatedAt: string;
    rawDate: number;
    maxSimilarity: number;
    activeComparisons: number;
    comparisons: Comparison[];
    assignedGroups: Grupo[];
}

export function Biblioteca({
    refreshTrigger = 0,
    onCompare,
    onComparisonClick,
    onGoToCatalog,
}: {
    refreshTrigger?: number;
    onCompare?: (problem: { id: number; title: string; lenguaje: string }) => void;
    onGoToCatalog?: () => void;
    onComparisonClick?: (comparison: Comparison, allComparisons?: Comparison[]) => void;
}) {
    const [currentPage, setCurrentPage] = useState(1);
    const [searchTerm, setSearchTerm] = useState("");
    const [selectedLanguage, setSelectedLanguage] = useState<"todos" | "c" | "cpp">("todos");
    const [sortBy, setSortBy] = useState<SortOption>("recientes");
    const [groupByCourse, setGroupByCourse] = useState(false);
    const [expandedGroupIds, setExpandedGroupIds] = useState<Set<string>>(() => new Set());

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
    const [failedSubmissions, setFailedSubmissions] = useState<string[]>([]);
    const [loadFailed, setLoadFailed] = useState(false);
    const itemsPerPage = 10;

    const fetchGroups = async () => {
        try {
            const data = await api.groups.list(showArchived);
            setGroups(data);
            return data;
        } catch (err) {
            console.warn("Error al cargar grupos académicos:", err);
            return [];
        }
    };

    const fetchProblems = async () => {
        if (references.length === 0) {
            setIsLoading(true);
        }
        const failedTitles: string[] = [];
        try {
            const [problems, groupList] = await Promise.all([
                api.problems.list(showArchived, true),
                api.groups.list(showArchived).catch(() => groups),
            ]);
            setLoadFailed(false);
            if (groupList && groupList.length > 0) {
                setGroups(groupList);
            }

            // Map group assignments by querying group details in parallel
            const groupAssignmentsMap = new Map<number, number[]>();
            if (groupList && groupList.length > 0) {
                await Promise.allSettled(
                    groupList.map(async (g) => {
                        try {
                            const detail = await api.groups.get(g.id);
                            const asignaciones =
                                (detail as unknown as { asignaciones?: Array<{ problema_id: number }> })
                                    ?.asignaciones || [];
                            groupAssignmentsMap.set(
                                g.id,
                                asignaciones.map((a) => a.problema_id)
                            );
                        } catch {
                            // ignore fallback
                        }
                    })
                );
            }

            if (problems && problems.length > 0) {
                const mapped = await Promise.all(
                    problems.map(async (p) => {
                        let subs: CodigoFuente[] = [];
                        if (p.entregas !== undefined) {
                            subs = p.entregas;
                        } else {
                            try {
                                subs = await api.problems.listSubmissions(p.id);
                            } catch (err) {
                                console.error(`Error al cargar las entregas del problema ${p.id}:`, err);
                                failedTitles.push(p.titulo);
                            }
                        }

                        // Determine assigned groups for this problem
                        const groupIds = new Set<number>();
                        subs.forEach((s) => {
                            if (s.grupo_id != null) groupIds.add(s.grupo_id);
                        });
                        for (const [gid, pids] of groupAssignmentsMap.entries()) {
                            if (pids.includes(p.id)) groupIds.add(gid);
                        }
                        const currentGroups = groupList && groupList.length > 0 ? groupList : groups;
                        const assignedGroups = currentGroups.filter((g) => groupIds.has(g.id));

                        // Find maximum similarity for sorting
                        let maxSim = 0;
                        subs.forEach((s) => {
                            const sim = s.reporte?.similitud_semantica;
                            if (sim != null && sim > maxSim) {
                                maxSim = sim;
                            }
                        });

                        return {
                            id: String(p.id),
                            problemId: p.id,
                            archived: Boolean(p.archivado),
                            title: p.titulo,
                            lenguaje: p.lenguaje,
                            category: p.lenguaje.toUpperCase(),
                            categoryColor: p.lenguaje === "cpp" ? "purple" : "cyan",
                            description: p.enunciado,
                            updatedAt: new Date(p.fecha_creacion).toLocaleDateString("es-MX", {
                                day: "2-digit",
                                month: "short",
                                year: "numeric",
                            }),
                            rawDate: new Date(p.fecha_creacion).getTime(),
                            maxSimilarity: maxSim,
                            activeComparisons: subs.length,
                            assignedGroups,
                            comparisons: subs.map((s, idx) => {
                                const rep = s.reporte;
                                if (rep) {
                                    const view = toComparison(rep, `${s.autor}`, s.grupo_id);
                                    return { ...view, subtitle: `${view.subtitle} (${s.lenguaje})` };
                                }
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
            setLoadFailed(true);
        } finally {
            setFailedSubmissions(failedTitles);
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

    useEffect(() => {
        const handleRefresh = () => {
            fetchProblems();
            fetchGroups();
        };
        window.addEventListener("graphito_library_refresh", handleRefresh);
        return () => window.removeEventListener("graphito_library_refresh", handleRefresh);
    }, [showArchived]);

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

    // 1. Filtrar entregas por grupo académico seleccionado en el filtro superior
    const groupFilteredReferences = references
        .filter((ref) => {
            if (selectedGroupId === null) return true;
            return (
                ref.assignedGroups.some((g) => g.id === selectedGroupId) ||
                ref.comparisons.some((c) => c.grupo_id === selectedGroupId)
            );
        })
        .map((ref) => {
            if (selectedGroupId === null) return ref;
            const groupComparisons = ref.comparisons.filter((c) => c.grupo_id === selectedGroupId);
            return {
                ...ref,
                activeComparisons: groupComparisons.length,
                comparisons: groupComparisons,
            };
        });

    // 2. Filtrar por término de búsqueda y lenguaje
    const filteredReferences = groupFilteredReferences.filter((ref) => {
        if (selectedLanguage !== "todos") {
            if (ref.lenguaje.toLowerCase() !== selectedLanguage.toLowerCase()) {
                return false;
            }
        }
        const term = searchTerm.toLowerCase().trim();
        if (!term) return true;
        return (
            ref.title.toLowerCase().includes(term) ||
            ref.description.toLowerCase().includes(term) ||
            ref.category.toLowerCase().includes(term) ||
            ref.assignedGroups.some(
                (g) =>
                    g.nombre.toLowerCase().includes(term) ||
                    g.codigo_grupo.toLowerCase().includes(term)
            )
        );
    });

    // 3. Ordenamiento
    const sortedReferences = [...filteredReferences].sort((a, b) => {
        switch (sortBy) {
            case "recientes":
                return b.rawDate - a.rawDate;
            case "similitud":
                return b.maxSimilarity - a.maxSimilarity;
            case "entregas":
                return b.activeComparisons - a.activeComparisons;
            case "alfabetico":
                return a.title.localeCompare(b.title, "es", { sensitivity: "base" });
            default:
                return 0;
        }
    });

    const totalItems = sortedReferences.length;
    const totalPages = Math.ceil(totalItems / itemsPerPage);
    const startIndex = (currentPage - 1) * itemsPerPage;
    const paginatedReferences = sortedReferences.slice(startIndex, startIndex + itemsPerPage);

    const handleSearchChange = (value: string) => {
        setSearchTerm(value);
        setCurrentPage(1);
    };

    const renderCard = (ref: Reference) => (
        <ReferenceCard
            key={ref.id}
            title={ref.title}
            category={ref.category}
            categoryColor={ref.categoryColor as "cyan" | "purple" | "orange"}
            description={ref.description}
            updatedAt={ref.updatedAt}
            activeComparisons={ref.activeComparisons}
            comparisons={ref.comparisons}
            assignedGroups={ref.assignedGroups}
            onCompare={() => onCompare?.({ id: ref.problemId, title: ref.title, lenguaje: ref.lenguaje })}
            onComparisonClick={onComparisonClick}
            archived={ref.archived}
            onAssignToGroup={() => setAssignTarget({ id: ref.problemId, title: ref.title })}
            onToggleArchive={() => handleToggleProblemArchive(ref)}
            onDelete={() => {
                setActionError(null);
                setPendingAction({ kind: "delete-problem", id: ref.problemId, title: ref.title });
            }}
        />
    );

    // Grouping computation when groupByCourse is active
    const courseGroups = groups
        .map((group) => {
            const problems = sortedReferences.filter((ref) =>
                ref.assignedGroups.some((g) => g.id === group.id)
            );
            return {
                group,
                problems,
            };
        })
        .filter((cg) => cg.problems.length > 0);

    const unassignedProblems = sortedReferences.filter(
        (ref) => ref.assignedGroups.length === 0
    );

    const allGroupKeys = [
        ...courseGroups.map((cg) => `group-${cg.group.id}`),
        ...(unassignedProblems.length > 0 ? ["unassigned"] : []),
    ];

    const isAllExpanded =
        allGroupKeys.length > 0 && allGroupKeys.every((key) => expandedGroupIds.has(key));

    const toggleAllGroups = () => {
        if (isAllExpanded) {
            setExpandedGroupIds(new Set());
        } else {
            setExpandedGroupIds(new Set(allGroupKeys));
        }
    };

    const toggleGroupExpand = (key: string) => {
        setExpandedGroupIds((prev) => {
            const next = new Set(prev);
            if (next.has(key)) {
                next.delete(key);
            } else {
                next.add(key);
            }
            return next;
        });
    };

    return (
        <main
            id="main-content"
            className="max-w-7xl mx-auto p-4 sm:p-6 lg:p-8 flex-1 w-full flex flex-col transition-colors duration-200"
            tabIndex={-1}
        >
            {/* Header principal */}
            <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 mb-8">
                <div>
                    <h2 className="text-3xl font-display font-black text-slate-900 dark:text-white transition-colors">
                        Mi Biblioteca
                    </h2>
                    <p className="text-slate-600 dark:text-slate-300 font-body mt-2 transition-colors">
                        Gestiona tus soluciones de referencia en C/C++ y supervisa el análisis de similitud entre entregas del curso.
                    </p>
                </div>

                {/* Acciones de Cursos y Carga Masiva */}
                <div className="flex items-center gap-3 shrink-0 flex-wrap">
                    <GroupFilterDropdown
                        groups={groups}
                        selectedGroupId={selectedGroupId}
                        onSelectGroup={(id) => {
                            setSelectedGroupId(id);
                            setCurrentPage(1);
                        }}
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
                        className={`flex items-center gap-2 px-4 py-2.5 min-h-[44px] rounded-xl text-xs font-bold border active:scale-95 transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-graphito-blue shadow-sm backdrop-blur-md ${
                            showArchived
                                ? "bg-graphito-violet/15 border-graphito-violet/40 text-graphito-violet"
                                : "bg-white/25 dark:bg-graphito-card/15 border-slate-200/60 dark:border-white/10 text-slate-700 dark:text-slate-300 hover:text-slate-900 dark:hover:text-white hover:border-graphito-blue/40"
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
                        className="flex items-center gap-2 px-4 py-2.5 min-h-[44px] rounded-xl text-xs font-bold text-white bg-gradient-to-r from-graphito-blue to-graphito-violet hover:opacity-95 shadow-md shadow-graphito-blue/20 active:scale-95 transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-graphito-blue"
                    >
                        <UploadCloud size={16} />
                        <span>Carga Masiva</span>
                    </button>
                </div>
            </div>

            {/* Barra de Filtros, Ordenamiento y Búsqueda */}
            <div className="flex flex-col gap-4 mb-8">
                <SearchBar
                    searchTerm={searchTerm}
                    onSearchChange={handleSearchChange}
                    placeholder="Buscar por título, descripción, lenguaje o grupo..."
                />

                <div className="flex flex-wrap items-center justify-between gap-3 p-3 rounded-2xl bg-white/25 dark:bg-graphito-card/15 backdrop-blur-md border border-slate-200/60 dark:border-white/10">
                    {/* Filtro de Lenguaje */}
                    <div className="flex items-center gap-1.5">
                        <span className="text-xs font-bold text-slate-500 dark:text-slate-400 mr-1.5 uppercase tracking-wider text-[11px]">
                            Lenguaje:
                        </span>
                        <button
                            type="button"
                            onClick={() => {
                                setSelectedLanguage("todos");
                                setCurrentPage(1);
                            }}
                            className={`px-3 py-1.5 rounded-xl text-xs font-bold transition-all ${
                                selectedLanguage === "todos"
                                    ? "bg-slate-900 text-white dark:bg-white dark:text-slate-950 shadow-sm"
                                    : "text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-graphito-dark"
                            }`}
                        >
                            Todos
                        </button>
                        <button
                            type="button"
                            onClick={() => {
                                setSelectedLanguage("c");
                                setCurrentPage(1);
                            }}
                            className={`px-3 py-1.5 rounded-xl text-xs font-bold border transition-all ${
                                selectedLanguage === "c"
                                    ? "bg-blue-500/20 text-blue-600 dark:text-blue-400 border-blue-500/50 shadow-sm"
                                    : "border-transparent text-slate-600 dark:text-slate-300 hover:bg-blue-500/10 hover:text-blue-500"
                            }`}
                        >
                            C
                        </button>
                        <button
                            type="button"
                            onClick={() => {
                                setSelectedLanguage("cpp");
                                setCurrentPage(1);
                            }}
                            className={`px-3 py-1.5 rounded-xl text-xs font-bold border transition-all ${
                                selectedLanguage === "cpp"
                                    ? "bg-pink-500/20 text-pink-600 dark:text-pink-400 border-pink-500/50 shadow-sm"
                                    : "border-transparent text-slate-600 dark:text-slate-300 hover:bg-pink-500/10 hover:text-pink-500"
                            }`}
                        >
                            C++
                        </button>
                    </div>

                    {/* Controles de Ordenamiento y Vista Agrupada */}
                    <div className="flex items-center gap-3 flex-wrap">
                        {/* Selector de Orden */}
                        <div className="flex items-center gap-2">
                            <ArrowUpDown size={14} className="text-slate-400 dark:text-slate-500 shrink-0" />
                            <label htmlFor="sort-select" className="text-xs font-bold text-slate-500 dark:text-slate-400 text-[11px] uppercase tracking-wider">
                                Ordenar:
                            </label>
                            <select
                                id="sort-select"
                                value={sortBy}
                                onChange={(e) => setSortBy(e.target.value as SortOption)}
                                className="px-3 py-1.5 rounded-xl text-xs font-semibold bg-white/50 dark:bg-graphito-dark/80 border border-slate-200/80 dark:border-white/10 text-slate-700 dark:text-slate-200 focus:outline-none focus:ring-2 focus:ring-graphito-blue cursor-pointer"
                            >
                                <option value="recientes">Más recientes</option>
                                <option value="similitud">Mayor similitud</option>
                                <option value="entregas">Más entregas</option>
                                <option value="alfabetico">Alfabético (A-Z)</option>
                            </select>
                        </div>

                        {/* Alternar Vista Agrupada por Curso */}
                        <button
                            type="button"
                            onClick={() => setGroupByCourse(!groupByCourse)}
                            aria-pressed={groupByCourse}
                            className={`flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl text-xs font-bold border transition-all active:scale-95 ${
                                groupByCourse
                                    ? "bg-graphito-blue/15 border-graphito-blue/50 text-graphito-blue dark:text-cyan-300 shadow-sm"
                                    : "border-slate-200/80 dark:border-white/10 text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-graphito-dark"
                            }`}
                            title="Agrupa los problemas visualmente por curso académico asignado"
                        >
                            <FolderKanban size={14} />
                            <span>{groupByCourse ? "Agrupado por curso" : "Agrupar por curso"}</span>
                        </button>

                        {groupByCourse && allGroupKeys.length > 0 && (
                            <button
                                type="button"
                                onClick={toggleAllGroups}
                                className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-bold border border-slate-200/80 dark:border-white/10 text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-graphito-dark transition-all active:scale-95"
                                title={isAllExpanded ? "Colapsar todos los cursos" : "Expandir todos los cursos"}
                            >
                                <Layers size={13} className="text-graphito-blue" />
                                <span>{isAllExpanded ? "Colapsar todo" : "Expandir todo"}</span>
                            </button>
                        )}
                    </div>
                </div>
            </div>

            {actionError && !pendingAction && (
                <div className="mb-4 p-3 bg-red-500/10 border border-red-500/30 rounded-xl text-red-600 dark:text-red-300 text-xs font-medium">
                    {actionError}
                </div>
            )}

            {!isLoading && (loadFailed || failedSubmissions.length > 0) && (
                <div
                    role="alert"
                    className="mb-4 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 p-4 bg-amber-500/10 border border-amber-500/30 rounded-xl text-amber-800 dark:text-amber-200 text-sm"
                >
                    <div>
                        <p className="font-bold">
                            {loadFailed ? "No se pudo cargar la biblioteca." : "No se pudieron cargar algunas entregas."}
                        </p>
                        <p className="mt-0.5 text-xs">
                            {loadFailed
                                ? "Revisa tu conexión e inténtalo de nuevo."
                                : `Los conteos de comparaciones pueden estar incompletos en: ${failedSubmissions.join(", ")}. Inténtalo de nuevo en unos momentos.`}
                        </p>
                    </div>
                    <button
                        type="button"
                        onClick={() => fetchProblems()}
                        className="shrink-0 px-4 py-2.5 min-h-[44px] rounded-xl text-xs font-bold border border-amber-500/40 hover:bg-amber-500/20 active:scale-95 transition-all focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-400/60"
                    >
                        Reintentar
                    </button>
                </div>
            )}

            {isLoading ? (
                <div className="flex flex-col items-center justify-center py-20 text-slate-500 dark:text-slate-400">
                    <Loader2 className="w-8 h-8 animate-spin text-graphito-blue mb-3" />
                    <p className="text-sm font-medium">Cargando soluciones de referencia...</p>
                </div>
            ) : references.length === 0 && !showArchived && !loadFailed ? (
                <div className="flex flex-col items-center justify-center border border-graphito-blue/30 rounded-2xl p-10 text-center my-4 bg-gradient-to-br from-graphito-blue/10 to-graphito-violet/10 transition-colors">
                    <div className="w-12 h-12 rounded-2xl bg-graphito-blue/15 text-graphito-blue flex items-center justify-center mb-4">
                        <BookOpen size={24} />
                    </div>
                    <p className="text-slate-900 dark:text-white font-display font-bold text-xl mb-2">
                        ¿No sabes por dónde empezar?
                    </p>
                    <p className="text-slate-600 dark:text-slate-300 text-sm max-w-md mb-6">
                        Agrega un código precargado del catálogo y empieza a comparar entregas sin subir tu propio código.
                    </p>
                    <button
                        type="button"
                        onClick={() => {
                            navigate("/catalogo");
                            onGoToCatalog?.();
                        }}
                        className="flex items-center gap-2 px-6 py-3 min-h-[44px] rounded-2xl text-sm font-bold text-white bg-gradient-to-r from-graphito-blue to-graphito-violet hover:opacity-95 shadow-md shadow-graphito-blue/20 active:scale-95 focus:outline-none focus-visible:ring-2 focus-visible:ring-graphito-blue transition-all"
                    >
                        <BookOpen size={16} />
                        <span>Ir al catálogo</span>
                    </button>
                </div>
            ) : sortedReferences.length === 0 && !loadFailed ? (
                <div className="flex flex-col items-center justify-center py-20 border border-dashed border-slate-300 dark:border-graphito-subtle rounded-2xl p-8 text-center my-4 bg-white/60 dark:bg-graphito-surface/20 transition-colors">
                    <p className="text-slate-800 dark:text-slate-200 font-bold text-lg mb-1">
                        {selectedGroupId !== null
                            ? "No hay entregas para el grupo académico seleccionado"
                            : "No se encontraron soluciones de referencia"}
                    </p>
                    <p className="text-slate-600 dark:text-slate-400 text-sm max-w-md">
                        {selectedGroupId !== null
                            ? "Utiliza 'Carga Masiva' para procesar el lote de entregas de este curso o asigna problemas a este grupo."
                            : searchTerm || selectedLanguage !== "todos"
                            ? "Intenta modificar los filtros de búsqueda o el lenguaje seleccionado."
                            : "Comienza agregando tu primera solución de referencia en C o C++ haciendo clic en 'Nuevo Código' en la esquina superior."}
                    </p>
                </div>
            ) : groupByCourse ? (
                /* Vista Agrupada por Curso Académico (con Secciones Colapsables) */
                <div className="space-y-4">
                    {courseGroups.map(({ group, problems }) => {
                        const key = `group-${group.id}`;
                        const isExpanded = expandedGroupIds.has(key);

                        return (
                            <div
                                key={group.id}
                                className="rounded-2xl border border-slate-200/70 dark:border-white/10 bg-white/30 dark:bg-graphito-card/15 backdrop-blur-md overflow-hidden transition-all duration-200 hover:border-slate-300 dark:hover:border-white/20 shadow-sm"
                            >
                                <button
                                    type="button"
                                    onClick={() => toggleGroupExpand(key)}
                                    className="w-full flex items-center justify-between gap-4 p-4 sm:p-5 text-left hover:bg-slate-500/5 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-graphito-blue"
                                    aria-expanded={isExpanded}
                                >
                                    <div className="flex items-center gap-3.5 min-w-0">
                                        <span className="shrink-0 px-3 py-1 rounded-xl text-xs font-mono font-bold bg-graphito-blue/15 text-graphito-blue border border-graphito-blue/30">
                                            {group.codigo_grupo}
                                        </span>
                                        <div className="min-w-0">
                                            <h3 className="text-base sm:text-lg font-display font-bold text-slate-900 dark:text-white truncate">
                                                {group.nombre}
                                            </h3>
                                            <p className="text-xs text-slate-500 dark:text-slate-400 truncate">
                                                Periodo: {group.periodo} {group.descripcion && `· ${group.descripcion}`}
                                            </p>
                                        </div>
                                    </div>

                                    <div className="flex items-center gap-3 shrink-0">
                                        <span className="text-xs font-semibold px-2.5 py-1 rounded-lg bg-slate-100 dark:bg-white/5 text-slate-600 dark:text-slate-300">
                                            {problems.length} {problems.length === 1 ? "problema" : "problemas"}
                                        </span>
                                        <div
                                            className={`p-1.5 rounded-lg text-slate-400 dark:text-slate-500 transition-transform duration-200 ${
                                                isExpanded ? "rotate-180 text-graphito-blue" : ""
                                            }`}
                                        >
                                            <ChevronDown size={18} />
                                        </div>
                                    </div>
                                </button>

                                {isExpanded && (
                                    <div className="p-4 sm:p-6 pt-0 border-t border-slate-200/50 dark:border-white/5">
                                        <div className="flex flex-col pt-4">
                                            {problems.map((ref) => renderCard(ref))}
                                        </div>
                                    </div>
                                )}
                            </div>
                        );
                    })}

                    {/* Problemas sin grupo asignado */}
                    {unassignedProblems.length > 0 && (() => {
                        const isExpanded = expandedGroupIds.has("unassigned");

                        return (
                            <div
                                key="unassigned"
                                className="rounded-2xl border border-slate-200/70 dark:border-white/10 bg-white/30 dark:bg-graphito-card/15 backdrop-blur-md overflow-hidden transition-all duration-200 hover:border-slate-300 dark:hover:border-white/20 shadow-sm"
                            >
                                <button
                                    type="button"
                                    onClick={() => toggleGroupExpand("unassigned")}
                                    className="w-full flex items-center justify-between gap-4 p-4 sm:p-5 text-left hover:bg-slate-500/5 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-graphito-blue"
                                    aria-expanded={isExpanded}
                                >
                                    <div className="flex items-center gap-3.5 min-w-0">
                                        <span className="shrink-0 px-3 py-1 rounded-xl text-xs font-mono font-bold bg-slate-500/10 text-slate-600 dark:text-slate-400 border border-slate-500/25">
                                            SIN GRUPO
                                        </span>
                                        <div className="min-w-0">
                                            <h3 className="text-base sm:text-lg font-display font-bold text-slate-900 dark:text-white truncate">
                                                Sin grupo asignado
                                            </h3>
                                            <p className="text-xs text-slate-500 dark:text-slate-400 truncate">
                                                Soluciones de referencia globales no vinculadas a ningún grupo académico específico.
                                            </p>
                                        </div>
                                    </div>

                                    <div className="flex items-center gap-3 shrink-0">
                                        <span className="text-xs font-semibold px-2.5 py-1 rounded-lg bg-slate-100 dark:bg-white/5 text-slate-600 dark:text-slate-300">
                                            {unassignedProblems.length} {unassignedProblems.length === 1 ? "problema" : "problemas"}
                                        </span>
                                        <div
                                            className={`p-1.5 rounded-lg text-slate-400 dark:text-slate-500 transition-transform duration-200 ${
                                                isExpanded ? "rotate-180 text-graphito-blue" : ""
                                            }`}
                                        >
                                            <ChevronDown size={18} />
                                        </div>
                                    </div>
                                </button>

                                {isExpanded && (
                                    <div className="p-4 sm:p-6 pt-0 border-t border-slate-200/50 dark:border-white/5">
                                        <div className="flex flex-col pt-4">
                                            {unassignedProblems.map((ref) => renderCard(ref))}
                                        </div>
                                    </div>
                                )}
                            </div>
                        );
                    })()}
                </div>
            ) : (
                /* Vista de Lista Plana con Paginación */
                <>
                    <div className="flex flex-col">
                        {paginatedReferences.map((ref) => renderCard(ref))}
                    </div>

                    {totalItems > itemsPerPage && (
                        <PaginationControls
                            currentPage={currentPage}
                            totalPages={totalPages}
                            totalItems={totalItems}
                            itemsPerPage={itemsPerPage}
                            onPageChange={setCurrentPage}
                        />
                    )}
                </>
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
                onAssigned={() => {
                    fetchGroups();
                    fetchProblems();
                }}
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
