import { useState, useEffect, useMemo, useCallback } from "react";
import { Loader2, ChevronDown, FileCode2, Check } from "lucide-react";
import { SearchBar } from "../components/layout/SearchBar";
import { CatalogProgramModal } from "../components/catalog/CatalogProgramModal";
import { api, CatalogSubject } from "../lib/api";
import { cn } from "../lib/utils";

interface CatalogoProps {
    /** Called after a catalog program was added to the teacher's library. */
    onProgramAdded?: () => void;
    /** Switches the app to the library section. */
    onGoToBiblioteca?: () => void;
}

const languageBadge = {
    c: "bg-graphito-blue/10 text-graphito-blue border-graphito-blue/20",
    cpp: "bg-graphito-violet/10 text-graphito-violet border-graphito-violet/20",
};

export function Catalogo({ onProgramAdded, onGoToBiblioteca }: CatalogoProps) {
    const [subjects, setSubjects] = useState<CatalogSubject[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [searchTerm, setSearchTerm] = useState("");
    // Everything starts collapsed; keys are "subject" or "subject/unit".
    const [expanded, setExpanded] = useState<Set<string>>(new Set());
    const [addedIds, setAddedIds] = useState<Set<string>>(new Set());
    const [selectedProgramId, setSelectedProgramId] = useState<string | null>(null);
    const [isModalOpen, setIsModalOpen] = useState(false);

    useEffect(() => {
        let cancelled = false;
        api.catalog
            .list()
            .then((res) => {
                if (!cancelled) setSubjects(res);
            })
            .catch((err: any) => {
                if (!cancelled) setError(err.message || "No se pudo cargar el catálogo.");
            })
            .finally(() => {
                if (!cancelled) setIsLoading(false);
            });
        return () => {
            cancelled = true;
        };
    }, []);

    // Programs already adopted by the teacher; a failure here must not break the catalog.
    const loadAdded = useCallback(async () => {
        try {
            const problems = await api.problems.list();
            const ids = problems.map((p) => p.catalogo_id).filter((id): id is string => !!id);
            setAddedIds(new Set(ids));
        } catch {
            setAddedIds(new Set());
        }
    }, []);

    useEffect(() => {
        loadAdded();
    }, [loadAdded]);

    // Filter by title, file, topic, unit or subject; drop units and subjects left empty.
    const filteredSubjects = useMemo(() => {
        const term = searchTerm.trim().toLowerCase();
        if (!term) return subjects;
        return subjects
            .map((subject) => {
                const subjectMatch = subject.materia_nombre.toLowerCase().includes(term);
                const unidades = subject.unidades
                    .map((unit) => {
                        if (subjectMatch || unit.unidad_nombre.toLowerCase().includes(term)) return unit;
                        return {
                            ...unit,
                            programas: unit.programas.filter(
                                (p) =>
                                    p.titulo.toLowerCase().includes(term) ||
                                    p.nombre_archivo.toLowerCase().includes(term) ||
                                    (p.tema ?? "").toLowerCase().includes(term)
                            ),
                        };
                    })
                    .filter((unit) => unit.programas.length > 0);
                const total = unidades.reduce((acc, u) => acc + u.programas.length, 0);
                return { ...subject, unidades, total };
            })
            .filter((subject) => subject.unidades.length > 0);
    }, [subjects, searchTerm]);

    const toggle = (key: string) => {
        setExpanded((prev) => {
            const next = new Set(prev);
            if (next.has(key)) next.delete(key);
            else next.add(key);
            return next;
        });
    };

    const openProgram = (id: string) => {
        setSelectedProgramId(id);
        setIsModalOpen(true);
    };

    const handleAdded = () => {
        loadAdded();
        onProgramAdded?.();
    };

    const handleGoToBiblioteca = () => {
        setIsModalOpen(false);
        onGoToBiblioteca?.();
    };

    const isSearching = searchTerm.trim().length > 0;

    return (
        <main id="main-content" className="max-w-7xl mx-auto p-8 flex-1 w-full flex flex-col transition-colors duration-200" tabIndex={-1}>
            <div className="mb-8">
                <h2 className="text-3xl font-display font-black text-slate-900 dark:text-white transition-colors">
                    Catálogo de Programas
                </h2>
                <p className="text-slate-600 dark:text-slate-400 font-body mt-2 transition-colors">
                    Programas de C/C++ organizados por materia y unidad. Agrega los que necesites a tu biblioteca para usarlos como solución de referencia.
                </p>
            </div>

            <SearchBar
                searchTerm={searchTerm}
                onSearchChange={setSearchTerm}
                placeholder="Buscar por programa, tema, unidad o materia..."
            />

            {isLoading ? (
                <div className="flex flex-col items-center justify-center py-20 text-slate-500 dark:text-slate-400">
                    <Loader2 className="w-8 h-8 animate-spin text-graphito-blue mb-3" />
                    <p className="text-sm font-medium">Cargando catálogo...</p>
                </div>
            ) : error ? (
                <div className="p-4 bg-red-500/10 border border-red-500/30 rounded-xl text-red-600 dark:text-red-300 text-sm font-medium">
                    {error}
                </div>
            ) : filteredSubjects.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-20 border border-dashed border-slate-300 dark:border-[#2b3346] rounded-2xl p-8 text-center my-4 bg-white/60 dark:bg-[#121827]/20 transition-colors">
                    <p className="text-slate-800 dark:text-slate-300 font-bold text-lg mb-1">
                        {isSearching ? "Sin resultados para tu búsqueda" : "El catálogo está vacío"}
                    </p>
                    <p className="text-slate-600 dark:text-slate-500 text-sm max-w-md">
                        {isSearching
                            ? "Prueba con otro título, tema, unidad o materia."
                            : "Aún no hay programas disponibles en el catálogo."}
                    </p>
                </div>
            ) : (
                <div className="flex flex-col gap-6">
                    {filteredSubjects.map((subject) => {
                        // While searching, matches are always shown; manual toggles are kept for when the search clears.
                        const isSubjectOpen = isSearching || expanded.has(subject.materia);
                        return (
                            <section key={subject.materia} aria-label={subject.materia_nombre}>
                                <button
                                    type="button"
                                    onClick={() => toggle(subject.materia)}
                                    aria-expanded={isSubjectOpen}
                                    className="w-full flex items-center justify-between gap-3 mb-4 text-left rounded-lg focus:outline-none focus-visible:ring-2 focus-visible:ring-graphito-blue/50"
                                >
                                    <span className="flex items-baseline gap-3">
                                        <span className="text-xl font-display font-bold text-slate-900 dark:text-white tracking-tight">
                                            {subject.materia_nombre}
                                        </span>
                                        <span className="text-xs font-semibold text-slate-500 dark:text-slate-400">
                                            {subject.total} {subject.total === 1 ? "programa" : "programas"}
                                        </span>
                                    </span>
                                    <ChevronDown
                                        size={18}
                                        className={cn("text-slate-400 transition-transform", isSubjectOpen && "rotate-180")}
                                    />
                                </button>

                                {isSubjectOpen && (
                                    <div className="flex flex-col gap-4">
                                        {subject.unidades.map((unit) => {
                                            const key = `${subject.materia}/${unit.unidad}`;
                                            const isOpen = isSearching || expanded.has(key);
                                            return (
                                                <div
                                                    key={key}
                                                    className="bg-white dark:bg-graphito-card border border-slate-200 dark:border-graphito-border rounded-2xl overflow-hidden"
                                                >
                                                    <button
                                                        type="button"
                                                        onClick={() => toggle(key)}
                                                        aria-expanded={isOpen}
                                                        className="w-full flex items-center justify-between gap-3 px-6 py-4 text-left hover:bg-slate-50 dark:hover:bg-graphito-dark/40 focus:outline-none focus-visible:ring-2 focus-visible:ring-graphito-blue/50 transition-colors"
                                                    >
                                                        <span className="font-display font-bold text-sm text-slate-800 dark:text-white">
                                                            {unit.unidad_nombre}
                                                            <span className="ml-2 text-xs font-medium text-slate-500 dark:text-slate-400">
                                                                ({unit.programas.length})
                                                            </span>
                                                        </span>
                                                        <ChevronDown
                                                            size={16}
                                                            className={cn(
                                                                "text-slate-400 transition-transform",
                                                                isOpen && "rotate-180"
                                                            )}
                                                        />
                                                    </button>

                                                    {isOpen && (
                                                        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3 px-6 pb-6">
                                                            {unit.programas.map((program) => (
                                                                <button
                                                                    key={program.id}
                                                                    type="button"
                                                                    onClick={() => openProgram(program.id)}
                                                                    className="text-left p-4 rounded-xl border border-slate-200 dark:border-graphito-border bg-slate-50/60 dark:bg-graphito-dark/40 hover:border-graphito-blue/40 hover:shadow-lg hover:shadow-graphito-blue/5 active:scale-[0.99] focus:outline-none focus-visible:ring-2 focus-visible:ring-graphito-blue/50 transition-all"
                                                                >
                                                                    <div className="flex items-start justify-between gap-3">
                                                                        <h4 className="font-display font-bold text-sm text-slate-900 dark:text-white leading-snug">
                                                                            {program.titulo}
                                                                        </h4>
                                                                        <span
                                                                            className={cn(
                                                                                "shrink-0 px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-widest border",
                                                                                program.lenguaje === "cpp" ? languageBadge.cpp : languageBadge.c
                                                                            )}
                                                                        >
                                                                            {program.lenguaje === "cpp" ? "C++" : "C"}
                                                                        </span>
                                                                    </div>
                                                                    {program.tema && (
                                                                        <p className="mt-1 text-xs text-slate-500 dark:text-slate-400 line-clamp-2">
                                                                            {program.tema}
                                                                        </p>
                                                                    )}
                                                                    <div className="mt-2 flex items-center justify-between gap-2">
                                                                        <p className="flex items-center gap-1.5 text-xs text-slate-500 dark:text-slate-400 font-mono truncate">
                                                                            <FileCode2 size={13} className="shrink-0" />
                                                                            <span className="truncate">{program.nombre_archivo}</span>
                                                                        </p>
                                                                        {addedIds.has(program.id) && (
                                                                            <span className="shrink-0 inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold border bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20">
                                                                                <Check size={11} />
                                                                                En tu biblioteca
                                                                            </span>
                                                                        )}
                                                                    </div>
                                                                </button>
                                                            ))}
                                                        </div>
                                                    )}
                                                </div>
                                            );
                                        })}
                                    </div>
                                )}
                            </section>
                        );
                    })}
                </div>
            )}

            <CatalogProgramModal
                isOpen={isModalOpen}
                programId={selectedProgramId}
                alreadyAdded={selectedProgramId !== null && addedIds.has(selectedProgramId)}
                onClose={() => setIsModalOpen(false)}
                onAdded={handleAdded}
                onGoToBiblioteca={handleGoToBiblioteca}
            />
        </main>
    );
}
