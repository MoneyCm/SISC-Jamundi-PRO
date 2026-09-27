import { useEffect, useRef, useState } from 'react';
import { Bell, User, Search, Menu, ShieldCheck, LogOut, MonitorSmartphone, ChevronDown, Loader2 } from 'lucide-react';
import { pageLabel } from '../utils/pageLabels';
import { apiFetch, readApiError } from '../utils/apiClient';

const LegacyHeader = ({ onMenuClick, isPublic }) => {
    // In public mode, we only show a very minimal header for mobile menu access
    // if needed, or hide it completely on desktop.
    if (isPublic) {
        return (
            <header className="md:hidden bg-white border-b border-slate-100 h-16 flex items-center justify-between px-4 z-10 sticky top-0">
                <div className="flex items-center space-x-4">
                    <button
                        onClick={onMenuClick}
                        className="p-2 -ml-2 text-slate-600 hover:bg-slate-50 rounded-lg transition-colors"
                    >
                        <Menu size={24} />
                    </button>
                    <span className="font-bold text-primary">SISC Jamundí</span>
                </div>
            </header>
        );
    }

    return (
        <header className="bg-white border-b border-slate-100 h-16 flex items-center justify-between px-4 md:px-8 z-10 sticky top-0">
            <div className="flex items-center space-x-4">
                <button
                    onClick={onMenuClick}
                    className="p-2 -ml-2 text-slate-600 hover:bg-slate-50 rounded-lg md:hidden transition-colors"
                >
                    <Menu size={24} />
                </button>

                <div className="hidden sm:flex items-center bg-slate-50 rounded-full px-4 py-2 w-64 lg:w-96 border border-slate-100">
                    <Search size={18} className="text-slate-400 mr-2" />
                    <input
                        type="text"
                        placeholder="Buscar reportes..."
                        className="bg-transparent border-none outline-none text-sm text-slate-700 w-full placeholder-slate-400"
                    />
                </div>
            </div>

            <div className="flex items-center space-x-6">
                <button className="relative text-slate-400 hover:text-primary transition-colors">
                    <Bell size={20} />
                    <span className="absolute -top-1 -right-1 bg-accent text-white text-[10px] w-4 h-4 rounded-full flex items-center justify-center font-bold">3</span>
                </button>

                <div className="flex items-center space-x-3 pl-6 border-l border-slate-100">
                    <div className="text-right hidden md:block">
                        <p className="text-sm font-bold text-primary leading-none">Alcaldía de Jamundí</p>
                        <p className="text-[10px] text-slate-400 uppercase font-black tracking-tighter">Valle del Cauca</p>
                    </div>
                    <div className="w-10 h-10 bg-primary/5 rounded-full flex items-center justify-center text-primary border border-primary/10">
                        <User size={20} />
                    </div>
                </div>
            </div>
        </header>
    );
};

// Los nombres de página vienen de utils/pageLabels.js (los mismos de la barra lateral).

const ROLE_LABELS = {
    TI_ADMIN: 'Administración TI',
    FUNC_ADMIN: 'Administración funcional',
    DATA_OWNER: 'Responsable de datos',
    DIRECTIVE: 'Perfil directivo',
    ANALYST: 'Perfil analista',
    SOURCE_UPLOADER: 'Carga de fuentes',
};

