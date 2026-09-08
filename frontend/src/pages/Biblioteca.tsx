import { useState, useEffect } from "react";
import { ReferenceCard } from "../components/layout/ReferenceCard";
import { PaginationControls } from "../components/ui/PaginationControls";
import { SearchBar } from "../components/layout/SearchBar";
import { api, Problema } from "../lib/api";
import { Loader2 } from "lucide-react";

interface Comparison {
    id: string;
    title: string;
    subtitle: string;
    similarity: number;
}

interface Reference {
    id: string;
    title: string;
    category: string;
    categoryColor: string;
    description: string;
    updatedAt: string;
    activeComparisons: number;
    comparisons: Comparison[];
}

export function Biblioteca({
    onCompare,
    onComparisonClick
}: {
    onCompare?: () => void,
    onComparisonClick?: (comparison: Comparison) => void
}) {
    const [currentPage, setCurrentPage] = useState(1);
    const [searchTerm, setSearchTerm] = useState("");
    const [references, setReferences] = useState<Reference[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const itemsPerPage = 10;

    useEffect(() => {
        const fetchProblems = async () => {
            setIsLoading(true);
            try {
                const problems = await api.problems.list();
                if (problems && problems.length > 0) {
                    const mapped = await Promise.all(
                        problems.map(async (p) => {
                            let subs: any[] = [];
                            try {
                                subs = await api.problems.listSubmissions(p.id);
                            } catch {
                                // ok
                            }
                            return {
                                id: String(p.id),
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
                                comparisons: subs.map((s, idx) => ({
                                    id: String(s.id),
                                    title: `${s.autor}`,
                                    subtitle: `Entrega #${idx + 1} (${s.lenguaje})`,
                                    similarity: 0,
                                })),
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

        fetchProblems();
    }, []);

    // Filtrar referencias según el término de búsqueda
    const filteredReferences = references.filter((ref) => {
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
        <main id="main-content" className="max-w-7xl mx-auto p-8 flex-1 w-full flex flex-col" tabIndex={-1}>
            <div className="mb-8">
                <h2 className="text-3xl font-display font-black text-white">
                    Mi Biblioteca
                </h2>
                <p className="text-slate-400 font-body mt-2">
                    Gestiona tus soluciones de referencia en C/C++ y supervisa el análisis de similitud entre entregas del curso.
                </p>
            </div>

            <SearchBar searchTerm={searchTerm} onSearchChange={handleSearchChange} />

            {isLoading ? (
                <div className="flex flex-col items-center justify-center py-20 text-slate-400">
                    <Loader2 className="w-8 h-8 animate-spin text-graphito-blue mb-3" />
                    <p className="text-sm font-medium">Cargando soluciones de referencia...</p>
                </div>
            ) : filteredReferences.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-20 border border-dashed border-[#2b3346] rounded-2xl p-8 text-center my-4 bg-[#121827]/20">
                    <p className="text-slate-300 font-bold text-lg mb-1">No hay soluciones de referencia registradas</p>
                    <p className="text-slate-500 text-sm max-w-md">
                        Comienza agregando tu primera solución de referencia en C o C++ haciendo clic en "Nuevo Código" en la esquina superior.
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
        </main>
    );
}
