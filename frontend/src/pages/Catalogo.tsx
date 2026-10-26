import { useState, useEffect, useMemo, useCallback } from "react";
import { Loader2, ChevronDown, FileCode2, Check, Layers } from "lucide-react";
import { SearchBar } from "../components/layout/SearchBar";
import { CatalogProgramModal } from "../components/catalog/CatalogProgramModal";
import { api, CatalogSubject } from "../lib/api";
import { navigate } from "../lib/router";
import { cn } from "../lib/utils";

interface CatalogoProps {
    /** Called after a catalog program was added to the teacher's library. */
    onProgramAdded?: () => void;
    /** Switches the app to the library section. */
    onGoToBiblioteca?: () => void;
}

const languageBadge = {
    c: "bg-graphito-blue/15 text-blue-700 dark:text-graphito-blue border-graphito-blue/30",
    cpp: "bg-graphito-violet/15 text-indigo-700 dark:text-graphito-violet border-graphito-violet/30",
};

const SUBJECT_ORDER: Record<string, number> = {
    "fundamentos_programación": 0,
    "fundamentos_programacion": 0,
    "algoritmos_estructuras_datos": 1,
    "estructuras_de_datos": 1,
    "analisis_diseño_algoritmos": 2,
    "analisis_diseno_algoritmos": 2,
    "programacion_avanzada": 2,
};

