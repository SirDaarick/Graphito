import { useState, useEffect, useRef } from "react";
import { AtSign, Lock, Eye, EyeOff, Loader2, Sun, Moon } from "lucide-react";
import logo from "../assets/logo.png";
import { AuthCard } from "../components/layout/AuthCard";
import { api } from "../lib/api";
import { useTheme } from "../context/ThemeContext";

interface LoginProps {
    onLogin?: () => void;
    onNavigateToRegister?: () => void;
}

export function Login({ onLogin, onNavigateToRegister }: LoginProps) {
    const [email, setEmail] = useState("");
    const [password, setPassword] = useState("");
    const [showPassword, setShowPassword] = useState(false);
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const { isDark, toggleTheme } = useTheme();
    const googleBtnRef = useRef<HTMLDivElement>(null);

    // Callback tras seleccionar cuenta en el popup oficial de Google
    const handleGoogleCallback = async (response: any) => {
        setIsLoading(true);
        setError(null);
        try {
            if (!response.credential) {
                throw new Error("No se recibió la credencial de autenticación de Google.");
            }
            await api.auth.googleLogin(response.credential);
            onLogin?.();
        } catch (err: any) {
            console.error("Error al autenticar con Google:", err);
            if (err.message?.includes("Failed to fetch") || err.name === "TypeError") {
                setError("No se pudo conectar con el servidor backend (ngrok). Verifique que el túnel esté activo y la URL configurada en VITE_API_URL.");
            } else {
                setError(err.message || "Error al autenticar con Google.");
            }
        } finally {
            setIsLoading(false);
        }
    };

    // Inicializar y renderizar botón oficial de Google Identity (Popup limpio, sin FedCM / Passkeys de dispositivo)
    useEffect(() => {
        const clientId = import.meta.env.VITE_GOOGLE_CLIENT_ID;
        if (!clientId) return;

        const renderGoogleButton = () => {
            if (!window.google?.accounts?.id || !googleBtnRef.current) return;

            window.google.accounts.id.initialize({
                client_id: clientId,
                callback: handleGoogleCallback,
                auto_select: false,
            });

            googleBtnRef.current.innerHTML = "";
            window.google.accounts.id.renderButton(googleBtnRef.current, {
                type: "standard",
                theme: isDark ? "filled_black" : "outline",
                size: "large",
                text: "continue_with",
                shape: "pill",
                width: 360,
                logo_alignment: "left",
            });
        };

        if (window.google?.accounts?.id) {
            renderGoogleButton();
        } else {
            const timer = setInterval(() => {
                if (window.google?.accounts?.id) {
                    clearInterval(timer);
                    renderGoogleButton();
                }
            }, 100);
            return () => clearInterval(timer);
        }
    }, [isDark]);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setError(null);
        setIsLoading(true);
        try {
            await api.auth.login(email, password);
            onLogin?.();
        } catch (err: any) {
            console.error("Error en login manual:", err);
            if (err.message?.includes("Failed to fetch") || err.name === "TypeError") {
                setError("No se pudo conectar con el servidor backend (ngrok). Verifique que el contenedor Docker y ngrok estén activos.");
            } else {
                setError(err.message || "Error al iniciar sesión. Verifique sus credenciales.");
            }
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <div className="flex-1 w-full flex flex-col items-center justify-center p-4 relative min-h-screen">
            {/* Botón flotante para cambiar tema */}
            <button
                type="button"
                onClick={toggleTheme}
                className="fixed top-6 right-6 p-2.5 text-slate-700 dark:text-slate-300 hover:bg-slate-200/60 dark:hover:bg-graphito-card rounded-full transition-all focus:outline-none z-50"
                aria-label="Cambiar tema"
                title={isDark ? "Cambiar a Modo Claro" : "Cambiar a Modo Oscuro"}
            >
                {isDark ? (
                    <Sun size={22} className="text-amber-400 hover:rotate-45 transition-transform" />
                ) : (
                    <Moon size={22} className="text-slate-700 hover:-rotate-12 transition-transform" />
                )}
            </button>

            <AuthCard className="w-full max-w-md bg-white dark:bg-graphito-card border border-slate-200 dark:border-[#2b3346]/60 shadow-xl transition-colors">
                {/* Header de la tarjeta */}
                <div className="flex flex-col items-center mb-10">
                    <div className="flex items-center gap-3 mb-4">
                        <img src={logo} alt="Graphito Logo" className="w-10 h-10 object-contain" />
                        <h1 className="text-4xl font-display font-extrabold tracking-tight bg-gradient-to-r from-graphito-blue to-graphito-violet bg-clip-text text-transparent">
                            Graphito
                        </h1>
                    </div>
                    <p className="text-sm text-slate-600 dark:text-slate-300 font-medium text-center">
                        Compara. Analiza. Comprende tu código.
                    </p>
                </div>

                {/* Botón oficial de Google Identity Services */}
                <div className="w-full flex flex-col items-center justify-center min-h-[44px]">
                    <div ref={googleBtnRef} className="flex justify-center w-full min-h-[44px]" />
                    {!import.meta.env.VITE_GOOGLE_CLIENT_ID && (
                        <p className="text-[11px] text-amber-600 dark:text-amber-400 mt-2 font-medium">
                            VITE_GOOGLE_CLIENT_ID no está configurado en .env
                        </p>
                    )}
                </div>

                {/* Separador */}
                <div className="flex items-center my-6">
                    <div className="flex-grow border-t border-slate-200 dark:border-[#2b3346]"></div>
                    <span className="mx-4 text-[10px] font-bold text-slate-400 dark:text-slate-500 uppercase">o</span>
                    <div className="flex-grow border-t border-slate-200 dark:border-[#2b3346]"></div>
                </div>

                {/* Error Banner */}
                {error && (
                    <div className="mb-4 p-3.5 bg-red-500/10 border border-red-500/30 rounded-xl text-red-600 dark:text-red-300 text-xs font-medium">
                        {error}
                    </div>
                )}

                {/* Formulario manual */}
                <form onSubmit={handleSubmit} className="space-y-5">
                    {/* Email */}
                    <div className="space-y-2">
                        <label htmlFor="login-email" className="text-[13px] font-bold text-slate-700 dark:text-slate-200 ml-1">
                            Correo electrónico
                        </label>
                        <div className="relative group">
                            <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none text-slate-400 dark:text-slate-500 group-focus-within:text-graphito-blue transition-colors">
                                <AtSign size={18} />
                            </div>
                            <input
                                id="login-email"
                                type="email"
                                required
                                value={email}
                                onChange={(e) => setEmail(e.target.value)}
                                placeholder="nombre@ejemplo.com"
                                className="w-full bg-slate-50 dark:bg-[#121827]/30 border border-slate-200 dark:border-[#2b3346] text-slate-900 dark:text-white rounded-2xl py-3.5 pl-12 pr-4 focus:outline-none focus:ring-2 focus:ring-graphito-blue/50 focus:border-graphito-blue transition-all placeholder:text-slate-400 dark:placeholder:text-slate-500 font-medium text-[15px]"
                            />
                        </div>
                    </div>

                    {/* Password */}
                    <div className="space-y-2">
                        <div className="flex items-center justify-between ml-1">
                            <label htmlFor="login-password" className="text-[13px] font-bold text-slate-700 dark:text-slate-200">
                                Contraseña
                            </label>
                            <button type="button" className="text-[10px] font-bold text-graphito-blue dark:text-graphito-violet hover:underline dark:hover:text-white transition-colors uppercase tracking-wider">
                                ¿Olvidaste tu contraseña?
                            </button>
                        </div>
                        <div className="relative group">
                            <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none text-slate-400 dark:text-slate-500 group-focus-within:text-graphito-blue transition-colors">
                                <Lock size={18} />
                            </div>
                            <input
                                id="login-password"
                                type={showPassword ? "text" : "password"}
                                required
                                value={password}
                                onChange={(e) => setPassword(e.target.value)}
                                placeholder="••••••••"
                                className="w-full bg-slate-50 dark:bg-[#121827]/30 border border-slate-200 dark:border-[#2b3346] text-slate-900 dark:text-white rounded-2xl py-3.5 pl-12 pr-12 focus:outline-none focus:ring-2 focus:ring-graphito-blue/50 focus:border-graphito-blue transition-all placeholder:text-slate-400 dark:placeholder:text-slate-500 text-[15px] tracking-widest font-mono"
                            />
                            <button
                                type="button"
                                onClick={() => setShowPassword(!showPassword)}
                                className="absolute inset-y-0 right-0 pr-4 flex items-center text-slate-400 hover:text-slate-700 dark:hover:text-white transition-colors"
                                aria-label={showPassword ? "Ocultar contraseña" : "Mostrar contraseña"}
                            >
                                {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                            </button>
                        </div>
                    </div>

                    {/* Submit */}
                    <button
                        type="submit"
                        disabled={isLoading}
                        className="w-full bg-gradient-to-r from-graphito-blue to-graphito-violet text-white font-bold rounded-2xl py-4 mt-2 hover:opacity-90 transition-opacity shadow-lg shadow-graphito-blue/20 text-[15px] flex items-center justify-center gap-2 disabled:opacity-50"
                    >
                        {isLoading ? (
                            <>
                                <Loader2 className="w-5 h-5 animate-spin" />
                                <span>Iniciando sesión...</span>
                            </>
                        ) : (
                            <span>Iniciar sesión</span>
                        )}
                    </button>
                </form>

                {/* Footer text */}
                <div className="mt-8 text-center">
                    <p className="text-[13px] text-slate-600 dark:text-slate-400 font-medium">
                        ¿No tienes una cuenta? <button onClick={onNavigateToRegister} className="text-slate-900 dark:text-white hover:text-graphito-blue dark:hover:text-graphito-violet font-bold transition-colors ml-1">Crear cuenta</button>
                    </p>
                </div>
            </AuthCard>

            {/* Badge ESCOM */}
            <div className="absolute bottom-6 flex items-center justify-center">
                <div className="flex items-center gap-2 bg-white/80 dark:bg-[#1a2031]/60 border border-slate-200 dark:border-[#2b3346] rounded-full px-4 py-2 backdrop-blur-md shadow-sm dark:shadow-none">
                    <div className="w-1.5 h-1.5 bg-indigo-500 dark:bg-indigo-400 rounded-full"></div>
                    <span className="text-[10px] uppercase font-bold tracking-widest text-slate-600 dark:text-slate-300">
                        Graphito ESCOM IPN
                    </span>
                </div>
            </div>
        </div>
    );
}