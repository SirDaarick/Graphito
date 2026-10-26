import { useState, useEffect } from "react";
import { Header, AppSection } from "./components/layout/Header";
import { Biblioteca } from "./pages/Biblioteca";
import { Catalogo } from "./pages/Catalogo";
import { Login } from "./pages/Login";
import { Register } from "./pages/Register";
import { MouseGlowBackground } from "./components/layout/MouseGlowBackground";
import { NewReferenceModal } from "./pages/NewReferenceModal";
import { NewComparisonModal } from "./pages/NewComparisonModal";
import { SimilarityReportModal } from "./pages/SimilarityReportModal";
import { api, Docente, IS_DEMO_MODE, invalidateLibrary } from "./lib/api";
import { toComparison } from "./lib/dictamen";
import { navigate, usePath, useRouteMatch, getInitialRoute } from "./lib/router";

type View = "login" | "register" | "app";

function App() {
    const path = usePath();
    const reportMatch = useRouteMatch("/reporte/:id");

    const [currentUser, setCurrentUser] = useState<Docente | null>(null);
    const [isCheckingAuth, setIsCheckingAuth] = useState(true);
    const [isNewCodeModalOpen, setIsNewCodeModalOpen] = useState(false);
    const [isNewComparisonModalOpen, setIsNewComparisonModalOpen] = useState(false);
    const [comparisonTargetProblem, setComparisonTargetProblem] = useState<{ id: number; title: string; lenguaje?: string } | null>(null);
    const [selectedComparison, setSelectedComparison] = useState<any>(null);
    const [comparisonList, setComparisonList] = useState<any[]>([]);
    const [section, setSection] = useState<AppSection>(path === "/catalogo" ? "catalogo" : "biblioteca");

    // Keep section in sync with URL
    useEffect(() => {
        if (path === "/catalogo") {
            setSection("catalogo");
        } else if (path === "/biblioteca" || path === "/") {
            setSection("biblioteca");
        }
    }, [path]);

    // Verify session on mount
    useEffect(() => {
        const verifySession = async () => {
            if (IS_DEMO_MODE) {
                try {
                    const demoUser = await api.auth.me();
                    setCurrentUser(demoUser);
                } catch {
                    // demo fallback
                }
                const initial = getInitialRoute(true);
                if (window.location.pathname === "/" || !window.location.pathname) {
                    navigate(initial, { replace: true });
                }
                setIsCheckingAuth(false);
                return;
            }

            if (api.auth.isAuthenticated()) {
                try {
                    const user = await api.auth.me();
                    setCurrentUser(user);
                    const initial = getInitialRoute(true);
                    if (window.location.pathname === "/" || window.location.pathname === "/login" || window.location.pathname === "/register") {
                        navigate(initial, { replace: true });
                    }
                } catch {
                    api.auth.logout();
                    setCurrentUser(null);
                    navigate("/login", { replace: true });
                }
            } else {
                if (window.location.pathname !== "/login" && window.location.pathname !== "/register") {
                    navigate("/login", { replace: true });
                }
            }
            setIsCheckingAuth(false);
        };
        verifySession();
    }, []);

    // Deep linking support for /reporte/:id
    const activeReportId = reportMatch.isMatch ? reportMatch.params.id : null;
    useEffect(() => {
        if (activeReportId) {
            const idNum = Number(activeReportId);
            if (!Number.isNaN(idNum) && (!selectedComparison || String(selectedComparison.id) !== String(activeReportId))) {
                let cancelled = false;
                api.analysis
                    .getReport(idNum)
                    .then((report) => {
                        if (cancelled) return;
                        const comp = toComparison(report, `Reporte #${report.id}`);
                        setSelectedComparison(comp);
                        setComparisonList((prev) =>
                            prev.length > 0 && prev.some((c) => String(c.id) === String(report.id))
                                ? prev
                                : [comp]
                        );
                    })
                    .catch((err) => {
                        if (cancelled) return;
                        console.warn("No se pudo cargar el reporte referenciado por URL:", err);
                    });
                return () => {
                    cancelled = true;
                };
            }
        }
    }, [activeReportId, selectedComparison]);

    const handleLogin = async () => {
        try {
            const user = await api.auth.me();
            setCurrentUser(user);
        } catch {
            // ok
        }
        navigate("/biblioteca");
    };

    const handleLogout = () => {
        api.auth.logout();
        setCurrentUser(null);
        navigate("/login");
    };

    const handleRegister = async () => {
        await handleLogin();
    };

    const navigateToRegister = () => navigate("/register");
    const navigateToLogin = () => navigate("/login");

    const handleOpenComparison = (comp: any, allComps?: any[]) => {
        setSelectedComparison(comp);
        setComparisonList(allComps && allComps.length > 0 ? allComps : [comp]);
        if (comp?.id) {
            navigate(`/reporte/${comp.id}`, { state: { fromGraphito: true } });
        }
    };

    const handleCloseReportModal = () => {
        const fallback = section === "catalogo" ? "/catalogo" : "/biblioteca";
        if (typeof window !== "undefined" && window.history.state?.fromGraphito) {
            window.history.back();
        } else {
            navigate(fallback);
        }
    };

    if (isCheckingAuth) {
        return (
            <MouseGlowBackground>
                <div className="flex h-screen items-center justify-center text-slate-600 dark:text-slate-300 font-medium text-sm">
                    Cargando Graphito...
                </div>
            </MouseGlowBackground>
        );
    }

    // Determine current view from route and auth status
    const isAuth = Boolean(currentUser) || (IS_DEMO_MODE ? true : api.auth.isAuthenticated());
    let currentView: View = "app";
    if (!isAuth) {
        currentView = path === "/register" ? "register" : "login";
    } else {
        if (path === "/login") {
            currentView = "login";
        } else if (path === "/register") {
            currentView = "register";
        } else {
            currentView = "app";
        }
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

            {currentView === "app" ? (
                <>
                    <Header
                        currentUser={currentUser}
                        onNewCode={() => setIsNewCodeModalOpen(true)}
                        onLogout={handleLogout}
                        activeSection={section}
                        onNavigate={(newSection) => {
                            setSection(newSection);
                            navigate(newSection === "catalogo" ? "/catalogo" : "/biblioteca");
                        }}
                        onViewComparison={(comp) => handleOpenComparison(comp, [comp])}
                    />
                    {section === "biblioteca" ? (
                        <Biblioteca
                            onCompare={(target) => {
                                setComparisonTargetProblem(target);
                                setIsNewComparisonModalOpen(true);
                            }}
                            onGoToCatalog={() => {
                                setSection("catalogo");
                                navigate("/catalogo");
                            }}
                            onComparisonClick={(comp, allComps) => handleOpenComparison(comp, allComps)}
                        />
                    ) : (
                        <Catalogo
                            onProgramAdded={() => invalidateLibrary()}
                            onGoToBiblioteca={() => {
                                setSection("biblioteca");
                                navigate("/biblioteca");
                            }}
                        />
                    )}
                    <NewReferenceModal
                        isOpen={isNewCodeModalOpen}
                        onClose={() => setIsNewCodeModalOpen(false)}
                        onSuccess={() => invalidateLibrary()}
                    />
                    <NewComparisonModal
                        isOpen={isNewComparisonModalOpen}
                        onClose={() => {
                            setIsNewComparisonModalOpen(false);
                            setComparisonTargetProblem(null);
                        }}
                        preselectedProblem={comparisonTargetProblem}
                        onAnalysisComplete={(report) => {
                            const comp = toComparison(report, `Reporte #${report.id}`);
                            handleOpenComparison(comp, [comp]);
                            invalidateLibrary();
                        }}
                    />
                    <SimilarityReportModal
                        isOpen={reportMatch.isMatch}
                        onClose={handleCloseReportModal}
                        comparison={selectedComparison}
                        submissions={comparisonList}
                        onSelectComparison={(comp) => {
                            setSelectedComparison(comp);
                            if (comp?.id) {
                                navigate(`/reporte/${comp.id}`, { replace: true, state: { fromGraphito: true } });
                            }
                        }}
                    />
                </>
            ) : currentView === "register" ? (
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
