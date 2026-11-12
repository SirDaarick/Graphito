import { useEffect, useState } from "react";
import { Loader2, Upload, CheckCircle2 } from "lucide-react";
import { Modal } from "../ui/Modal";
import { GradientButton } from "../ui/GradientButton";
import { api, MyCatalog } from "../../lib/api";

const inputClass =
    "w-full bg-slate-50 dark:bg-[#121827]/40 border border-slate-200 dark:border-[#2b3346] text-slate-900 dark:text-white placeholder:text-slate-400 dark:placeholder:text-slate-600 rounded-xl py-3 px-4 text-sm focus:outline-none focus:border-graphito-blue transition-colors";
const labelClass = "text-[10px] uppercase font-black tracking-widest text-slate-500 dark:text-slate-400";

function ErrorBox({ message }: { message: string | null }) {
    if (!message) return null;
    return (
        <div className="p-3 bg-red-500/10 border border-red-500/30 rounded-xl text-red-600 dark:text-red-300 text-xs font-medium">
            {message}
        </div>
    );
}

function Footer({
    onClose,
    onSubmit,
    busy,
    disabled,
    label,
}: {
    onClose: () => void;
    onSubmit: () => void;
    busy: boolean;
    disabled?: boolean;
    label: string;
}) {
    return (
        <div className="flex items-center justify-end gap-6">
            <button
                type="button"
                onClick={onClose}
                disabled={busy}
                className="text-sm font-bold text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white rounded-lg px-4 py-2 disabled:opacity-50"
            >
                Cancelar
            </button>
            <GradientButton onClick={onSubmit} disabled={busy || disabled} className="!py-3 !px-8 disabled:opacity-50">
                <div className="flex items-center gap-2">
                    {busy && <Loader2 size={16} className="animate-spin" />}
                    <span>{label}</span>
                </div>
            </GradientButton>
        </div>
    );
}

interface NewCatalogModalProps {
    isOpen: boolean;
    onClose: () => void;
    onCreated: (catalog: MyCatalog) => void;
}

export function NewCatalogModal({ isOpen, onClose, onCreated }: NewCatalogModalProps) {
    const [nombre, setNombre] = useState("");
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        if (isOpen) {
            setNombre("");
            setError(null);
        }
    }, [isOpen]);

    const submit = async () => {
        if (!nombre.trim() || busy) return;
        setBusy(true);
        setError(null);
        try {
            onCreated(await api.myCatalogs.create(nombre.trim()));
            onClose();
        } catch (err: any) {
            setError(err.message || "No se pudo crear el catálogo.");
        } finally {
            setBusy(false);
        }
    };

    return (
        <Modal
            isOpen={isOpen}
            onClose={onClose}
            maxWidth="sm"
            title="Nuevo catálogo"
            description="Una colección privada de programas para reutilizar."
            bodyClassName="space-y-4"
            footer={<Footer onClose={onClose} onSubmit={submit} busy={busy} disabled={!nombre.trim()} label="Crear catálogo" />}
        >
            <ErrorBox message={error} />
            <div className="space-y-1.5">
                <label htmlFor="my-catalog-name" className={labelClass}>
                    Nombre
                </label>
                <input
                    id="my-catalog-name"
                    type="text"
                    value={nombre}
                    maxLength={150}
                    onChange={(e) => setNombre(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && submit()}
                    placeholder="Ej. Mis problemas de arreglos"
                    className={inputClass}
                    disabled={busy}
                    autoFocus
                />
            </div>
        </Modal>
    );
}

interface AddProgramModalProps {
    isOpen: boolean;
    catalog: { id: number; nombre: string } | null;
    onClose: () => void;
    onAdded: () => void;
}