function sortSubjects(list: CatalogSubject[]): CatalogSubject[] {
    return [...list].sort((a, b) => {
        const orderA = SUBJECT_ORDER[a.materia] ?? 99;
        const orderB = SUBJECT_ORDER[b.materia] ?? 99;
        return orderA - orderB;
    });
}

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

    // Filter by title, file, topic, unit or subject; drop units and subjects left empty; ordered pedagogically.
    const filteredSubjects = useMemo(() => {
        const term = searchTerm.trim().toLowerCase();
        const base = term
            ? subjects
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
                .filter((subject) => subject.unidades.length > 0)
            : subjects;

        return sortSubjects(base);
    }, [subjects, searchTerm]);

    const toggle = (key: string) => {
        setExpanded((prev) => {
            const next = new Set(prev);
            if (next.has(key)) next.delete(key);
            else next.add(key);
            return next;
        });
    };

    const allKeys = useMemo(() => {
        const keys: string[] = [];
        subjects.forEach((s) => {
            keys.push(s.materia);
            s.unidades.forEach((u) => {
                keys.push(`${s.materia}/${u.unidad}`);
            });
        });
        return keys;
    }, [subjects]);

    const isAllExpanded = expanded.size > 0 && expanded.size >= allKeys.length;

    const toggleAll = () => {
        if (isAllExpanded) {
            setExpanded(new Set());
        } else {
            setExpanded(new Set(allKeys));
        }
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
        navigate("/biblioteca");
        onGoToBiblioteca?.();
    };

    const isSearching = searchTerm.trim().length > 0;

    return (
        <main id="main-content" className="max-w-7xl mx-auto p-4 sm:p-6 lg:p-8 flex-1 w-full flex flex-col transition-colors duration-200" tabIndex={-1}>
            <div className="mb-8">
                <h2 className="text-3xl font-display font-black text-slate-900 dark:text-white transition-colors">
                    Catálogo de Programas
                </h2>
                <p className="text-slate-600 dark:text-slate-300 font-body mt-2 transition-colors">
                    Programas de C/C++ organizados por materia y unidad. Agrega los que necesites a tu biblioteca para usarlos como solución de referencia.
                </p>
            </div>

            <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-4 mb-6">
                <div className="flex-1">
                    <SearchBar
                        searchTerm={searchTerm}
                        onSearchChange={setSearchTerm}
                        placeholder="Buscar por programa, tema, unidad o materia..."
                    />
                </div>
                <button
                    type="button"
                    onClick={toggleAll}
                    className="shrink-0 flex items-center justify-center gap-2 px-4 py-3 min-h-[44px] rounded-xl text-xs font-bold border border-slate-200 dark:border-graphito-border bg-white dark:bg-graphito-card text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-graphito-dark transition-all duration-200 shadow-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-graphito-blue active:scale-95"
                >
                    <Layers size={15} className="text-graphito-blue" />
                    <span>{isAllExpanded ? "Colapsar todo" : "Expandir todo"}</span>
                </button>
            </div>

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
                <div className="flex flex-col items-center justify-center py-20 border border-dashed border-slate-300 dark:border-graphito-subtle rounded-2xl p-8 text-center my-4 bg-white/60 dark:bg-graphito-surface/20 transition-colors">
                    <p className="text-slate-800 dark:text-slate-200 font-bold text-lg mb-1">
                        {isSearching ? "Sin resultados para tu búsqueda" : "El catálogo está vacío"}
                    </p>
                    <p className="text-slate-600 dark:text-slate-400 text-sm max-w-md">
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
                            <section
                                key={subject.materia}
                                aria-label={subject.materia_nombre}
                                className="bg-white/20 dark:bg-graphito-card/15 backdrop-blur-[3px] p-4 sm:p-5 rounded-2xl border border-slate-200/60 dark:border-white/15 transition-colors shadow-sm shadow-[inset_0_1px_0_0_rgba(255,255,255,0.08)]"
                            >
                                <button
                                    type="button"
                                    onClick={() => toggle(subject.materia)}
                                    aria-expanded={isSubjectOpen}
                                    className="w-full flex items-center justify-between gap-3 min-h-[44px] text-left rounded-xl p-2 -m-2 hover:bg-slate-100/60 dark:hover:bg-graphito-dark/50 focus:outline-none focus-visible:ring-2 focus-visible:ring-graphito-blue transition-colors group"
                                >
                                    <span className="flex items-center gap-3 flex-wrap">
                                        <span className="text-xl sm:text-2xl font-display font-bold text-slate-900 dark:text-white tracking-tight group-hover:text-graphito-blue transition-colors">
                                            {subject.materia_nombre}
                                        </span>
                                        <span className="text-xs font-bold px-2.5 py-0.5 rounded-full bg-graphito-blue/10 text-graphito-blue border border-graphito-blue/20">
                                            {subject.total} {subject.total === 1 ? "programa" : "programas"}
                                        </span>
                                    </span>
                                    <div className="flex items-center gap-2 text-slate-600 dark:text-slate-300 group-hover:text-graphito-blue transition-colors">
                                        <span className="text-xs font-semibold hidden sm:inline">
                                            {isSubjectOpen ? "Colapsar" : "Expandir"}
                                        </span>
                                        <ChevronDown
                                            size={20}
                                            className={cn(
                                                "transition-transform duration-300 ease-[cubic-bezier(0.16,1,0.3,1)]",
                                                isSubjectOpen && "rotate-180"
                                            )}
                                        />
                                    </div>
                                </button>

                                <div
                                    className={cn(
                                        "grid transition-all duration-300 ease-[cubic-bezier(0.16,1,0.3,1)]",
                                        isSubjectOpen ? "grid-rows-[1fr] opacity-100 mt-4" : "grid-rows-[0fr] opacity-0 mt-0 pointer-events-none"
                                    )}
                                >
                                    <div className="overflow-hidden">
                                        <div className="flex flex-col gap-4">
                                            {subject.unidades.map((unit) => {
                                                const key = `${subject.materia}/${unit.unidad}`;
                                                const isOpen = isSearching || expanded.has(key);
                                                return (
                                                    <div
                                                        key={key}
                                                        className={cn(
                                                            "bg-white/25 dark:bg-graphito-card/15 backdrop-blur-[3px] border rounded-2xl overflow-hidden transition-all duration-200 shadow-[inset_0_1px_0_0_rgba(255,255,255,0.08)]",
                                                            isOpen
                                                                ? "border-graphito-blue/40 shadow-md shadow-graphito-blue/5 dark:border-graphito-blue/30"
                                                                : "border-slate-200/60 dark:border-white/10 hover:border-slate-300 dark:hover:border-graphito-subtle"
                                                        )}
                                                    >
                                                        <button
                                                            type="button"
                                                            onClick={() => toggle(key)}
                                                            aria-expanded={isOpen}
                                                            className="w-full flex items-center justify-between gap-3 px-6 py-4 min-h-[48px] text-left hover:bg-slate-50 dark:hover:bg-graphito-dark/40 focus:outline-none focus-visible:ring-2 focus-visible:ring-graphito-blue transition-colors group"
                                                        >
                                                            <span className="font-display font-bold text-sm text-slate-800 dark:text-white flex items-center gap-2">
                                                                <span>{unit.unidad_nombre}</span>
                                                                <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-slate-100 dark:bg-graphito-surface text-slate-600 dark:text-slate-300 border border-slate-200 dark:border-graphito-border">
                                                                    {unit.programas.length} {unit.programas.length === 1 ? "programa" : "programas"}
                                                                </span>
                                                            </span>
                                                            <div className="flex items-center gap-2">
                                                                <span className="text-xs font-medium text-slate-600 dark:text-slate-300 group-hover:text-graphito-blue transition-colors">
                                                                    {isOpen ? "Ocultar" : "Ver programas"}
                                                                </span>
                                                                <ChevronDown
                                                                    size={16}
                                                                    className={cn(
                                                                        "text-slate-600 dark:text-slate-300 group-hover:text-graphito-blue transition-transform duration-300 ease-[cubic-bezier(0.16,1,0.3,1)]",
                                                                        isOpen && "rotate-180"
                                                                    )}
                                                                />
                                                            </div>
                                                        </button>

                                                        <div
                                                            className={cn(
                                                                "grid transition-all duration-300 ease-[cubic-bezier(0.16,1,0.3,1)]",
                                                                isOpen ? "grid-rows-[1fr] opacity-100" : "grid-rows-[0fr] opacity-0 pointer-events-none"
                                                            )}
                                                        >
                                                            <div className="overflow-hidden">
                                                                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3.5 px-6 pb-6 pt-2 border-t border-slate-100 dark:border-graphito-border/50">
                                                                    {unit.programas.map((program) => (
                                                                        <button
                                                                            key={program.id}
                                                                            type="button"
                                                                            onClick={() => openProgram(program.id)}
                                                                            className="group/card text-left p-4 rounded-xl border border-slate-200/60 dark:border-white/10 bg-slate-50/30 dark:bg-graphito-dark/20 backdrop-blur-[2px] hover:bg-white/60 dark:hover:bg-graphito-card/40 hover:border-graphito-blue/50 hover:shadow-lg hover:shadow-graphito-blue/10 hover:-translate-y-0.5 active:scale-[0.98] focus:outline-none focus-visible:ring-2 focus-visible:ring-graphito-blue transition-all duration-200 min-h-[48px] flex flex-col justify-between"
                                                                        >
                                                                            <div>
                                                                                <div className="flex items-start justify-between gap-3">
                                                                                    <h4 className="font-display font-bold text-sm text-slate-900 dark:text-white leading-snug group-hover/card:text-graphito-blue transition-colors">
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
                                                                                    <p className="mt-1 text-xs text-slate-600 dark:text-slate-300 line-clamp-2">
                                                                                        {program.tema}
                                                                                    </p>
                                                                                )}
                                                                            </div>

                                                                            <div className="mt-3 pt-2.5 border-t border-slate-200/50 dark:border-graphito-border/40 flex items-center justify-between gap-2">
                                                                                <p className="flex items-center gap-1.5 text-xs text-slate-600 dark:text-slate-300 font-mono truncate">
                                                                                    <FileCode2 size={13} className="shrink-0 text-graphito-blue" />
                                                                                    <span className="truncate">{program.nombre_archivo}</span>
                                                                                </p>
                                                                                {addedIds.has(program.id) ? (
                                                                                    <span className="shrink-0 inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold border bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border-emerald-500/20">
                                                                                        <Check size={11} />
                                                                                        En tu biblioteca
                                                                                    </span>
                                                                                ) : (
                                                                                    <span className="shrink-0 text-[10px] font-semibold text-graphito-blue opacity-0 group-hover/card:opacity-100 transition-opacity">
                                                                                        Ver código →
                                                                                    </span>
                                                                                )}
                                                                            </div>
                                                                        </button>
                                                                    ))}
                                                                </div>
                                                            </div>
                                                        </div>
                                                    </div>
                                                );
                                            })}
                                        </div>
                                    </div>
                                </div>
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
