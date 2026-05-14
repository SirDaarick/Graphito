import { useState, useRef, useEffect } from "react";
import { Bell, ChevronDown, X, FileText } from "lucide-react";
import { GradientButton } from "../ui/GradientButton";

import logo from "../../assets/logo.png";

interface Comparison {
    id: string;
    title: string;
    subtitle: string;
    similarity: number;
}

interface Notification {
    id: string;
    comparison: Comparison;
}

const MOCK_NOTIFICATIONS: Notification[] = [
    {
        id: "n1",
        comparison: { id: "c1", title: "Juan Pérez - Boleta 2022630123", subtitle: "Entrega Práctica 2", similarity: 89 },
    },
    {
        id: "n2",
        comparison: { id: "c2", title: "Maria Garcia - Boleta 2022630456", subtitle: "Tarea Semanal 4", similarity: 12 },
    },
    {
        id: "n3",
        comparison: { id: "c5", title: "Carlos López - Boleta 2021630987", subtitle: "Proyecto Parcial 1", similarity: 94 },
    },
    {
        id: "n4",
        comparison: { id: "c8", title: "Pedro Ruiz - Boleta 2022630345", subtitle: "Tarea 3 - Algoritmos", similarity: 76 },
    },
    {
        id: "n5",
        comparison: { id: "c9", title: "Sofía Díaz - Boleta 2022630567", subtitle: "Práctica de Laboratorio", similarity: 88 },
    },
];

interface HeaderProps {
    onNewCode?: () => void;
    onLogout?: () => void;
    onViewComparison?: (comparison: Comparison) => void;
}

