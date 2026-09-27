import { useEffect, useRef, useState } from 'react';
import { Bell, User, Search, Menu, ShieldCheck, LogOut, MonitorSmartphone, ChevronDown, Loader2, KeyRound, Eye, EyeOff, X, CheckCircle2 } from 'lucide-react';
import { pageLabel } from '../utils/pageLabels';
import { apiFetch, readApiError } from '../utils/apiClient';
import { passwordIssues } from '../utils/passwordPolicy';

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

// Cambio de la contraseña propia. Al cambiarla se cierran todas las sesiones, también esta.
const ChangePasswordDialog = ({ username, onClose, onDone }) => {
    const [form, setForm] = useState({ current: '', next: '', confirm: '' });
    const [show, setShow] = useState(false);
    const [touched, setTouched] = useState(false);
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState('');
    const [done, setDone] = useState(false);
    const issues = passwordIssues({ ...form, username });
    const field = (key) => ({
        value: form[key],
        onChange: (event) => { setForm({ ...form, [key]: event.target.value }); setError(''); },
        type: show ? 'text' : 'password',
        className: 'mt-1 block w-full rounded-md border border-slate-300 px-3 py-2 text-sm',
    });

    const submit = async (event) => {
        event.preventDefault();
        setTouched(true);
        if (issues.length) return;
        setBusy(true);
        setError('');
        try {
            const response = await apiFetch('/users/me/password', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ current_password: form.current, new_password: form.next }),
            });
            if (!response.ok) throw new Error(await readApiError(response));
            setDone(true);
        } catch (requestError) {
            setError(requestError.message || 'No fue posible cambiar la contraseña.');
        } finally {
            setBusy(false);
        }
    };

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/50 p-4" role="dialog" aria-modal="true" aria-labelledby="change-password-title">
            <div className="w-full max-w-md rounded-lg bg-white p-6 shadow-2xl">
                {done ? (
                    <div className="text-center">
                        <CheckCircle2 size={40} className="mx-auto text-emerald-600" />
                        <h3 id="change-password-title" className="mt-3 text-xl font-black text-slate-900">Contraseña actualizada</h3>
                        <p className="mt-2 text-sm text-slate-600">Por seguridad se cerraron todas sus sesiones. Ingrese de nuevo con la contraseña nueva.</p>
                        <button onClick={() => onDone?.()} className="mt-5 rounded-md bg-primary px-4 py-2.5 text-sm font-bold text-white">Ir al ingreso</button>
                    </div>
                ) : (
                    <form onSubmit={submit} noValidate>
                        <div className="flex items-start justify-between">
                            <h3 id="change-password-title" className="text-xl font-black text-slate-900">Cambiar mi contraseña</h3>
                            <button type="button" onClick={onClose} aria-label="Cerrar"><X size={20} /></button>
                        </div>
                        <p className="mt-1 text-sm text-slate-500">Al cambiarla se cerrará su sesión en todos sus dispositivos.</p>
                        <div className="mt-4 space-y-3">
                            <label className="block text-xs font-bold text-slate-600">Contraseña actual
                                <input autoComplete="current-password" autoFocus {...field('current')} />
                            </label>
                            <label className="block text-xs font-bold text-slate-600">Contraseña nueva
                                <input autoComplete="new-password" {...field('next')} />
                            </label>
                            <label className="block text-xs font-bold text-slate-600">Repita la contraseña nueva
                                <input autoComplete="new-password" {...field('confirm')} />
                            </label>
                            <button type="button" onClick={() => setShow((value) => !value)} className="inline-flex items-center gap-2 text-xs font-bold text-slate-600">
                                {show ? <EyeOff size={15} /> : <Eye size={15} />} {show ? 'Ocultar' : 'Mostrar'} contraseñas
                            </button>
                        </div>
                        <p className="mt-3 text-xs text-slate-500">Mínimo 12 caracteres, con al menos tres de estos: mayúsculas, minúsculas, números o símbolos. No puede contener su usuario.</p>
                        {touched && issues.length > 0 && (
                            <ul role="alert" className="mt-3 list-disc space-y-1 rounded-md bg-amber-50 p-3 pl-7 text-sm font-semibold text-amber-900">
                                {issues.map((issue) => <li key={issue}>{issue}</li>)}
                            </ul>
                        )}
                        {error && <p role="alert" className="mt-3 rounded-md bg-red-50 p-3 text-sm font-bold text-red-800">{error}</p>}
                        <div className="mt-5 flex justify-end gap-3">
                            <button type="button" onClick={onClose} className="rounded-md border border-slate-200 px-4 py-2.5 text-sm font-bold">Cancelar</button>
                            <button disabled={busy} className="inline-flex items-center gap-2 rounded-md bg-primary px-4 py-2.5 text-sm font-bold text-white disabled:opacity-60">
                                {busy && <Loader2 size={15} className="animate-spin" />} Cambiar contraseña
                            </button>
                        </div>
                    </form>
                )}
            </div>
        </div>
    );
};

// Menú de la cuenta: cerrar la sesión en este equipo o en todos los dispositivos de la persona.
const UserMenu = ({ currentUser, displayName, primaryRole, onLogout }) => {
    const [open, setOpen] = useState(false);
    const [confirming, setConfirming] = useState(false);
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState('');
    const [changing, setChanging] = useState(false);
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
                    <button role="menuitem" onClick={() => { setOpen(false); setChanging(true); }} className="flex w-full items-center gap-3 rounded-md px-3 py-2.5 text-left text-sm font-bold text-slate-700 hover:bg-slate-50">
                        <KeyRound size={17} /> Cambiar mi contraseña
                    </button>
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
            {changing && <ChangePasswordDialog username={currentUser?.username} onClose={() => setChanging(false)} onDone={onLogout} />}
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
