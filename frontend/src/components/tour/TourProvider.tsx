import { useEffect, useMemo, useReducer, useState, type ReactNode } from "react";
import { INITIAL_TOUR_STATE, tourReducer } from "../../lib/tour/machine";
import { usePath } from "../../lib/router";
import { TourContext, type TourApi } from "./TourContext";
import { TourChooser } from "./TourChooser";
import { TourOverlay } from "./TourOverlay";

const SEEN_KEY = "graphito_tour_seen";

function readSeen(): boolean {
    try {
        return localStorage.getItem(SEEN_KEY) === "1";
    } catch {
        return false;
    }
}

function writeSeen(): void {
    try {
        localStorage.setItem(SEEN_KEY, "1");
    } catch {
        // Private mode or blocked storage: the hint just shows again next time.
    }
}

export function TourProvider({ children }: { children: ReactNode }) {
    const [state, dispatch] = useReducer(tourReducer, INITIAL_TOUR_STATE);
    const [hasSeen, setHasSeen] = useState(readSeen);
    const path = usePath();

    // The guide only makes sense inside the app: leave it on logout.
    useEffect(() => {
        if (state.status !== "idle" && (path === "/login" || path === "/register")) {
            dispatch({ type: "exit" });
        }
    }, [path, state.status]);

    const api = useMemo<TourApi>(
        () => ({
            state,
            hasSeen,
            open: () => {
                writeSeen();
                setHasSeen(true);
                dispatch({ type: "open" });
            },
            exit: () => dispatch({ type: "exit" }),
            choose: (flow) => dispatch({ type: "choose", flow }),
            next: (from) => dispatch({ type: "next", from }),
            back: () => dispatch({ type: "back" }),
            goTo: (stepId) => dispatch({ type: "goTo", stepId }),
            setProblem: (problemId) => dispatch({ type: "setProblem", problemId }),
        }),
        [state, hasSeen]
    );

    return (
        <TourContext.Provider value={api}>
            {children}
            <TourChooser />
            <TourOverlay />
        </TourContext.Provider>
    );
}
