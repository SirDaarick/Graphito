import { useState, useEffect, useRef } from "react";
import { Check, Loader2, Sun, Moon } from "lucide-react";
import logo from "../assets/logo.png";
import { AuthCard } from "../components/layout/AuthCard";
import { api } from "../lib/api";
import { useTheme } from "../context/ThemeContext";

interface RegisterProps {
    onRegister?: () => void;
    onNavigateToLogin?: () => void;
}

export function Register({ onRegister, onNavigateToLogin }: RegisterProps) {
    const [name, setName] = useState("");
    const [email, setEmail] = useState("");
    const [password, setPassword] = useState("");
    const [confirmPassword, setConfirmPassword] = useState("");
    const [agreed, setAgreed] = useState(false);
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
            onRegister?.();
        } catch (err: any) {
            console.error("Error al registrarse con Google:", err);
            if (err.message?.includes("Failed to fetch") || err.name === "TypeError") {
                setError("No se pudo conectar con el servidor backend (ngrok). Verifique que el túnel esté activo y la URL configurada en VITE_API_URL.");
            } else {
                setError(err.message || "Error al autenticar con Google.");
            }
        } finally {
            setIsLoading(false);
        }
    };

    // Inicializar y renderizar botón oficial de Google Identity Services
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
                text: "signup_with",
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

        if (password !== confirmPassword) {
            setError("Las contraseñas no coinciden.");
            return;
        }

        setIsLoading(true);
        try {
            await api.auth.register(email, password, name);
            // Iniciar sesión inmediatamente tras registro exitoso
            await api.auth.login(email, password);
            onRegister?.();
        } catch (err: any) {
            console.error("Error al registrarse:", err);
            if (err.message?.includes("Failed to fetch") || err.name === "TypeError") {
                setError("No se pudo conectar con el servidor backend (ngrok). Verifique que el contenedor Docker y ngrok estén activos.");
            } else {
                setError(err.message || "Error al registrarse. Intente de nuevo.");
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
                <div className="flex flex-col items-center mb-8">
                    <div className="flex items-center gap-3 mb-4">
                        <img src={logo} alt="Graphito Logo" className="w-8 h-8 object-contain" />
                        <span className="text-2xl font-display font-extrabold tracking-tight bg-gradient-to-r from-graphito-blue to-graphito-violet bg-clip-text text-transparent">
                            Graphito
                        </span>
                    </div>
                    <h1 className="text-2xl font-display font-extrabold text-slate-900 dark:text-white text-center leading-tight">
                        Únete y empieza a analizar tu código
                    </h1>
                    <p className="text-xs text-slate-600 dark:text-slate-400 font-medium mt-2 text-center">
                        Crea tu espacio de trabajo editorial hoy mismo.
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
                    <span className="mx-4 text-[10px] font-bold text-slate-400 dark:text-slate-500 uppercase italic">o</span>
                    <div className="flex-grow border-t border-slate-200 dark:border-[#2b3346]"></div>
                </div>

                {/* Error Banner */}
                {error && (
                    <div className="mb-4 p-3 bg-red-500/10 border border-red-500/30 rounded-xl text-red-600 dark:text-red-300 text-xs font-medium">
                        {error}
                    </div>
                )}

                {/* Formulario */}
                <form onSubmit={handleSubmit} className="space-y-4">

                    {/* Nombre completo */}
                    <div className="space-y-1.5">
                        <label htmlFor="register-name" className="text-[12px] font-bold text-slate-700 dark:text-slate-400 ml-1">
                            Nombre completo
                        </label>
                        <input
                            id="register-name"
                            type="text"
                            required
                            value={name}
                            onChange={(e) => setName(e.target.value)}
                            placeholder="Ej. Alex Rivera"
                            className="w-full bg-slate-50 dark:bg-[#121827]/30 border border-slate-200 dark:border-[#2b3346] text-slate-900 dark:text-white rounded-xl py-3 px-4 focus:outline-none focus:ring-2 focus:ring-graphito-blue/50 focus:border-graphito-blue transition-all placeholder:text-slate-400 dark:placeholder:text-slate-600 font-medium text-sm"
                        />
                    </div>

                    {/* Email */}
                    <div className="space-y-1.5">
                        <label htmlFor="register-email" className="text-[12px] font-bold text-slate-700 dark:text-slate-400 ml-1">
                            Correo electrónico
                        </label>
                        <input
                            id="register-email"
                            type="email"
                            required
                            value={email}
                            onChange={(e) => setEmail(e.target.value)}
                            placeholder="nombre@ejemplo.com"
                            className="w-full bg-slate-50 dark:bg-[#121827]/30 border border-slate-200 dark:border-[#2b3346] text-slate-900 dark:text-white rounded-xl py-3 px-4 focus:outline-none focus:ring-2 focus:ring-graphito-blue/50 focus:border-graphito-blue transition-all placeholder:text-slate-400 dark:placeholder:text-slate-600 font-medium text-sm"
                        />
                    </div>

                    {/* Password */}
                    <div className="space-y-1.5">
                        <label htmlFor="register-password" className="text-[12px] font-bold text-slate-700 dark:text-slate-400 ml-1">
                            Contraseña
                        </label>
                        <input
                            id="register-password"
                            type="password"
                            required
                            value={password}
                            onChange={(e) => setPassword(e.target.value)}
                            placeholder="••••••••"
                            className="w-full bg-slate-50 dark:bg-[#121827]/30 border border-slate-200 dark:border-[#2b3346] text-slate-900 dark:text-white rounded-xl py-3 px-4 focus:outline-none focus:ring-2 focus:ring-graphito-blue/50 focus:border-graphito-blue transition-all placeholder:text-slate-400 dark:placeholder:text-slate-600 text-sm tracking-widest font-mono"
                        />

                        {/* Password Strength meter */}
                        <div className="flex gap-1.5 px-1 mt-2">
                            <div className="h-1.5 flex-1 rounded-full bg-orange-500"></div>
                            <div className="h-1.5 flex-1 rounded-full bg-orange-500"></div>
                            <div className="h-1.5 flex-1 rounded-full bg-slate-200 dark:bg-[#121827]/30 border border-slate-300 dark:border-[#2b3346]"></div>
                            <div className="h-1.5 flex-1 rounded-full bg-slate-200 dark:bg-[#121827]/30 border border-slate-300 dark:border-[#2b3346]"></div>
                        </div>
                        <p className="text-[10px] font-bold text-orange-500 dark:text-orange-400 ml-1">
                            Contraseña media: añade caracteres especiales
                        </p>
                    </div>

                    {/* Confirm Password */}
                    <div className="space-y-1.5">
                        <label htmlFor="register-confirm-password" className="text-[12px] font-bold text-slate-700 dark:text-slate-400 ml-1">
                            Confirmar contraseña
                        </label>
                        <div className="relative">
                            <input
                                id="register-confirm-password"
                                type="password"
                                required
                                value={confirmPassword}
                                onChange={(e) => setConfirmPassword(e.target.value)}
                                placeholder="••••••••"
                                className="w-full bg-slate-50 dark:bg-[#121827]/30 border border-slate-200 dark:border-[#2b3346] text-slate-900 dark:text-white rounded-xl py-3 px-4 focus:outline-none focus:ring-2 focus:ring-graphito-blue/50 focus:border-graphito-blue transition-all placeholder:text-slate-400 dark:placeholder:text-slate-600 text-sm tracking-widest font-mono"
                            />
                            <div className="absolute inset-y-0 right-0 pr-4 flex items-center text-graphito-blue">
                                <Check size={16} strokeWidth={3} />
                            </div>
                        </div>
                    </div>

                    {/* Terms checkbox */}
                    <div className="flex items-center gap-3 pt-1">
                        <input
                            type="checkbox"
                            id="terms"
                            checked={agreed}
                            onChange={(e) => setAgreed(e.target.checked)}
                            className="w-4 h-4 rounded border-slate-300 dark:border-[#2b3346] bg-slate-50 dark:bg-[#121827]/50 text-graphito-blue focus:ring-2 focus:ring-graphito-blue/50 focus:outline-none"
                        />
                        <label htmlFor="terms" className="text-[11px] font-medium text-slate-600 dark:text-slate-400">
                            Acepto los <button type="button" className="text-slate-800 dark:text-slate-300 underline">Términos de uso</button> y la <button type="button" className="text-slate-800 dark:text-slate-300 underline">Política de privacidad</button>
                        </label>
                    </div>

                    {/* Submit */}
                    <button
                        type="submit"
                        disabled={isLoading}
                        className="w-full bg-gradient-to-r from-graphito-blue to-graphito-violet text-white font-bold rounded-xl py-3.5 mt-2 hover:opacity-90 transition-opacity shadow-lg shadow-graphito-blue/20 text-sm flex items-center justify-center gap-2 disabled:opacity-50"
                    >
                        {isLoading ? (
                            <>
                                <Loader2 className="w-4 h-4 animate-spin" />
                                <span>Creando cuenta...</span>
                            </>
                        ) : (
                            <span>Crear mi cuenta</span>
                        )}
                    </button>
                </form>

                {/* Footer text */}
                <div className="mt-6 text-center">
                    <p className="text-[12px] text-slate-600 dark:text-slate-400 font-medium">
                        ¿Ya tienes una cuenta? <button onClick={onNavigateToLogin} className="text-slate-900 dark:text-white hover:text-graphito-blue dark:hover:text-graphito-violet font-bold transition-colors ml-1">Iniciar sesión</button>
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