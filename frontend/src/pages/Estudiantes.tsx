import { useEffect, useMemo, useState } from "react";
import { ArrowLeft, ChevronRight, Loader2, Users } from "lucide-react";
import { SearchBar } from "../components/layout/SearchBar";
import { api } from "../lib/api";
import type { ComparisonView } from "../lib/dictamen";
import { formatPct } from "../lib/dictamen";
import { navigate, useRouteMatch } from "../lib/router";
import { groupStudents, normalizeName, searchStudents, type Student, type StudentTask } from "../lib/students";
import { cn } from "../lib/utils";

type OpenReport = (comparison: ComparisonView, all: ComparisonView[]) => void;

// Same glass surface and language badges as the library cards.
const GLASS = "bg-white/25 dark:bg-graphito-card/15 backdrop-blur-[3px] border border-slate-200/60 dark:border-white/15 rounded-2xl shadow-sm";
const GLASS_HOVER = "transition-all duration-200 hover:shadow-xl hover:shadow-graphito-blue/5 hover:border-graphito-blue/40 dark:hover:border-graphito-blue/40";
const FOCUS = "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-graphito-blue";
const LANG_BADGE = {
    c: "bg-blue-500/10 text-blue-600 dark:text-blue-400 border-blue-500/30",
    cpp: "bg-pink-500/10 text-pink-600 dark:text-pink-400 border-pink-500/30",
};

const formatDate = (iso: string) =>
    new Date(iso).toLocaleDateString("es-MX", { day: "2-digit", month: "short", year: "numeric" });

const countLabel = (n: number) => `${n} ${n === 1 ? "entrega" : "entregas"}`;

function Avatar({ name, size }: { name: string; size: "md" | "lg" }) {
    return (
        <span
            aria-hidden="true"
            className={cn(
                "shrink-0 rounded-full bg-gradient-to-tr from-slate-700 to-slate-500 flex items-center justify-center text-white font-bold",
                size === "lg" ? "w-14 h-14 text-xl" : "w-10 h-10"
            )}
        >
            {name.charAt(0).toUpperCase()}
        </span>
    );
}