export function Header({ onNewCode, onLogout, onViewComparison }: HeaderProps) {
    const [showNotifications, setShowNotifications] = useState(false);
    const [showUserMenu, setShowUserMenu] = useState(false);
    const [notifications, setNotifications] = useState<Notification[]>(MOCK_NOTIFICATIONS);

    const notifRef = useRef<HTMLDivElement>(null);
    const userMenuRef = useRef<HTMLDivElement>(null);

    // Cerrar dropdowns al hacer clic fuera
    useEffect(() => {
        function handleClickOutside(event: MouseEvent) {
            if (notifRef.current && !notifRef.current.contains(event.target as Node)) {
                setShowNotifications(false);
            }
            if (userMenuRef.current && !userMenuRef.current.contains(event.target as Node)) {
                setShowUserMenu(false);
            }
        }
        document.addEventListener("click", handleClickOutside);
        return () => document.removeEventListener("click", handleClickOutside);
    }, []);

    const dismissNotification = (id: string) => {
        setNotifications((prev) => prev.filter((n) => n.id !== id));
    };

    const handleReportClick = (comparison: Comparison) => {
        setShowNotifications(false);
        onViewComparison?.(comparison);
    };

    const handleLogout = () => {
        onLogout?.();
    };

    return (
        <header className="w-full bg-graphito-dark border-b border-graphito-border px-6 py-4">
            <div className="max-w-7xl mx-auto flex items-center justify-between">

                {/* Lado Izquierdo: Logo y Nav */}
                <div className="flex items-center gap-10">
                    <div className="flex items-center gap-3 group cursor-pointer">
                        <img
                            src={logo}
                            alt="Graphito Logo"
                            className="w-9 h-9 object-contain transform group-hover:rotate-6 transition-transform duration-300"
                        />
                        <span className="text-2xl font-display font-extrabold tracking-tighter bg-gradient-to-r from-graphito-blue to-graphito-violet bg-clip-text text-transparent">
                            Graphito
                        </span>
                    </div>

                    <nav className="hidden md:flex items-center gap-6">
                        <a href="#" className="font-body text-sm font-semibold text-white border-b-2 border-graphito-blue pb-1">
                            Biblioteca
                        </a>
                        <a
                            href="https://github.com/SirDaarick/Graphito"
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-slate-400 hover:text-white transition-colors"
                            aria-label="Repositorio de GitHub"
                        >
                            <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor" className="text-current">
                                    <path d="M12 0C5.37 0 0 5.37 0 12c0 5.303 3.438 9.8 8.205 11.385.6.113.82-.258.82-.577 0-.285-.01-1.04-.015-2.04-3.338.724-4.042-1.61-4.042-1.61-.546-1.385-1.335-1.755-1.335-1.755-1.087-.744.084-.729.084-.729 1.205.084 1.838 1.236 1.838 1.236 1.07 1.835 2.809 1.305 3.495.998.108-.776.417-1.305.76-1.605-2.665-.3-5.466-1.332-5.466-5.93 0-1.31.465-2.38 1.235-3.22-.135-.303-.54-1.523.105-3.176 0 0 1.005-.322 3.3 1.23.96-.267 1.98-.399 3-.405 1.02.006 2.04.138 3 .405 2.28-1.552 3.285-1.23 3.285-1.23.645 1.653.24 2.873.12 3.176.765.84 1.23 1.91 1.23 3.22 0 4.61-2.805 5.625-5.475 5.92.42.36.81 1.096.81 2.22 0 1.605-.015 2.896-.015 3.286 0 .315.21.69.825.57C20.565 21.795 24 17.295 24 12 24 5.37 18.63 0 12 0z" />
                                </svg>
                        </a>
                    </nav>
                </div>

                {/* Lado Derecho: Acciones y Perfil */}
                <div className="flex items-center gap-6">

                    <GradientButton onClick={onNewCode}>
                        <span>+ Nuevo código</span>
                    </GradientButton>

                    {/* Campana de notificaciones */}
                    <div className="relative" ref={notifRef}>
                        <button
                            onClick={(e) => {
                                e.stopPropagation();
                                setShowNotifications(!showNotifications);
                                setShowUserMenu(false);
                            }}
                            className="relative p-2 text-slate-400 hover:text-white hover:bg-graphito-card rounded-full transition-all focus-visible:ring-2 focus-visible:ring-graphito-blue/50 focus-visible:outline-none"
                            aria-label="Notificaciones"
                        >
                            <Bell size={20} />
                            {notifications.length > 0 && (
                                <span className="absolute top-2 right-2 w-2 h-2 bg-risk-high rounded-full border-2 border-graphito-dark"></span>
                            )}
                        </button>

                        {/* Dropdown de notificaciones */}
                        {showNotifications && (
                            <div className="absolute right-0 top-12 w-80 bg-graphito-card border border-graphito-border rounded-2xl shadow-2xl shadow-black/40 z-50 overflow-hidden">
                                <div className="flex items-center justify-between px-4 py-3 border-b border-graphito-border">
                                    <h3 className="text-sm font-bold text-white">Notificaciones</h3>
                                    {notifications.length > 0 && (
                                        <span className="text-[10px] font-bold text-slate-500 bg-graphito-dark px-2 py-0.5 rounded-full">
                                            {notifications.length}
                                        </span>
                                    )}
                                </div>
                                <div className="max-h-80 overflow-y-auto">
                                    {notifications.length > 0 ? (
                                        notifications.map((notif) => (
                                            <div
                                                key={notif.id}
                                                onClick={() => handleReportClick(notif.comparison)}
                                                className="px-4 py-3 border-b border-graphito-border/50 hover:bg-graphito-dark/50 transition-colors cursor-pointer"
                                            >
                                                <div className="flex items-start gap-2 mb-2">
                                                    <div className="w-5 h-5 rounded-full bg-graphito-blue/20 flex items-center justify-center shrink-0 mt-0.5">
                                                        <div className="w-2 h-2 rounded-full bg-graphito-blue"></div>
                                                    </div>
                                                    <div className="flex-1 min-w-0">
                                                        <p className="text-xs font-semibold text-white leading-tight">
                                                            Comparación terminada
                                                        </p>
                                                        <p className="text-[11px] text-slate-400 mt-0.5 leading-tight">
                                                            {notif.comparison.title}
                                                        </p>
                                                        <p className="text-[10px] text-slate-500 mt-0.5">
                                                            {notif.comparison.subtitle}
                                                        </p>
                                                    </div>
                                                </div>
                                                <div className="flex items-center gap-2 ml-7">
                                                    <button
                                                        onClick={(e) => {
                                                            e.stopPropagation();
                                                            handleReportClick(notif.comparison);
                                                        }}
                                                        className="flex items-center gap-1 px-2.5 py-1 text-[10px] font-bold text-white bg-graphito-blue/20 hover:bg-graphito-blue/40 rounded-lg transition-colors"
                                                    >
                                                        <FileText size={11} />
                                                        Reporte
                                                    </button>
                                                    <button
                                                        onClick={(e) => {
                                                            e.stopPropagation();
                                                            dismissNotification(notif.id);
                                                        }}
                                                        className="flex items-center gap-1 px-2.5 py-1 text-[10px] font-medium text-slate-400 hover:text-white hover:bg-graphito-dark rounded-lg transition-colors"
                                                    >
                                                        <X size={11} />
                                                        Cerrar
                                                    </button>
                                                </div>
                                            </div>
                                        ))
                                    ) : (
                                        <div className="px-4 py-8 text-center text-xs text-slate-500">
                                            No hay notificaciones
                                        </div>
                                    )}
                                </div>
                            </div>
                        )}
                    </div>

                    <div className="h-8 w-[1px] bg-graphito-border"></div>

                    {/* Menú de usuario */}
                    <div className="relative" ref={userMenuRef}>
                        <button
                            onClick={(e) => {
                                e.stopPropagation();
                                setShowUserMenu(!showUserMenu);
                                setShowNotifications(false);
                            }}
                            className="flex items-center gap-3 pl-2 cursor-pointer group rounded-xl transition-all focus-visible:ring-2 focus-visible:ring-graphito-blue/50 focus-visible:outline-none"
                            aria-label="Menú de usuario"
                        >
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
                            </div>
                            <ChevronDown size={14} className="text-slate-500 group-hover:text-white transition-colors" />
                        </button>

                        {/* Dropdown del usuario */}
                        {showUserMenu && (
                            <div className="absolute right-0 top-12 w-48 bg-graphito-card border border-graphito-border rounded-xl shadow-2xl shadow-black/40 z-50 overflow-hidden">
                                <div className="px-4 py-3 border-b border-graphito-border">
                                    <p className="text-xs font-bold text-white">Daarick ESCOM</p>
                                    <p className="text-[10px] text-slate-500">daarick@example.com</p>
                                </div>
                                <div className="py-1">
                                    <button
                                        onClick={(e) => {
                                            e.stopPropagation();
                                            handleLogout();
                                        }}
                                        className="w-full flex items-center gap-3 px-4 py-2.5 text-sm text-slate-300 hover:text-white hover:bg-graphito-dark transition-colors"
                                    >
                                        <span>Cerrar sesión</span>
                                    </button>
                                </div>
                            </div>
                        )}
                    </div>

                </div>
            </div>
        </header>
    );
}
