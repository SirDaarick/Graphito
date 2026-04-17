"use client"

import { ChevronLeft, ChevronRight } from "lucide-react"
import { cn } from "../../lib/utils" // Usando ruta relativa para evitar errores de alias

interface PaginationControlsProps {
    currentPage: number
    totalPages: number
    totalItems: number
    itemsPerPage: number
    onPageChange: (page: number) => void
}

export function PaginationControls({
    currentPage,
    totalPages,
    totalItems,
    itemsPerPage,
    onPageChange,
}: PaginationControlsProps) {
    const startItem = (currentPage - 1) * itemsPerPage + 1
    const endItem = Math.min(currentPage * itemsPerPage, totalItems)

    return (
        <div className="flex items-center justify-between mt-10 px-2 font-body">
            {/* Texto informativo */}
            <p className="text-sm text-slate-400">
                Mostrando <span className="text-white font-semibold">{startItem}-{endItem}</span> de <span className="text-white font-semibold">{totalItems}</span> referencias
            </p>

            {/* Controles de página */}
            <div className="flex items-center gap-1">
                {/* Botón Anterior */}
                <button
                    className={cn(
                        "p-2.5 min-w-11 min-h-11 rounded-lg transition-all border border-transparent",
                        currentPage === 1
                            ? "text-slate-600 cursor-not-allowed"
                            : "text-slate-400 hover:text-white hover:bg-graphito-card hover:border-graphito-border focus-visible:ring-2 focus-visible:ring-graphito-blue/50 focus-visible:outline-none"
                    )}
                    onClick={() => onPageChange(currentPage - 1)}
                    disabled={currentPage === 1}
                    aria-label="Página anterior"
                >
                    <ChevronLeft className="h-5 w-5" />
                </button>

                {/* Números de página */}
                <div className="flex items-center gap-1 px-2">
                    {Array.from({ length: totalPages }, (_, i) => i + 1).map((page) => (
                        <button
                            key={page}
                            onClick={() => onPageChange(page)}
                            aria-label={`Ir a página ${page}`}
                            aria-current={page === currentPage ? "page" : undefined}
                            className={cn(
                                "h-9 w-9 min-w-9 rounded-xl text-sm font-bold transition-all duration-300",
                                page === currentPage
                                    ? "bg-graphito-blue text-white shadow-[0_0_15px_rgba(59,130,246,0.4)] scale-110"
                                    : "text-slate-400 hover:text-white hover:bg-graphito-card focus-visible:ring-2 focus-visible:ring-graphito-blue/50 focus-visible:outline-none"
                            )}
                        >
                            {page}
                        </button>
                    ))}
                </div>

                {/* Botón Siguiente */}
                <button
                    className={cn(
                        "p-2.5 min-w-11 min-h-11 rounded-lg transition-all border border-transparent",
                        currentPage === totalPages
                            ? "text-slate-600 cursor-not-allowed"
                            : "text-slate-400 hover:text-white hover:bg-graphito-card hover:border-graphito-border focus-visible:ring-2 focus-visible:ring-graphito-blue/50 focus-visible:outline-none"
                    )}
                    onClick={() => onPageChange(currentPage + 1)}
                    disabled={currentPage === totalPages}
                    aria-label="Página siguiente"
                >
                    <ChevronRight className="h-5 w-5" />
                </button>
            </div>
        </div>
    )
}