// Menú de la cuenta: cerrar la sesión en este equipo o en todos los dispositivos de la persona.
const UserMenu = ({ currentUser, displayName, primaryRole, onLogout }) => {
    const [open, setOpen] = useState(false);
    const [confirming, setConfirming] = useState(false);
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState('');
    const ref = useRef(null);

    useEffect(() => {
        if (!open) return undefined;
        const close = (event) => {
            if (event.type === 'keydown' ? event.key === 'Escape' : !ref.current?.contains(event.target)) {
                setOpen(false);
                setConfirming(false);
            }
        };
        document.addEventListener('mousedown', close);
        document.addEventListener('keydown', close);
        return () => {
            document.removeEventListener('mousedown', close);
            document.removeEventListener('keydown', close);
        };
    }, [open]);

    const logoutEverywhere = async () => {
        setBusy(true);
        setError('');
        try {
            const response = await apiFetch('/users/me/revoke-sessions', { method: 'POST' });
            if (!response.ok) throw new Error(await readApiError(response));
            onLogout?.();
        } catch (requestError) {
            setError(requestError.message || 'No fue posible cerrar las sesiones.');
            setBusy(false);
        }
    };

    return (
        <div className="relative" ref={ref}>
            <button onClick={() => { setOpen((value) => !value); setConfirming(false); setError(''); }}
                aria-haspopup="menu" aria-expanded={open} aria-label="Menú de la cuenta"
                className="flex items-center gap-3 pl-4 border-l border-slate-200 min-w-0 rounded-lg py-1 hover:bg-slate-50">
                <div className="hidden sm:block text-right min-w-0">
                    <p className="text-sm font-bold text-slate-800 truncate max-w-56">{displayName}</p>
                    <p className="text-[10px] text-slate-500 font-semibold truncate max-w-56">
                        {ROLE_LABELS[primaryRole] || currentUser?.dependency || 'Acceso institucional'} · N{currentUser?.data_level_max || 1}
                    </p>
                </div>
                <div className="w-9 h-9 bg-primary/5 rounded-full flex items-center justify-center text-primary border border-primary/10" title={displayName}>
                    {primaryRole?.includes('ADMIN') ? <ShieldCheck size={18} /> : <User size={18} />}
                </div>
                <ChevronDown size={16} className="text-slate-400" aria-hidden="true" />
            </button>
            {open && (
                <div role="menu" className="absolute right-0 mt-2 w-72 rounded-lg border border-slate-200 bg-white p-2 shadow-xl z-30">
                    <div className="px-3 py-2 border-b border-slate-100 mb-1">
                        <p className="text-sm font-black text-slate-900 truncate">{displayName}</p>
                        <p className="text-xs text-slate-500 truncate">{currentUser?.username}</p>
                    </div>
                    <button role="menuitem" onClick={() => onLogout?.()} className="flex w-full items-center gap-3 rounded-md px-3 py-2.5 text-left text-sm font-bold text-slate-700 hover:bg-slate-50">
                        <LogOut size={17} /> Cerrar sesión
                    </button>
                    {!confirming ? (
                        <button role="menuitem" onClick={() => setConfirming(true)} className="flex w-full items-center gap-3 rounded-md px-3 py-2.5 text-left text-sm font-bold text-slate-700 hover:bg-orange-50 hover:text-orange-800">
                            <MonitorSmartphone size={17} /> Cerrar sesión en todos mis dispositivos
                        </button>
                    ) : (
                        <div className="rounded-md bg-orange-50 p-3 text-sm">
                            <p className="font-semibold text-orange-900">Se cerrará su sesión en el celular, en este equipo y en cualquier otro donde haya ingresado. Úselo si perdió un dispositivo.</p>
                            {error && <p role="alert" className="mt-2 font-bold text-red-700">{error}</p>}
                            <div className="mt-3 flex justify-end gap-2">
                                <button onClick={() => setConfirming(false)} className="rounded-md border border-slate-200 bg-white px-3 py-1.5 font-bold text-slate-700">Cancelar</button>
                                <button disabled={busy} onClick={logoutEverywhere} className="inline-flex items-center gap-2 rounded-md bg-orange-700 px-3 py-1.5 font-bold text-white disabled:opacity-60">
                                    {busy && <Loader2 size={14} className="animate-spin" />} Cerrar todas
                                </button>
                            </div>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
};

const Header = ({ onMenuClick, isPublic, currentUser, activePage, onLogout }) => {
    if (isPublic) return <LegacyHeader onMenuClick={onMenuClick} isPublic />;

    const primaryRole = currentUser?.roles?.[0];
    const displayName = currentUser?.full_name || currentUser?.username || 'Usuario institucional';

    return (
        <header className="bg-white border-b border-slate-200 min-h-16 flex items-center justify-between gap-4 px-4 md:px-8 z-10 sticky top-0">
            <div className="flex items-center gap-3 min-w-0">
                <button onClick={onMenuClick} aria-label="Abrir navegación" className="p-2 -ml-2 text-slate-600 hover:bg-slate-50 rounded-lg md:hidden">
                    <Menu size={24} />
                </button>
                <div className="min-w-0">
                    <p className="text-[10px] font-bold uppercase text-slate-400">Centro de mando SISC</p>
                    <h1 className="text-sm md:text-base font-black text-slate-800 truncate">{pageLabel(activePage)}</h1>
                </div>
            </div>

            <UserMenu currentUser={currentUser} displayName={displayName} primaryRole={primaryRole} onLogout={onLogout} />
        </header>
    );
};

export default Header;
