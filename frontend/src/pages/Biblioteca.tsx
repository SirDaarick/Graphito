import { useState } from "react";
import { ReferenceCard } from "../components/layout/ReferenceCard";
import { PaginationControls } from "../components/ui/PaginationControls";
import { SearchBar } from "../components/layout/SearchBar";

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

const BASE_MOCKS: Omit<Reference, "id" | "title">[] = [
    {
        category: "Arrays",
        categoryColor: "cyan",
        description: "Implementación del algoritmo Two Sum usando fuerza bruta y optimización con tabla hash en C. Retorna los índices de dos números que sumen el valor objetivo.",
        updatedAt: "14 Abr, 2026",
        activeComparisons: 3,
        comparisons: [
            { id: "c1", title: "Juan Pérez - Boleta 2022630123", subtitle: "Entrega Práctica 2", similarity: 89 },
            { id: "c2", title: "Maria Garcia - Boleta 2022630456", subtitle: "Tarea Semanal 4", similarity: 12 },
            { id: "c3", title: "Repositorio Externo - GitHub", subtitle: "intro_cpp_examples", similarity: 45 },
        ]
    },
    {
        category: "Cadenas",
        categoryColor: "purple",
        description: "Solución al problema de Palindrome Number: determina si un entero es palíndromo sin convertirlo a cadena, manejando correctamente el desbordamiento en C.",
        updatedAt: "12 Abr, 2026",
        activeComparisons: 1,
        comparisons: [
            { id: "c4", title: "Entrega_Palindromo.c", subtitle: "Subido por: Dr. Arjona", similarity: 5 },
        ]
    },
    {
        category: "Recursión",
        categoryColor: "orange",
        description: "Implementación de la secuencia de Fibonacci con tres enfoques en C: recursivo simple, memoización (top-down) y programación dinámica iterativa (bottom-up).",
        updatedAt: "10 Abr, 2026",
        activeComparisons: 2,
        comparisons: [
            { id: "c5", title: "Carlos López - Boleta 2021630987", subtitle: "Proyecto Parcial 1", similarity: 94 },
            { id: "c6", title: "Ana Martínez - Boleta 2022630111", subtitle: "Ejercicio Clase 8", similarity: 23 },
        ]
    },
    {
        category: "Algoritmos",
        categoryColor: "cyan",
        description: "Búsqueda binaria implementada en C sobre arreglos ordenados. Incluye versión iterativa y recursiva con análisis de complejidad O(log n).",
        updatedAt: "08 Abr, 2026",
        activeComparisons: 1,
        comparisons: [
            { id: "c7", title: "Equipo 3 - Proyecto Final", subtitle: "Estructuras de Datos", similarity: 18 },
        ]
    },
    {
        category: "Matemáticas",
        categoryColor: "purple",
        description: "Verificación de números primos con optimización hasta √n. Incluye la Criba de Eratóstenes para generar primos en rango y comparativa de rendimiento en C.",
        updatedAt: "05 Abr, 2026",
        activeComparisons: 4,
        comparisons: [
            { id: "c8", title: "Pedro Ruiz - Boleta 2022630345", subtitle: "Tarea 3 - Algoritmos", similarity: 76 },
            { id: "c9", title: "Sofía Díaz - Boleta 2022630567", subtitle: "Práctica de Laboratorio", similarity: 88 },
            { id: "c10", title: "Luis Gómez - Boleta 2021630456", subtitle: "Examen Diagnóstico", similarity: 34 },
            { id: "c11", title: "Repositorio Local - USB", subtitle: "codigos_c_basicos", similarity: 61 },
        ]
    }
];

const TITLES = [
    "Two Sum — Búsqueda de Pares con Hash",
    "Palindrome Number — Verificación sin String",
    "Fibonacci — Recursión vs Iterativo",
    "Binary Search — Búsqueda en O(log n)",
    "Números Primos — Criba de Eratóstenes",
];

const MOCK_REFERENCES: Reference[] = Array.from({ length: 25 }, (_, i) => ({
    ...BASE_MOCKS[i % BASE_MOCKS.length],
    id: `ref-${i + 1}`,
    title: `${TITLES[i % TITLES.length]} (#${i + 1})`,
} as Reference));

interface Comparison {
    id: string;
    title: string;
    subtitle: string;
    similarity: number;
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
    const itemsPerPage = 10;

    // Filtrar referencias según el término de búsqueda
    const filteredReferences = MOCK_REFERENCES.filter((ref) => {
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
