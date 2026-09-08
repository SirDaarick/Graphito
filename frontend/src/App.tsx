import { useState, useEffect } from "react";
import { Header } from "./components/layout/Header";
import { Biblioteca } from "./pages/Biblioteca";
import { Login } from "./pages/Login";
import { Register } from "./pages/Register";
import { MouseGlowBackground } from "./components/layout/MouseGlowBackground";
import { NewReferenceModal } from "./pages/NewReferenceModal";
import { NewComparisonModal } from "./pages/NewComparisonModal";
import { SimilarityReportModal } from "./pages/SimilarityReportModal";
import { api, Docente } from "./lib/api";

type View = "login" | "register" | "app";

function App() {
    const [view, setView] = useState<View>("login");
    const [currentUser, setCurrentUser] = useState<Docente | null>(null);
    const [isCheckingAuth, setIsCheckingAuth] = useState(true);
    const [isNewCodeModalOpen, setIsNewCodeModalOpen] = useState(false);
    const [isNewComparisonModalOpen, setIsNewComparisonModalOpen] = useState(false);
    const [selectedComparison, setSelectedComparison] = useState<any>(null);
    const [isSimilarityReportOpen, setIsSimilarityReportOpen] = useState(false);
    const [refreshKey, setRefreshKey] = useState(0);

    useEffect(() => {
        const verifySession = async () => {
            if (api.auth.isAuthenticated()) {
                try {
                    const user = await api.auth.me();
                    setCurrentUser(user);
                    setView("app");
                } catch {
                    api.auth.logout();
                    setView("login");
                }
            } else {
                setView("login");
            }
            setIsCheckingAuth(false);
        };
        verifySession();
    }, []);

    const handleLogin = async () => {
        try {
            const user = await api.auth.me();
            setCurrentUser(user);
        } catch {
            // ok
        }
        setView("app");
    };

    const handleLogout = () => {
        api.auth.logout();
        setCurrentUser(null);
        setView("login");
    };

    const handleRegister = async () => {
        await handleLogin();
    };

    const navigateToRegister = () => setView("register");
    const navigateToLogin = () => setView("login");

    if (isCheckingAuth) {
        return (
            <MouseGlowBackground>
                <div className="flex h-screen items-center justify-center text-slate-300 font-medium text-sm">
                    Cargando Graphito...
                </div>
            </MouseGlowBackground>
        );
    }

    return (
        <MouseGlowBackground>
            {/* Skip link for keyboard navigation */}
            <a
                href="#main-content"
                className="sr-only focus:not-sr-only focus:absolute focus:top-4 focus:left-4 focus:z-50 focus:px-4 focus:py-2 focus:bg-graphito-blue focus:text-white focus:rounded-lg focus:font-bold"
            >
                Saltar al contenido principal
            </a>

            {view === "app" ? (
                <>
                    <Header
                        onNewCode={() => setIsNewCodeModalOpen(true)}
                        onLogout={handleLogout}
                        onViewComparison={(comp) => {
                            setSelectedComparison(comp);
                            setIsSimilarityReportOpen(true);
                        }}
                    />
                    <Biblioteca
                        key={refreshKey}
                        onCompare={() => setIsNewComparisonModalOpen(true)}
                        onComparisonClick={(comp) => {
                            setSelectedComparison(comp);
                            setIsSimilarityReportOpen(true);
                        }}
                    />
                    <NewReferenceModal
                        isOpen={isNewCodeModalOpen}
                        onClose={() => {
                            setIsNewCodeModalOpen(false);
                            setRefreshKey((prev) => prev + 1);
                        }}
                    />
                    <NewComparisonModal
                        isOpen={isNewComparisonModalOpen}
                        onClose={() => {
                            setIsNewComparisonModalOpen(false);
                            setRefreshKey((prev) => prev + 1);
                        }}
                        onAnalysisComplete={(report) => {
                            setSelectedComparison(report);
                            setIsSimilarityReportOpen(true);
                        }}
                    />
                    <SimilarityReportModal
                        isOpen={isSimilarityReportOpen}
                        onClose={() => setIsSimilarityReportOpen(false)}
                        comparison={selectedComparison}
                    />
                </>
            ) : view === "register" ? (
                <Register
                    onRegister={handleRegister}
                    onNavigateToLogin={navigateToLogin}
                />
            ) : (
                <Login
                    onLogin={handleLogin}
                    onNavigateToRegister={navigateToRegister}
                />
            )}
        </MouseGlowBackground>
    );
}

export default App;