export function AddProgramModal({ isOpen, catalog, onClose, onAdded }: AddProgramModalProps) {
    const [titulo, setTitulo] = useState("");
    const [enunciado, setEnunciado] = useState("");
    const [lenguaje, setLenguaje] = useState<"c" | "cpp">("c");
    const [codigo, setCodigo] = useState("");
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        if (isOpen) {
            setTitulo("");
            setEnunciado("");
            setLenguaje("c");
            setCodigo("");
            setError(null);
        }
    }, [isOpen]);

    const loadFile = async (file?: File) => {
        if (!file) return;
        setCodigo(await file.text());
        setLenguaje(/\.(cpp|cc|cxx|hpp)$/i.test(file.name) ? "cpp" : "c");
        if (!titulo.trim()) setTitulo(file.name.replace(/\.[^.]+$/, ""));
    };

    const canSubmit = Boolean(titulo.trim() && codigo.trim());

    const submit = async () => {
        if (!catalog || !canSubmit || busy) return;
        setBusy(true);
        setError(null);
        try {
            await api.myCatalogs.addProgram(catalog.id, { titulo: titulo.trim(), enunciado, lenguaje, codigo });
            onAdded();
            onClose();
        } catch (err: any) {
            setError(err.message || "No se pudo agregar el programa.");
        } finally {
            setBusy(false);
        }
    };

    return (
        <Modal
            isOpen={isOpen}
            onClose={onClose}
            maxWidth="2xl"
            title="Agregar programa"
            description={catalog ? `Se guardará en “${catalog.nombre}”.` : undefined}
            bodyClassName="space-y-4"
            footer={<Footer onClose={onClose} onSubmit={submit} busy={busy} disabled={!canSubmit} label="Guardar programa" />}
        >
            <ErrorBox message={error} />
            <div className="grid grid-cols-3 gap-3">
                <div className="col-span-2 space-y-1.5">
                    <label htmlFor="my-prog-title" className={labelClass}>
                        Título
                    </label>
                    <input
                        id="my-prog-title"
                        type="text"
                        value={titulo}
                        maxLength={255}
                        onChange={(e) => setTitulo(e.target.value)}
                        placeholder="Ej. Búsqueda binaria"
                        className={inputClass}
                        disabled={busy}
                    />
                </div>
                <div className="space-y-1.5">
                    <label htmlFor="my-prog-lang" className={labelClass}>
                        Lenguaje
                    </label>
                    <select
                        id="my-prog-lang"
                        value={lenguaje}
                        onChange={(e) => setLenguaje(e.target.value as "c" | "cpp")}
                        className={inputClass}
                        disabled={busy}
                    >
                        <option value="c">C</option>
                        <option value="cpp">C++</option>
                    </select>
                </div>
            </div>
            <div className="space-y-1.5">
                <label htmlFor="my-prog-statement" className={labelClass}>
                    Enunciado (opcional)
                </label>
                <textarea
                    id="my-prog-statement"
                    value={enunciado}
                    onChange={(e) => setEnunciado(e.target.value)}
                    rows={3}
                    placeholder="Qué debe resolver el programa"
                    className={`${inputClass} resize-none`}
                    disabled={busy}
                />
            </div>
            <div className="space-y-1.5">
                <div className="flex items-center justify-between">
                    <label htmlFor="my-prog-code" className={labelClass}>
                        Código de referencia
                    </label>
                    <label className="flex items-center gap-1.5 text-xs font-bold text-graphito-blue cursor-pointer hover:underline">
                        <Upload size={13} />
                        Cargar archivo
                        <input
                            type="file"
                            accept=".c,.cpp,.cc,.cxx,.h,.hpp,text/plain"
                            className="sr-only"
                            onChange={(e) => {
                                loadFile(e.target.files?.[0]);
                                e.target.value = "";
                            }}
                        />
                    </label>
                </div>
                <textarea
                    id="my-prog-code"
                    value={codigo}
                    onChange={(e) => setCodigo(e.target.value)}
                    rows={10}
                    spellCheck={false}
                    placeholder="Pega aquí tu solución de referencia"
                    className={`${inputClass} font-mono text-xs resize-y`}
                    disabled={busy}
                />
            </div>
        </Modal>
    );
}

interface SaveToCatalogModalProps {
    isOpen: boolean;
    problem: { id: number; title: string } | null;
    onClose: () => void;
}

const NEW = "new";