export function Estudiantes({ onOpenReport }: { onOpenReport: OpenReport }) {
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

    return (
        <main id="main-content" className="max-w-7xl mx-auto p-4 sm:p-6 lg:p-8 flex-1 w-full flex flex-col transition-colors duration-200" tabIndex={-1}>
            <div className="mb-8">
                <h1 className="text-3xl font-display font-black text-slate-900 dark:text-white transition-colors">Estudiantes</h1>
                <p className="text-slate-600 dark:text-slate-300 font-body mt-2 transition-colors">
                    Busca a un estudiante para ver todas sus entregas con sus métricas.
                </p>
            </div>

            {isLoading ? (
                <div className="flex items-center justify-center gap-2 py-16 text-slate-600 dark:text-slate-300 text-sm" role="status">
                    <Loader2 className="animate-spin text-graphito-blue" size={18} /> Cargando estudiantes...
                </div>
            ) : loadFailed ? (
                <p className={cn(GLASS, "p-6 text-sm text-slate-600 dark:text-slate-300")}>No se pudieron cargar los estudiantes.</p>
            ) : route.isMatch ? (
                <StudentHistory student={selected} name={route.params.nombre} onOpenReport={onOpenReport} />
            ) : (
                <>
                    <SearchBar searchTerm={query} onSearchChange={setQuery} placeholder="Buscar estudiante por nombre..." className="mb-6" />
                    {matches.length === 0 ? (
                        <p className={cn(GLASS, "p-6 text-center text-sm text-slate-600 dark:text-slate-300")}>No hay estudiantes que coincidan.</p>
                    ) : (
                        <ul className="space-y-3">
                            {matches.map((s) => (
                                <li key={s.key}>
                                    <button
                                        type="button"
                                        onClick={() => navigate(`/estudiantes/${encodeURIComponent(s.name)}`)}
                                        className={cn(GLASS, GLASS_HOVER, FOCUS, "group w-full flex items-center justify-between gap-4 p-4 sm:p-5 text-left")}
                                    >
                                        <span className="flex items-center gap-3.5 min-w-0">
                                            <Avatar name={s.name} size="md" />
                                            <span className="text-base sm:text-lg font-display font-bold text-slate-900 dark:text-white truncate">{s.name}</span>
                                        </span>
                                        <span className="flex items-center gap-3 shrink-0">
                                            <span className="text-xs font-semibold px-2.5 py-1 rounded-lg bg-slate-100 dark:bg-white/5 text-slate-600 dark:text-slate-300">
                                                {countLabel(s.tasks.length)}
                                            </span>
                                            <ChevronRight size={18} className="text-slate-400 group-hover:text-graphito-blue transition-colors" aria-hidden="true" />
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

function Metric({ label, value }: { label: string; value: string }) {
    return (
        <div className="flex flex-col items-end">
            <span className="text-[10px] font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">{label}</span>
            <span className="text-sm font-black font-mono text-slate-700 dark:text-slate-200">{value}</span>
        </div>
    );
}

function TaskRow({ task, onOpen }: { task: StudentTask; onOpen?: () => void }) {
    const c = task.comparison;
    const body = (
        <>
            <div className="min-w-0 space-y-2">
                <h3 className="text-base sm:text-lg font-display font-bold text-slate-900 dark:text-white tracking-tight truncate" title={task.problemTitle}>
                    {task.problemTitle}
                </h3>
                <div className="flex flex-wrap items-center gap-2">
                    <span
                        className={cn(
                            "px-2.5 py-0.5 rounded-md text-[10px] font-black uppercase tracking-wider border shrink-0",
                            task.lenguaje === "cpp" ? LANG_BADGE.cpp : LANG_BADGE.c
                        )}
                    >
                        {task.lenguaje}
                    </span>
                    {task.groupCode && (
                        <span
                            className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-md text-[10px] font-bold bg-graphito-blue/10 text-graphito-blue dark:text-cyan-300 border border-graphito-blue/25 shrink-0"
                            title={task.groupName ? `Grupo: ${task.groupName}` : undefined}
                        >
                            <Users size={11} aria-hidden="true" />
                            {task.groupCode}
                        </span>
                    )}
                    <span className="text-xs text-slate-500 dark:text-slate-400">{formatDate(task.date)}</span>
                </div>
            </div>
            <div className="flex items-center gap-4 sm:gap-6 shrink-0">
                {c ? (
                    <>
                        <Metric label="Sim. lógica" value={c.similarity == null ? "—" : `${c.similarity}%`} />
                        <Metric label="Sim. léxica" value={formatPct(c.similitud_semantica)} />
                        <Metric label="Estilo IA" value={formatPct(c.probabilidad_ia)} />
                        <ChevronRight size={18} className="text-slate-400 group-hover:text-graphito-blue transition-colors" aria-hidden="true" />
                    </>
                ) : (
                    <span className="text-xs font-semibold px-2.5 py-1 rounded-lg bg-slate-100 dark:bg-white/5 text-slate-500 dark:text-slate-400">Sin análisis</span>
                )}
            </div>
        </>
    );
    const layout = "w-full flex flex-col sm:flex-row sm:items-center justify-between gap-3 sm:gap-4 p-4 sm:p-5 text-left";
    return onOpen ? (
        <button type="button" onClick={onOpen} className={cn(GLASS, GLASS_HOVER, FOCUS, "group", layout)}>
            {body}
        </button>
    ) : (
        <div className={cn(GLASS, layout)}>{body}</div>
    );
}

function StudentHistory({ student, name, onOpenReport }: { student?: Student; name: string; onOpenReport: OpenReport }) {
    const reports = (student?.tasks ?? []).flatMap((t) => (t.comparison ? [t.comparison] : []));
    return (
        <div>
            <button
                type="button"
                onClick={() => navigate("/estudiantes")}
                className={cn("flex items-center gap-1.5 px-3 py-2 -ml-3 mb-4 min-h-[44px] rounded-xl text-sm font-semibold text-slate-700 dark:text-slate-200 hover:bg-slate-200/60 dark:hover:bg-slate-800/80 active:scale-95 transition-all", FOCUS)}
            >
                <ArrowLeft size={16} aria-hidden="true" /> Todos los estudiantes
            </button>
            <div className={cn(GLASS, "flex items-center gap-4 p-4 sm:p-5 mb-6")}>
                <Avatar name={student?.name ?? name} size="lg" />
                <div className="min-w-0">
                    <h2 className="text-2xl font-display font-black text-slate-900 dark:text-white tracking-tight break-words">{student?.name ?? name}</h2>
                    <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">{countLabel(student?.tasks.length ?? 0)}</p>
                </div>
            </div>
            {!student ? (
                <p className={cn(GLASS, "p-6 text-center text-sm text-slate-600 dark:text-slate-300")}>Este estudiante no tiene entregas.</p>
            ) : (
                <div className="space-y-3">
                    {student.tasks.map((t, i) => (
                        <TaskRow key={`${t.problemId}-${i}`} task={t} onOpen={t.comparison ? () => onOpenReport(t.comparison!, reports) : undefined} />
                    ))}
                </div>
            )}
        </div>
    );
}
