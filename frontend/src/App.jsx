import { useState } from "react";
import { Header } from "./components/layout/Header";
import { ReferenceCard } from "./components/layout/ReferenceCard";
import { PaginationControls } from "./components/ui/PaginationControls";
import { SearchBar } from "./components/layout/SearchBar";

const BASE_MOCKS = [
  {
    id: "ref-1",
    title: "Algoritmo de Dijkstra - Optimización de Rutas",
    category: "Grafos",
    categoryColor: "cyan",
    description: "Implementación base del algoritmo de Dijkstra para el cálculo de rutas mínimas en grafos dirigidos con pesos no negativos.",
    updatedAt: "14 Abr, 2026",
    activeComparisons: 3,
    comparisons: [
      { id: "c1", title: "Juan Pérez - Boleta 2022630123", subtitle: "Entrega Final Semestre", similarity: 89 },
      { id: "c2", title: "Maria Garcia - Boleta 2022630456", subtitle: "Práctica 4", similarity: 12 },
      { id: "c3", title: "Repositorio Externo - GitHub", subtitle: "Estructuras_C_Master", similarity: 45 },
    ]
  },
  {
    id: "ref-2",
    title: "Análisis Léxico - Compiladores",
    category: "Teoría",
    categoryColor: "purple",
    description: "Referencia para el proyecto de compiladores que incluye el manejo de tokens y tablas de símbolos.",
    updatedAt: "12 Abr, 2026",
    activeComparisons: 1,
    comparisons: [
      { id: "c4", title: "Proyecto_Final_V2.c", subtitle: "Subido por: Dr. Arjona", similarity: 5 },
    ]
  }
];

// Generamos 25 referencias de prueba repetidas para poder ver la paginación en acción
const MOCK_REFERENCES = Array.from({ length: 25 }, (_, i) => ({
  ...BASE_MOCKS[i % 2],
  id: `ref-${i + 1}`,
  title: `${BASE_MOCKS[i % 2].title} (#${i + 1})`,
}));

function App() {
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

  const handleSearchChange = (value) => {
    setSearchTerm(value);
    setCurrentPage(1); // Resetear a la primera página al buscar
  };

  return (
    <div className="min-h-screen bg-graphito-dark">
      <Header />

      <main className="max-w-7xl mx-auto p-8">
        <div className="mb-8">
          <h2 className="text-3xl font-display font-black text-white">
            Mi Biblioteca
          </h2>
          <p className="text-slate-400 font-body mt-2">
            Gestiona tus códigos de referencia y supervisa los análisis de integridad bimodal.
          </p>
        </div>

        <SearchBar searchTerm={searchTerm} onSearchChange={handleSearchChange} />

        <div className="flex flex-col">
          {paginatedReferences.map((ref) => (
            <ReferenceCard
              key={ref.id}
              title={ref.title}
              category={ref.category}
              categoryColor={ref.categoryColor}
              description={ref.description}
              updatedAt={ref.updatedAt}
              activeComparisons={ref.activeComparisons}
              comparisons={ref.comparisons}
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
    </div>
  );
}

export default App;