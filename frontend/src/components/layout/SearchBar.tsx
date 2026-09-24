"use client"

import { Search, SlidersHorizontal, ArrowUpDown } from "lucide-react"
import { cn } from "../../lib/utils"

interface SearchBarProps {
    searchTerm: string;
    onSearchChange: (value: string) => void;
}

export function SearchBar({ searchTerm, onSearchChange }: SearchBarProps) {
    return (
        <div className="flex flex-col md:flex-row items-start md:items-center gap-4 w-full mb-8">
            <div className="relative flex-1 w-full max-w-xl group">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400 dark:text-slate-500 group-focus-within:text-graphito-blue transition-colors" />
                <input
                    type="text"
                    value={searchTerm}
                    onChange={(e) => onSearchChange(e.target.value)}
                    placeholder="Buscar en la librería de códigos..."
                    className={cn(
                        "w-full pl-10 pr-4 py-2.5 rounded-xl font-body text-sm transition-all",
                        "bg-white dark:bg-graphito-dark border border-slate-200 dark:border-graphito-border text-slate-900 dark:text-white",
                        "placeholder:text-slate-400 dark:placeholder:text-slate-600 outline-none",
                        "focus:border-graphito-blue/50 focus:ring-4 focus:ring-graphito-blue/10"
                    )}
                />
            </div>

            {/* Botones de Acción */}
            <div className="flex items-center gap-3 w-full md:w-auto">
                <button
                    className={cn(
                        "flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl font-body text-sm font-semibold transition-all",
                        "bg-white dark:bg-graphito-card border border-slate-200 dark:border-graphito-border text-slate-700 dark:text-slate-400",
                        "hover:text-slate-900 dark:hover:text-white hover:border-graphito-blue/30 hover:bg-slate-100 dark:hover:bg-graphito-card/80",
                        "active:scale-95 focus-visible:ring-2 focus-visible:ring-graphito-blue/50 focus-visible:outline-none"
                    )}
                    aria-label="Abrir filtros"
                >
                    <SlidersHorizontal className="h-4 w-4" />
                    <span>Filtrar</span>
                </button>

                <button
                    className={cn(
                        "flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl font-body text-sm font-semibold transition-all",
                        "bg-white dark:bg-graphito-card border border-slate-200 dark:border-graphito-border text-slate-700 dark:text-slate-400",
                        "hover:text-slate-900 dark:hover:text-white hover:border-graphito-blue/30 hover:bg-slate-100 dark:hover:bg-graphito-card/80",
                        "active:scale-95 focus-visible:ring-2 focus-visible:ring-graphito-blue/50 focus-visible:outline-none"
                    )}
                    aria-label="Abrir opciones de ordenamiento"
                >
                    <ArrowUpDown className="h-4 w-4" />
                    <span>Ordenar</span>
                </button>
            </div>
        </div>
    )
}