export function SaveToCatalogModal({ isOpen, problem, onClose }: SaveToCatalogModalProps) {
    const [catalogs, setCatalogs] = useState<MyCatalog[]>([]);
    const [choice, setChoice] = useState<number | typeof NEW>(NEW);
    const [newName, setNewName] = useState("");
    const [loading, setLoading] = useState(false);
    const [busy, setBusy] = useState(false);
    const [savedIn, setSavedIn] = useState<string | null>(null);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        if (!isOpen) return;
        setSavedIn(null);
        setError(null);
        setNewName("");
        setLoading(true);
        let cancelled = false;
        api.myCatalogs
            .list()
            .then((list) => {
                if (cancelled) return;
                setCatalogs(list);
                setChoice(list.length > 0 ? list[0].id : NEW);
            })
            .catch((err: any) => !cancelled && setError(err.message || "No se pudieron cargar tus catálogos."))
            .finally(() => !cancelled && setLoading(false));
        return () => {
            cancelled = true;
        };
    }, [isOpen]);

    const canSubmit = choice !== NEW || newName.trim().length > 0;

    const submit = async () => {
        if (!problem || !canSubmit || busy) return;
        setBusy(true);
        setError(null);
        try {
            let target = catalogs.find((c) => c.id === choice);
            if (!target) {
                target = await api.myCatalogs.create(newName.trim());
                setCatalogs((prev) => [...prev, target!]);
                setChoice(target.id);
            }
            await api.myCatalogs.saveProblem(target.id, problem.id);
            setSavedIn(target.nombre);
        } catch (err: any) {
            setError(err.message || "No se pudo guardar el programa en el catálogo.");
        } finally {
            setBusy(false);
        }
    };

    return (
        <Modal
            isOpen={isOpen}
            onClose={onClose}
            maxWidth="md"
            title="Guardar en catálogo"
            description={problem ? `“${problem.title}” se copia al catálogo con su código de referencia y sus variantes IA, y queda guardado aunque lo borres de la biblioteca.` : undefined}
            bodyClassName="space-y-4"
            footer={
                savedIn ? (
                    <div className="flex justify-end">
                        <GradientButton onClick={onClose} className="!py-3 !px-8">
                            <span>Cerrar</span>
                        </GradientButton>
                    </div>
                ) : (
                    <Footer onClose={onClose} onSubmit={submit} busy={busy} disabled={loading || !canSubmit} label="Guardar" />
                )
            }
        >
            <ErrorBox message={error} />
            {savedIn ? (
                <div role="status" className="flex items-center gap-2 p-3 bg-emerald-500/10 border border-emerald-500/30 rounded-xl text-emerald-700 dark:text-emerald-300 text-sm font-bold">
                    <CheckCircle2 size={18} className="shrink-0" />
                    Guardado en “{savedIn}”
                </div>
            ) : loading ? (
                <div className="flex justify-center py-8">
                    <Loader2 className="w-6 h-6 animate-spin text-graphito-blue" />
                </div>
            ) : (
                <fieldset className="space-y-2" disabled={busy}>
                    <legend className={`${labelClass} mb-2`}>Catálogo</legend>
                    {catalogs.map((c) => (
                        <label key={c.id} className="flex items-center gap-3 p-3 rounded-xl border border-slate-200 dark:border-[#2b3346] cursor-pointer text-sm text-slate-800 dark:text-slate-100">
                            <input type="radio" name="catalog" checked={choice === c.id} onChange={() => setChoice(c.id)} />
                            <span className="flex-1 truncate">{c.nombre}</span>
                            <span className="text-xs text-slate-500">{c.programas.length}</span>
                        </label>
                    ))}
                    <label className="flex items-center gap-3 p-3 rounded-xl border border-slate-200 dark:border-[#2b3346] cursor-pointer text-sm text-slate-800 dark:text-slate-100">
                        <input type="radio" name="catalog" checked={choice === NEW} onChange={() => setChoice(NEW)} />
                        <span>Nuevo catálogo</span>
                    </label>
                    {choice === NEW && (
                        <input
                            type="text"
                            value={newName}
                            maxLength={150}
                            onChange={(e) => setNewName(e.target.value)}
                            placeholder="Nombre del catálogo"
                            aria-label="Nombre del nuevo catálogo"
                            className={inputClass}
                            autoFocus
                        />
                    )}
                </fieldset>
            )}
        </Modal>
    );
}
