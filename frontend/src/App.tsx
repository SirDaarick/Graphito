import { useState } from "react";
import { Header } from "./components/layout/Header";
import { Biblioteca } from "./pages/Biblioteca";
import { Login } from "./pages/Login";
import { Register } from "./pages/Register";
import { MouseGlowBackground } from "./components/layout/MouseGlowBackground";
import { NewReferenceModal } from "./pages/NewReferenceModal";
import { NewComparisonModal } from "./pages/NewComparisonModal";

import { SimilarityReportModal } from "./pages/SimilarityReportModal";

type View = "login" | "register" | "app";

function App() {
    const [view, setView] = useState<View>("login");
    const [isNewCodeModalOpen, setIsNewCodeModalOpen] = useState(false);
    const [isNewComparisonModalOpen, setIsNewComparisonModalOpen] = useState(false);
    const [selectedComparison, setSelectedComparison] = useState<any>(null);
    const [isSimilarityReportOpen, setIsSimilarityReportOpen] = useState(false);

    const handleLogin = () => setView("app");
    const handleRegister = () => setView("app");
    const navigateToRegister = () => setView("register");
    const navigateToLogin = () => setView("login");

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
                    <Header onNewCode={() => setIsNewCodeModalOpen(true)} />
                    <Biblioteca
                        onCompare={() => setIsNewComparisonModalOpen(true)}
                        onComparisonClick={(comp) => {
                            setSelectedComparison(comp);
                            setIsSimilarityReportOpen(true);
                        }}
                    />
                    <NewReferenceModal
                        isOpen={isNewCodeModalOpen}
                        onClose={() => setIsNewCodeModalOpen(false)}
                    />
                    <NewComparisonModal
                        isOpen={isNewComparisonModalOpen}
                        onClose={() => setIsNewComparisonModalOpen(false)}
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
