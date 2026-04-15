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
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-500 group-focus-within:text-graphito-blue transition-colors" />
                <input
                    type="text"
                    value={searchTerm}
                    onChange={(e) => onSearchChange(e.target.value)}
                    placeholder="Buscar en la librería de códigos..."
                    className={cn(
                        "w-full pl-10 pr-4 py-2.5 rounded-xl font-body text-sm",
                        "bg-graphito-dark border border-graphito-border text-white",
                        "placeholder:text-slate-600 outline-none transition-all",
                        "focus:border-graphito-blue/50 focus:ring-4 focus:ring-graphito-blue/10"
                    )}
                />
            </div>

            {/* Botones de Acción */}
            <div className="flex items-center gap-3 w-full md:w-auto">
                <button
                    className={cn(
                        "flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl font-body text-sm font-semibold",
                        "bg-graphito-card border border-graphito-border text-slate-400 transition-all",
                        "hover:text-white hover:border-graphito-blue/30 hover:bg-graphito-card/80",
                        "active:scale-95"
                    )}
                >
                    <SlidersHorizontal className="h-4 w-4" />
                    <span>Filtrar</span>
                </button>

                <button
                    className={cn(
                        "flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl font-body text-sm font-semibold",
                        "bg-graphito-card border border-graphito-border text-slate-400 transition-all",
                        "hover:text-white hover:border-graphito-blue/30 hover:bg-graphito-card/80",
                        "active:scale-95"
                    )}
                >
                    <ArrowUpDown className="h-4 w-4" />
                    <span>Ordenar</span>
                </button>
            </div>
        </div>
    )
}