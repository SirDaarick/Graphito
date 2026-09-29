# Guía de Implementación 08: Navegación Ágil (Avance Automático & Atajos de Teclado)

## 1. Fundamentos & Filosofía de Arquitectura
En el diseño de interfaces de alta productividad (*High-Throughput Review Interfaces*), la **Ley de Fitts** y la **minimización de la carga cognitiva** son determinantes.

Si un profesor califica 40 entregas y para cada una debe:
1. Abrir el modal de reporte,
2. Revisar las métricas y el código,
3. Emitir el dictamen,
4. Cerrar el modal,
5. Hacer scroll en la biblioteca buscando al siguiente alumno...

El usuario realiza más de **240 interacciones mecánicas redundantes**.

La solución es una **arquitectura de Cola de Revisión Secuencial (Review Carousel / Queue)** con:
* Avance automático suave al siguiente elemento tras emitir dictamen.
* Transiciones fluidas asistidas por GSAP.
* Soporte de **atajos de teclado (Keyboard Shortcuts)** para revisión rápida.

---

## 2. Impacto en el Sistema
* **Frontend (React + GSAP):**
  * Modificación de `SimilarityReportModal.tsx`:
    * Recibir la lista completa de entregas `comparisons: ComparisonData[]` y el índice activo `currentIndex: number`.
    * Control de navegación: `goToNext()`, `goToPrev()`.
    * Efecto de transición visual (slide / cross-fade con GSAP).
    * Hook para escuchar eventos de teclado (`keydown`: `A` -> Aceptar, `D` -> Duda, `R` -> Rechazar, flechas).
* **Backend:** Sin impacto directo (utiliza el endpoint de veredicto de la Guía 07).

---

## 3. Especificación Técnica Detallada

### 3.1. Estado de la Cola en `SimilarityReportModal.tsx`
```tsx
interface FastReviewModalProps {
  isOpen: boolean;
  onClose: () => void;
  submissions: ComparisonData[];
  initialIndex?: number;
  onUpdateVerdict: (id: string | number, verdict: "APROBADO" | "RECHAZADO" | "EN_DUDA") => Promise<void>;
}

export function FastReviewModal({
  isOpen,
  onClose,
  submissions,
  initialIndex = 0,
  onUpdateVerdict
}: FastReviewModalProps) {
  const [currentIndex, setCurrentIndex] = useState(initialIndex);
  const [isTransitioning, setIsTransitioning] = useState(false);
  const cardContainerRef = useRef<HTMLDivElement>(null);

  const currentItem = submissions[currentIndex];
  const hasNext = currentIndex < submissions.length - 1;
  const hasPrev = currentIndex > 0;

  const navigateTo = (newIndex: number) => {
    if (newIndex < 0 || newIndex >= submissions.length || isTransitioning) return;
    
    setIsTransitioning(true);
    gsap.to(cardContainerRef.current, {
      opacity: 0,
      x: -20,
      duration: 0.2,
      onComplete: () => {
        setCurrentIndex(newIndex);
        gsap.fromTo(
          cardContainerRef.current,
          { opacity: 0, x: 20 },
          { opacity: 1, x: 0, duration: 0.25, onComplete: () => setIsTransitioning(false) }
        );
      }
    });
  };

  const handleVerdictAndAdvance = async (verdict: "APROBADO" | "RECHAZADO" | "EN_DUDA") => {
    if (!currentItem?.id) return;
    await onUpdateVerdict(currentItem.id, verdict);
    
    if (hasNext) {
      navigateTo(currentIndex + 1);
    } else {
      onClose();
    }
  };

  useEffect(() => {
    if (!isOpen) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (["INPUT", "TEXTAREA"].includes((e.target as HTMLElement).tagName)) return;

      if (e.key === "a" || e.key === "A") handleVerdictAndAdvance("APROBADO");
      if (e.key === "d" || e.key === "D") handleVerdictAndAdvance("EN_DUDA");
      if (e.key === "r" || e.key === "R") handleVerdictAndAdvance("RECHAZADO");
      if (e.key === "ArrowRight") navigateTo(currentIndex + 1);
      if (e.key === "ArrowLeft") navigateTo(currentIndex - 1);
      if (e.key === "Escape") onClose();
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, currentIndex, hasNext, currentItem]);

  return (
    <div className="modal-container">
      <div className="flex justify-between items-center pb-4 border-b border-line-subtle">
        <span className="text-xs uppercase font-mono text-content-muted">
          Revisando {currentIndex + 1} de {submissions.length} — Alumno: {currentItem.title}
        </span>
        <div className="flex gap-2">
          <button onClick={() => navigateTo(currentIndex - 1)} disabled={!hasPrev}>Anterior</button>
          <button onClick={() => navigateTo(currentIndex + 1)} disabled={!hasNext}>Siguiente</button>
        </div>
      </div>

      <div ref={cardContainerRef} className="py-4">
        {/* Contenido del reporte, diff de código y métricas */}
      </div>

      <TriageBar
        currentDecision={currentItem.decision || "PENDIENTE"}
        onSelectVerdict={handleVerdictAndAdvance}
      />
    </div>
  );
}
```

---

## 4. Criterios de Aceptación y Pruebas
1. Al pulsar `[Aceptar]`, `[Duda]` o `[Rechazar]`, la decisión se persiste y la vista transiciona inmediatamente a la siguiente entrega sin cerrar el modal.
2. Los atajos de teclado (`A`, `D`, `R`, flechas) funcionan correctamente.
