import { useState, useEffect } from "react";
import { Header } from "./components/layout/Header";
import { Biblioteca } from "./pages/Biblioteca";
import { Login } from "./pages/Login";
import { Register } from "./pages/Register";
import { MouseGlowBackground } from "./components/layout/MouseGlowBackground";
import { NewReferenceModal } from "./pages/NewReferenceModal";
import { NewComparisonModal } from "./pages/NewComparisonModal";
import { SimilarityReportModal } from "./pages/SimilarityReportModal";
import { api, Docente, IS_DEMO_MODE } from "./lib/api";

type View = "login" | "register" | "app";

function App() {
    const [view, setView] = useState<View>(IS_DEMO_MODE ? "app" : "login");
    const [currentUser, setCurrentUser] = useState<Docente | null>(null);
    const [isCheckingAuth, setIsCheckingAuth] = useState(true);
    const [isNewCodeModalOpen, setIsNewCodeModalOpen] = useState(false);
    const [isNewComparisonModalOpen, setIsNewComparisonModalOpen] = useState(false);
    const [selectedComparison, setSelectedComparison] = useState<any>(null);
    const [comparisonList, setComparisonList] = useState<any[]>([]);
    const [isSimilarityReportOpen, setIsSimilarityReportOpen] = useState(false);
    const [refreshTrigger, setRefreshTrigger] = useState(0);

    useEffect(() => {
        const verifySession = async () => {
            if (IS_DEMO_MODE) {
                try {
                    const demoUser = await api.auth.me();
                    setCurrentUser(demoUser);
                    setView("app");
                } catch {
                    // fallback
                }
                setIsCheckingAuth(false);
                return;
            }

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
                <div className="flex h-screen items-center justify-center text-slate-600 dark:text-slate-300 font-medium text-sm">
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
                            currentUser={currentUser}
                            onNewCode={() => setIsNewCodeModalOpen(true)}
                            onLogout={handleLogout}
                            onViewComparison={(comp) => {
                                setSelectedComparison(comp);
                                setComparisonList([comp]);
                                setIsSimilarityReportOpen(true);
                            }}
                        />
                        <Biblioteca
                            refreshTrigger={refreshTrigger}
                            onCompare={() => setIsNewComparisonModalOpen(true)}
                            onComparisonClick={(comp, allComps) => {
                                setSelectedComparison(comp);
                                setComparisonList(allComps && allComps.length > 0 ? allComps : [comp]);
                                setIsSimilarityReportOpen(true);
                            }}
                        />
                        <NewReferenceModal
                            isOpen={isNewCodeModalOpen}
                            onClose={() => setIsNewCodeModalOpen(false)}
                            onSuccess={() => setRefreshTrigger((prev) => prev + 1)}
                        />
                        <NewComparisonModal
                            isOpen={isNewComparisonModalOpen}
                            onClose={() => setIsNewComparisonModalOpen(false)}
                            onAnalysisComplete={(report) => {
                                setSelectedComparison(report);
                                setComparisonList([report]);
                                setIsSimilarityReportOpen(true);
                                setRefreshTrigger((prev) => prev + 1);
                            }}
                        />
                        <SimilarityReportModal
                            isOpen={isSimilarityReportOpen}
                            onClose={() => setIsSimilarityReportOpen(false)}
                            comparison={selectedComparison}
                            submissions={comparisonList}
                            onSelectComparison={(comp) => setSelectedComparison(comp)}
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