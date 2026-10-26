"use client"

import React from "react"
import { Search, SlidersHorizontal, ArrowUpDown } from "lucide-react"
import { cn } from "../../lib/utils"

interface SearchBarProps {
    searchTerm: string;
    onSearchChange: (value: string) => void;
    placeholder?: string;
    showFilterButtons?: boolean;
    className?: string;
    children?: React.ReactNode;
}

export function SearchBar({
    searchTerm,
    onSearchChange,
    placeholder = "Buscar en la librería de códigos...",
    showFilterButtons = false,
    className,
    children,
}: SearchBarProps) {
    return (
        <div className={cn("flex flex-col md:flex-row items-stretch md:items-center gap-4 w-full", className)}>
            <div className="relative flex-1 w-full group">
                <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400 dark:text-slate-500 group-focus-within:text-graphito-blue transition-colors" />
                <input
                    type="text"
                    value={searchTerm}
                    onChange={(e) => onSearchChange(e.target.value)}
                    placeholder={placeholder}
                    className={cn(
                        "w-full pl-10 pr-4 py-2.5 rounded-xl font-body text-sm transition-all",
                        "bg-white/25 dark:bg-graphito-card/15 backdrop-blur-[3px] border border-slate-200/60 dark:border-white/15 text-slate-900 dark:text-white shadow-[inset_0_1px_0_0_rgba(255,255,255,0.08)]",
                        "placeholder:text-slate-400 dark:placeholder:text-slate-600 outline-none",
                        "focus:border-graphito-blue/50 focus:ring-4 focus:ring-graphito-blue/10"
                    )}
                />
            </div>

            {children}

            {showFilterButtons && (
                <div className="flex items-center gap-3 w-full md:w-auto shrink-0">
                    <button
                        type="button"
                        className={cn(
                            "flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl font-body text-sm font-semibold transition-all",
                            "bg-white/25 dark:bg-graphito-card/15 backdrop-blur-[3px] border border-slate-200/60 dark:border-white/15 text-slate-700 dark:text-slate-300 shadow-[inset_0_1px_0_0_rgba(255,255,255,0.08)]",
                            "hover:text-slate-900 dark:hover:text-white hover:border-graphito-blue/30 hover:bg-slate-100 dark:hover:bg-graphito-card/80",
                            "active:scale-95 focus-visible:ring-2 focus-visible:ring-graphito-blue/50 focus-visible:outline-none"
                        )}
                        aria-label="Abrir filtros"
                    >
                        <SlidersHorizontal className="h-4 w-4" />
                        <span>Filtrar</span>
                    </button>

                    <button
                        type="button"
                        className={cn(
                            "flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl font-body text-sm font-semibold transition-all",
                            "bg-white/25 dark:bg-graphito-card/15 backdrop-blur-[3px] border border-slate-200/60 dark:border-white/15 text-slate-700 dark:text-slate-300 shadow-[inset_0_1px_0_0_rgba(255,255,255,0.08)]",
                            "hover:text-slate-900 dark:hover:text-white hover:border-graphito-blue/30 hover:bg-slate-100 dark:hover:bg-graphito-card/80",
                            "active:scale-95 focus-visible:ring-2 focus-visible:ring-graphito-blue/50 focus-visible:outline-none"
                        )}
                        aria-label="Abrir opciones de ordenamiento"
                    >
                        <ArrowUpDown className="h-4 w-4" />
                        <span>Ordenar</span>
                    </button>
                </div>
            )}
        </div>
    )
}
