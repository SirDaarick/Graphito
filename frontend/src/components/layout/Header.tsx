import { Bell, ChevronDown } from "lucide-react";
import { GradientButton } from "../ui/GradientButton";

// Importamos tu logo. Asegúrate de que esté en src/assets/logo.png
import logo from "../../assets/logo.png";

export function Header() {
    return (
        <header className="w-full bg-graphito-dark border-b border-graphito-border px-6 py-4">
            <div className="max-w-7xl mx-auto flex items-center justify-between">

                {/* Lado Izquierdo: Logo y Nav */}
                <div className="flex items-center gap-10">
                    <div className="flex items-center gap-3 group cursor-pointer">
                        {/* 1. Cambio: Logo PNG en lugar del div con la 'G' */}
                        <img
                            src={logo}
                            alt="Graphito Logo"
                            className="w-9 h-9 object-contain transform group-hover:rotate-6 transition-transform duration-300"
                        />

                        {/* 2. Cambio: Texto con relleno de degradado */}
                        <span className="text-2xl font-display font-extrabold tracking-tighter bg-gradient-to-r from-graphito-blue to-graphito-violet bg-clip-text text-transparent">
                            Graphito
                        </span>
                    </div>

                    <nav className="hidden md:flex items-center gap-6">
                        <a href="#" className="font-body text-sm font-semibold text-white border-b-2 border-graphito-blue pb-1">
                            Biblioteca
                        </a>
                        <a href="#" className="font-body text-sm font-medium text-slate-400 hover:text-white transition-colors">
                            Historial
                        </a>
                        <a href="#" className="font-body text-sm font-medium text-slate-400 hover:text-white transition-colors">
                            Configuración
                        </a>
                    </nav>
                </div>

                {/* Lado Derecho: Acciones y Perfil */}
                <div className="flex items-center gap-6">

                    <GradientButton>
                        <span>+ Nuevo código</span>
                    </GradientButton>

                    <button className="relative p-2 text-slate-400 hover:text-white hover:bg-graphito-card rounded-full transition-all">
                        <Bell size={20} />
                        <span className="absolute top-2 right-2 w-2 h-2 bg-risk-high rounded-full border-2 border-graphito-dark"></span>
                    </button>

                    <div className="h-8 w-[1px] bg-graphito-border"></div>

                    <div className="flex items-center gap-3 pl-2 cursor-pointer group">
                        <div className="relative">
                            <div className="w-10 h-10 rounded-full bg-graphito-card border border-graphito-border overflow-hidden ring-2 ring-transparent group-hover:ring-graphito-blue/50 transition-all">
                                <div className="w-full h-full bg-gradient-to-tr from-slate-700 to-slate-500 flex items-center justify-center text-white font-bold">
                                    D
                                </div>
                            </div>
                            <div className="absolute bottom-0 right-0 w-3 h-3 bg-emerald-500 border-2 border-graphito-dark rounded-full"></div>
                        </div>

                        <div className="hidden lg:block text-left">
                            <p className="font-body text-xs font-bold text-white leading-none">Daarick ESCOM</p>
                            <p className="font-body text-[10px] text-slate-500 mt-1 uppercase tracking-wider">Investigador</p>
                        </div>
                        <ChevronDown size={14} className="text-slate-500 group-hover:text-white transition-colors" />
                    </div>

                </div>
            </div>
        </header>
    );
}