import { useEffect, useMemo, useState } from "react";
import { ArrowLeft, ChevronRight, Loader2, UserRound } from "lucide-react";
import { SearchBar } from "../components/layout/SearchBar";
import { api } from "../lib/api";
import type { ComparisonView } from "../lib/dictamen";
import { formatPct } from "../lib/dictamen";
import { navigate, useRouteMatch } from "../lib/router";
import { groupStudents, normalizeName, searchStudents, type Student } from "../lib/students";

const formatDate = (iso: string) =>
    new Date(iso).toLocaleDateString("es-MX", { day: "2-digit", month: "short", year: "numeric" });

export function Estudiantes({
    onOpenReport,
}: {
    onOpenReport: (comparison: ComparisonView, all: ComparisonView[]) => void;
}) {
    const [students, setStudents] = useState<Student[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [loadFailed, setLoadFailed] = useState(false);
    const [query, setQuery] = useState("");
    const route = useRouteMatch("/estudiantes/:nombre");

    useEffect(() => {
        let cancelled = false;
        Promise.all([api.problems.list(true, true), api.groups.list(true).catch(() => [])])
            .then(([problems, groups]) => !cancelled && setStudents(groupStudents(problems, groups)))
            .catch(() => !cancelled && setLoadFailed(true))
            .finally(() => !cancelled && setIsLoading(false));
        return () => {
            cancelled = true;
        };
    }, []);

    const selected = route.isMatch ? students.find((s) => s.key === normalizeName(route.params.nombre)) : undefined;
    const matches = useMemo(() => searchStudents(students, query), [students, query]);
    const openStudent = (name: string) => navigate(`/estudiantes/${encodeURIComponent(name)}`);

    return (
        <main id="main-content" className="max-w-7xl mx-auto p-4 sm:p-6 lg:p-8 flex-1 w-full flex flex-col" tabIndex={-1}>
            <h1 className="text-3xl font-display font-black text-slate-900 dark:text-white">Estudiantes</h1>
            <p className="text-slate-600 dark:text-slate-300 font-body mt-2 mb-6">
                Busca a un estudiante para ver todas sus entregas con sus métricas.
            </p>

            {isLoading ? (
                <div className="flex items-center gap-2 text-slate-600 dark:text-slate-300 text-sm">
                    <Loader2 className="animate-spin" size={16} /> Cargando estudiantes...
                </div>
            ) : loadFailed ? (
                <p className="text-sm text-slate-600 dark:text-slate-300">No se pudieron cargar los estudiantes.</p>
            ) : route.isMatch ? (
                <StudentHistory student={selected} name={route.params.nombre} onOpenReport={onOpenReport} />
            ) : (
                <>
                    <SearchBar searchTerm={query} onSearchChange={setQuery} placeholder="Buscar estudiante por nombre..." className="mb-4" />
                    {matches.length === 0 ? (
                        <p className="text-sm text-slate-600 dark:text-slate-300">No hay estudiantes que coincidan.</p>
                    ) : (
                        <ul className="space-y-2">
                            {matches.map((s) => (
                                <li key={s.key}>
                                    <button
                                        type="button"
                                        onClick={() => openStudent(s.name)}
                                        className="w-full flex items-center justify-between gap-3 p-3 px-4 rounded-xl border border-slate-200/80 dark:border-white/[0.06] bg-white/40 hover:bg-white/90 dark:bg-graphito-dark/30 dark:hover:bg-graphito-dark/60 transition-colors text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-graphito-blue"
                                    >
                                        <span className="flex items-center gap-3 min-w-0">
                                            <UserRound size={16} className="text-slate-500 shrink-0" aria-hidden="true" />
                                            <span className="text-sm font-semibold text-slate-800 dark:text-slate-200 truncate">{s.name}</span>
                                        </span>
                                        <span className="flex items-center gap-2 shrink-0 text-xs text-slate-500 dark:text-slate-400">
                                            {s.tasks.length} {s.tasks.length === 1 ? "entrega" : "entregas"}
                                            <ChevronRight size={14} aria-hidden="true" />
                                        </span>
                                    </button>
                                </li>
                            ))}
                        </ul>
                    )}
                </>
            )}
        </main>
    );
}

function StudentHistory({
    student,
    name,
    onOpenReport,
}: {
    student?: Student;
    name: string;
    onOpenReport: (comparison: ComparisonView, all: ComparisonView[]) => void;
}) {
    const reports = (student?.tasks ?? []).flatMap((t) => (t.comparison ? [t.comparison] : []));
    return (
        <div>
            <button
                type="button"
                onClick={() => navigate("/estudiantes")}
                className="flex items-center gap-1.5 mb-4 text-sm font-semibold text-slate-700 dark:text-slate-200 hover:text-graphito-blue focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-graphito-blue rounded-md"
            >
                <ArrowLeft size={16} aria-hidden="true" /> Todos los estudiantes
            </button>
            <h2 className="text-2xl font-display font-black text-slate-900 dark:text-white mb-4 break-words">
                {student?.name ?? name}
            </h2>
            {!student ? (
                <p className="text-sm text-slate-600 dark:text-slate-300">Este estudiante no tiene entregas.</p>
            ) : (
                <div className="overflow-x-auto rounded-xl border border-slate-200/80 dark:border-white/[0.06]">
                    <table className="w-full text-sm text-left">
                        <thead className="text-[11px] uppercase tracking-wider text-slate-500 dark:text-slate-400">
                            <tr>
                                {["Tarea", "Grupo", "Lenguaje", "Fecha", "Similitud lógica", "Similitud léxica", "Estilo IA"].map((h) => (
                                    <th key={h} scope="col" className="px-4 py-3 font-semibold whitespace-nowrap">{h}</th>
                                ))}
                            </tr>
                        </thead>
                        <tbody>
                            {student.tasks.map((t, i) => {
                                const c = t.comparison;
                                const open = c ? () => onOpenReport(c, reports) : undefined;
                                return (
                                    <tr
                                        key={`${t.problemId}-${i}`}
                                        onClick={open}
                                        className={`border-t border-slate-200/60 dark:border-white/[0.06] ${c ? "cursor-pointer hover:bg-white/60 dark:hover:bg-graphito-dark/50" : ""}`}
                                    >
                                        <td className="px-4 py-3 font-semibold text-slate-800 dark:text-slate-200">
                                            {c ? (
                                                <button type="button" onClick={(e) => { e.stopPropagation(); open?.(); }} className="text-left hover:text-graphito-blue focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-graphito-blue rounded-sm">
                                                    {t.problemTitle}
                                                </button>
                                            ) : (
                                                t.problemTitle
                                            )}
                                        </td>
                                        <td className="px-4 py-3 text-slate-600 dark:text-slate-300">{t.groupName ?? "—"}</td>
                                        <td className="px-4 py-3 text-slate-600 dark:text-slate-300 uppercase">{t.lenguaje}</td>
                                        <td className="px-4 py-3 text-slate-600 dark:text-slate-300 whitespace-nowrap">{formatDate(t.date)}</td>
                                        {c ? (
                                            <>
                                                <td className="px-4 py-3 font-mono">{c.similarity == null ? "—" : `${c.similarity}%`}</td>
                                                <td className="px-4 py-3 font-mono">{formatPct(c.similitud_semantica)}</td>
                                                <td className="px-4 py-3 font-mono">{formatPct(c.probabilidad_ia)}</td>
                                            </>
                                        ) : (
                                            <td colSpan={3} className="px-4 py-3 text-slate-500 dark:text-slate-400">Sin análisis</td>
                                        )}
                                    </tr>
                                );
                            })}
                        </tbody>
                    </table>
                </div>
            )}
        </div>
    );
}
