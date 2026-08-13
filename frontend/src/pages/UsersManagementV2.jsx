import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
    AlertTriangle,
    Check,
    Eye,
    EyeOff,
    KeyRound,
    LoaderCircle,
    Pencil,
    Plus,
    Power,
    RefreshCw,
    Search,
    Shield,
    UserCheck,
    Users,
    X,
} from 'lucide-react';
import { apiFetch, apiJson, readApiError } from '../utils/apiClient';

const ROLE_OPTIONS = [
    { code: 'TI_ADMIN', name: 'Administrador TI', minLevel: 3 },
    { code: 'FUNC_ADMIN', name: 'Administrador funcional', minLevel: 2 },
    { code: 'DATA_OWNER', name: 'Responsable de datos', minLevel: 3 },
    { code: 'STEWARD', name: 'Custodio de datos', minLevel: 2 },
    { code: 'ANALYST', name: 'Analista', minLevel: 2 },
    { code: 'DIRECTIVE', name: 'Directivo', minLevel: 2 },
    { code: 'SOURCE_UPLOADER', name: 'Carga de fuentes', minLevel: 2 },
    { code: 'PORTAL_EDITOR', name: 'Editor del portal', minLevel: 1 },
    { code: 'PORTAL_ADMIN', name: 'Administrador del portal', minLevel: 2 },
];

const EMPTY_FORM = {
    username: '',
    email: '',
    password: '',
    full_name: '',
    dependency: '',
    position: '',
    data_level_max: 2,
    role_codes: ['ANALYST'],
};

const ROLE_NAMES = Object.fromEntries(ROLE_OPTIONS.map((role) => [role.code, role.name]));

const generateTemporaryPassword = () => {
    const random = new Uint32Array(12);
    crypto.getRandomValues(random);
    const alphabet = 'ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789!@#$%';
    const middle = Array.from(random, (value) => alphabet[value % alphabet.length]).join('');
    return `SisC!${middle}9a`;
};

const formatDate = (value) => {
    if (!value) return 'Nunca';
    return new Intl.DateTimeFormat('es-CO', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value));
};

const UsersManagement = ({ userRoles = [], currentUser }) => {
    const canManage = userRoles.includes('TI_ADMIN');
    const [users, setUsers] = useState([]);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState('');
    const [notice, setNotice] = useState('');
    const [query, setQuery] = useState('');
    const [statusFilter, setStatusFilter] = useState('all');
    const [editor, setEditor] = useState(null);
    const [form, setForm] = useState(EMPTY_FORM);
    const [showPassword, setShowPassword] = useState(false);
    const [resetUser, setResetUser] = useState(null);
    const [temporaryPassword, setTemporaryPassword] = useState('');
    const [statusUser, setStatusUser] = useState(null);

    const loadUsers = useCallback(async () => {
        setLoading(true);
        setError('');
        try {
            const data = await apiJson('/users/');
            setUsers(Array.isArray(data) ? data : []);
        } catch (requestError) {
            setError(requestError.message || 'No fue posible cargar los usuarios.');
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        loadUsers();
    }, [loadUsers]);

    const filteredUsers = useMemo(() => {
        const needle = query.trim().toLowerCase();
        return users.filter((user) => {
            const matchesStatus = statusFilter === 'all'
                || (statusFilter === 'active' ? user.is_active : !user.is_active);
            const haystack = [user.full_name, user.username, user.email, user.dependency, user.position]
                .filter(Boolean)
                .join(' ')
                .toLowerCase();
            return matchesStatus && (!needle || haystack.includes(needle));
        });
    }, [query, statusFilter, users]);

    const stats = useMemo(() => ({
        total: users.length,
        active: users.filter((user) => user.is_active).length,
        restricted: users.filter((user) => user.data_level_max === 3 && user.is_active).length,
        admins: users.filter((user) => user.is_active && user.roles?.some((role) => role.code === 'TI_ADMIN')).length,
    }), [users]);

    const openCreate = () => {
        setForm(EMPTY_FORM);
        setEditor({ mode: 'create' });
        setShowPassword(false);
        setError('');
    };

    const openEdit = (user) => {
        setForm({
            username: user.username || '',
            email: user.email || '',
            password: '',
            full_name: user.full_name || '',
            dependency: user.dependency || '',
            position: user.position || '',
            data_level_max: user.data_level_max || 1,
            role_codes: user.roles?.map((role) => role.code) || [],
        });
        setEditor({ mode: 'edit', user });
        setError('');
    };

    const toggleRole = (role) => {
        const selected = form.role_codes.includes(role.code);
        const roleCodes = selected
            ? form.role_codes.filter((code) => code !== role.code)
            : [...form.role_codes, role.code];
        setForm((current) => ({
            ...current,
            role_codes: roleCodes,
            data_level_max: selected ? current.data_level_max : Math.max(current.data_level_max, role.minLevel),
        }));
    };

    const submitUser = async (event) => {
        event.preventDefault();
        setSaving(true);
        setError('');
        setNotice('');
        try {
            const isCreate = editor?.mode === 'create';
            const payload = isCreate ? form : {
                email: form.email,
                full_name: form.full_name,
                dependency: form.dependency,
                position: form.position,
                data_level_max: form.data_level_max,
                role_codes: form.role_codes,
            };
            const response = await apiFetch(isCreate ? '/users/' : `/users/${editor.user.id}`, {
                method: isCreate ? 'POST' : 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload),
            });
            if (!response.ok) throw new Error(await readApiError(response));
            setEditor(null);
            setNotice(isCreate ? 'Usuario creado correctamente.' : 'Permisos y perfil actualizados.');
            await loadUsers();
        } catch (requestError) {
            setError(requestError.message || 'No fue posible guardar el usuario.');
        } finally {
            setSaving(false);
        }
    };

    const updateStatus = async () => {
        if (!statusUser) return;
        setSaving(true);
        setError('');
        try {
            const response = await apiFetch(`/users/${statusUser.id}/status`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ is_active: !statusUser.is_active }),
            });
            if (!response.ok) throw new Error(await readApiError(response));
            setNotice(statusUser.is_active ? 'Acceso suspendido y sesiones cerradas.' : 'Cuenta reactivada.');
            setStatusUser(null);
            await loadUsers();
        } catch (requestError) {
            setError(requestError.message || 'No fue posible cambiar el estado.');
        } finally {
            setSaving(false);
        }
    };

    const resetPassword = async (event) => {
        event.preventDefault();
        setSaving(true);
        setError('');
        try {
            const response = await apiFetch(`/users/${resetUser.id}/reset-password`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ temporary_password: temporaryPassword }),
            });
            if (!response.ok) throw new Error(await readApiError(response));
            setNotice('Contraseña temporal actualizada; las sesiones anteriores fueron cerradas.');
            setResetUser(null);
        } catch (requestError) {
            setError(requestError.message || 'No fue posible restablecer la contraseña.');
        } finally {
            setSaving(false);
        }
    };

    const openPasswordReset = (user) => {
        setResetUser(user);
        setTemporaryPassword(generateTemporaryPassword());
        setShowPassword(false);
        setError('');
    };

    return (
        <div className="max-w-[1500px] mx-auto space-y-6 pb-12">
            <header className="flex flex-col lg:flex-row lg:items-end justify-between gap-4">
                <div>
                    <p className="text-xs font-bold uppercase text-primary mb-1">Administración y trazabilidad</p>
                    <h2 className="text-2xl md:text-3xl font-black text-slate-900">Gestión de usuarios</h2>
                    <p className="text-sm text-slate-500 mt-1">Cuentas institucionales, roles y niveles de acceso.</p>
                </div>
                {canManage && (
                    <button onClick={openCreate} className="inline-flex items-center justify-center gap-2 bg-primary text-white px-4 py-2.5 rounded-lg font-bold text-sm shadow-sm hover:bg-primary-secondary">
                        <Plus size={18} /> Crear usuario
                    </button>
                )}
            </header>

            <section className="grid grid-cols-2 xl:grid-cols-4 gap-3" aria-label="Resumen de usuarios">
                {[
                    ['Cuentas', stats.total, Users, 'text-primary bg-primary/5'],
                    ['Activas', stats.active, UserCheck, 'text-emerald-700 bg-emerald-50'],
                    ['Acceso N3', stats.restricted, Shield, 'text-amber-700 bg-amber-50'],
                    ['Admin TI', stats.admins, KeyRound, 'text-slate-700 bg-slate-100'],
                ].map(([label, value, Icon, color]) => (
                    <div key={label} className="bg-white border border-slate-200 rounded-lg p-4 flex items-center justify-between min-w-0">
                        <div><p className="text-[11px] font-bold uppercase text-slate-500">{label}</p><p className="text-2xl font-black text-slate-900">{value}</p></div>
                        <div className={`p-2 rounded-lg ${color}`}><Icon size={20} /></div>
                    </div>
                ))}
            </section>

            {!canManage && (
                <div className="flex items-start gap-3 bg-blue-50 border border-blue-100 text-blue-900 rounded-lg p-4 text-sm">
                    <Shield size={18} className="mt-0.5 shrink-0" />
                    Su perfil puede consultar cuentas. La creación, edición y suspensión corresponden a Administración TI.
                </div>
            )}
            {(error || notice) && (
                <div className={`flex items-start gap-3 rounded-lg p-4 text-sm border ${error ? 'bg-red-50 border-red-100 text-red-800' : 'bg-emerald-50 border-emerald-100 text-emerald-800'}`}>
                    {error ? <AlertTriangle size={18} className="shrink-0" /> : <Check size={18} className="shrink-0" />}
                    <span className="flex-1">{error || notice}</span>
                    <button onClick={() => { setError(''); setNotice(''); }} aria-label="Cerrar mensaje"><X size={16} /></button>
                </div>
            )}

            <section className="bg-white border border-slate-200 rounded-lg overflow-hidden">
                <div className="p-4 border-b border-slate-200 flex flex-col md:flex-row gap-3 md:items-center md:justify-between">
                    <div className="relative flex-1 max-w-xl">
                        <Search size={17} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                        <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Buscar por nombre, usuario, correo o dependencia" className="w-full pl-10 pr-3 py-2.5 border border-slate-200 rounded-lg text-sm outline-none focus:border-primary" />
                    </div>
                    <div className="flex items-center gap-2">
                        <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)} className="border border-slate-200 rounded-lg px-3 py-2.5 text-sm bg-white">
                            <option value="all">Todos los estados</option>
                            <option value="active">Activos</option>
                            <option value="inactive">Inactivos</option>
                        </select>
                        <button onClick={loadUsers} aria-label="Actualizar usuarios" title="Actualizar" className="p-2.5 border border-slate-200 rounded-lg text-slate-600 hover:text-primary">
                            <RefreshCw size={17} className={loading ? 'animate-spin' : ''} />
                        </button>
                    </div>
                </div>

                <div className="divide-y divide-slate-100 lg:hidden">
                    {loading ? (
                        <div className="p-10 text-center text-slate-500"><LoaderCircle className="animate-spin inline mr-2" size={18} />Cargando usuarios...</div>
                    ) : filteredUsers.length === 0 ? (
                        <div className="p-10 text-center text-slate-500">No hay usuarios que coincidan con la búsqueda.</div>
                    ) : filteredUsers.map((user) => (
                        <article key={user.id} className="p-4 space-y-3">
                            <div className="flex items-start justify-between gap-3">
                                <div className="min-w-0">
                                    <h3 className="font-bold text-slate-900 break-words">{user.full_name || user.username}</h3>
                                    <p className="text-xs text-slate-500 break-all">@{user.username} · {user.email}</p>
                                </div>
                                <span className={`shrink-0 inline-flex items-center gap-1.5 text-xs font-bold ${user.is_active ? 'text-emerald-700' : 'text-slate-500'}`}>
                                    <span className={`w-2 h-2 rounded-full ${user.is_active ? 'bg-emerald-500' : 'bg-slate-300'}`} />
                                    {user.is_active ? 'Activo' : 'Inactivo'}
                                </span>
                            </div>
                            <div className="grid grid-cols-2 gap-3 text-xs">
                                <div className="min-w-0">
                                    <p className="font-bold uppercase text-[10px] text-slate-400">Dependencia</p>
                                    <p className="font-semibold text-slate-700 break-words">{user.dependency || 'Sin dependencia'}</p>
                                    <p className="text-slate-500 break-words">{user.position || 'Sin cargo'}</p>
                                </div>
                                <div>
                                    <p className="font-bold uppercase text-[10px] text-slate-400">Último ingreso</p>
                                    <p className="text-slate-600">{formatDate(user.last_login_at)}</p>
                                </div>
                            </div>
                            <div className="flex items-center gap-1.5 flex-wrap">
                                <span className="px-2 py-1 rounded bg-slate-900 text-white text-[10px] font-bold">N{user.data_level_max}</span>
                                {user.roles?.map((role) => <span key={role.code} title={role.code} className="px-2 py-1 rounded bg-primary/5 text-primary text-[10px] font-bold">{ROLE_NAMES[role.code] || role.name || role.code}</span>)}
                            </div>
                            {canManage && (
                                <div className="flex justify-end gap-1 pt-1">
                                    <button onClick={() => openEdit(user)} aria-label={`Editar ${user.username}`} title="Editar perfil y permisos" className="p-2.5 rounded-lg text-slate-600 hover:text-primary hover:bg-primary/5"><Pencil size={18} /></button>
                                    <button onClick={() => openPasswordReset(user)} aria-label={`Restablecer contraseña de ${user.username}`} title="Restablecer contraseña" className="p-2.5 rounded-lg text-slate-600 hover:text-amber-700 hover:bg-amber-50"><KeyRound size={18} /></button>
                                    <button disabled={user.id === currentUser?.id} onClick={() => setStatusUser(user)} aria-label={`${user.is_active ? 'Desactivar' : 'Activar'} ${user.username}`} title={user.id === currentUser?.id ? 'No puede desactivar su propia cuenta' : user.is_active ? 'Desactivar cuenta' : 'Activar cuenta'} className="p-2.5 rounded-lg text-slate-600 hover:text-red-700 hover:bg-red-50 disabled:opacity-30 disabled:cursor-not-allowed"><Power size={18} /></button>
                                </div>
                            )}
                        </article>
                    ))}
                </div>

                <div className="hidden lg:block overflow-x-auto">
                    <table className="w-full min-w-[980px] text-left">
                        <thead className="bg-slate-50 text-[11px] uppercase text-slate-500">
                            <tr>
                                <th className="px-5 py-3 font-bold">Usuario</th>
                                <th className="px-5 py-3 font-bold">Dependencia</th>
                                <th className="px-5 py-3 font-bold">Acceso</th>
                                <th className="px-5 py-3 font-bold">Último ingreso</th>
                                <th className="px-5 py-3 font-bold">Estado</th>
                                <th className="px-5 py-3 font-bold text-right">Acciones</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-100">
                            {loading ? (
                                <tr><td colSpan="6" className="p-12 text-center text-slate-500"><LoaderCircle className="animate-spin inline mr-2" size={18} />Cargando usuarios...</td></tr>
                            ) : filteredUsers.length === 0 ? (
                                <tr><td colSpan="6" className="p-12 text-center text-slate-500">No hay usuarios que coincidan con la búsqueda.</td></tr>
                            ) : filteredUsers.map((user) => (
                                <tr key={user.id} className="hover:bg-slate-50/70">
                                    <td className="px-5 py-4">
                                        <p className="font-bold text-slate-900">{user.full_name || user.username}</p>
                                        <p className="text-xs text-slate-500">@{user.username} · {user.email}</p>
                                    </td>
                                    <td className="px-5 py-4"><p className="text-sm font-semibold text-slate-700">{user.dependency || 'Sin dependencia'}</p><p className="text-xs text-slate-500">{user.position || 'Sin cargo'}</p></td>
                                    <td className="px-5 py-4">
                                        <div className="flex items-center gap-1.5 flex-wrap">
                                            <span className="px-2 py-1 rounded bg-slate-900 text-white text-[10px] font-bold">N{user.data_level_max}</span>
                                            {user.roles?.map((role) => <span key={role.code} title={role.code} className="px-2 py-1 rounded bg-primary/5 text-primary text-[10px] font-bold">{ROLE_NAMES[role.code] || role.name || role.code}</span>)}
                                        </div>
                                    </td>
                                    <td className="px-5 py-4 text-xs text-slate-600">{formatDate(user.last_login_at)}</td>
                                    <td className="px-5 py-4"><span className={`inline-flex items-center gap-1.5 text-xs font-bold ${user.is_active ? 'text-emerald-700' : 'text-slate-500'}`}><span className={`w-2 h-2 rounded-full ${user.is_active ? 'bg-emerald-500' : 'bg-slate-300'}`} />{user.is_active ? 'Activo' : 'Inactivo'}</span></td>
                                    <td className="px-5 py-4">
                                        {canManage && (
                                            <div className="flex justify-end gap-1">
                                                <button onClick={() => openEdit(user)} aria-label={`Editar ${user.username}`} title="Editar perfil y permisos" className="p-2 rounded-lg text-slate-500 hover:text-primary hover:bg-primary/5"><Pencil size={17} /></button>
                                                <button onClick={() => openPasswordReset(user)} aria-label={`Restablecer contraseña de ${user.username}`} title="Restablecer contraseña" className="p-2 rounded-lg text-slate-500 hover:text-amber-700 hover:bg-amber-50"><KeyRound size={17} /></button>
                                                <button disabled={user.id === currentUser?.id} onClick={() => setStatusUser(user)} aria-label={`${user.is_active ? 'Desactivar' : 'Activar'} ${user.username}`} title={user.id === currentUser?.id ? 'No puede desactivar su propia cuenta' : user.is_active ? 'Desactivar cuenta' : 'Activar cuenta'} className="p-2 rounded-lg text-slate-500 hover:text-red-700 hover:bg-red-50 disabled:opacity-30 disabled:cursor-not-allowed"><Power size={17} /></button>
                                            </div>
                                        )}
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            </section>

            {editor && (
                <div className="fixed inset-0 z-50 bg-slate-950/50 flex items-center justify-center p-4" role="dialog" aria-modal="true">
                    <div className="bg-white rounded-lg shadow-2xl w-full max-w-3xl max-h-[92vh] overflow-y-auto">
                        <div className="sticky top-0 bg-white border-b border-slate-200 px-6 py-4 flex items-center justify-between z-10">
                            <div><h3 className="text-xl font-black text-slate-900">{editor.mode === 'create' ? 'Crear usuario' : 'Editar usuario'}</h3><p className="text-sm text-slate-500">Defina identidad, dependencia y acceso mínimo necesario.</p></div>
                            <button onClick={() => setEditor(null)} aria-label="Cerrar" className="p-2 rounded-lg hover:bg-slate-100"><X size={20} /></button>
                        </div>
                        <form onSubmit={submitUser} className="p-6 space-y-6">
                            <div className="grid md:grid-cols-2 gap-4">
                                {editor.mode === 'create' && <label className="text-sm font-bold text-slate-700">Usuario<input required minLength="3" value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value })} className="mt-1 w-full border border-slate-200 rounded-lg px-3 py-2.5 font-normal" placeholder="nombre.apellido" /></label>}
                                <label className="text-sm font-bold text-slate-700">Nombre completo<input required value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} className="mt-1 w-full border border-slate-200 rounded-lg px-3 py-2.5 font-normal" /></label>
                                <label className="text-sm font-bold text-slate-700">Correo institucional<input required type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} className="mt-1 w-full border border-slate-200 rounded-lg px-3 py-2.5 font-normal" /></label>
                                {editor.mode === 'create' && <label className="text-sm font-bold text-slate-700">Contraseña inicial<div className="relative mt-1"><input required minLength="12" type={showPassword ? 'text' : 'password'} value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} className="w-full border border-slate-200 rounded-lg px-3 py-2.5 pr-11 font-normal" /><button type="button" onClick={() => setShowPassword(!showPassword)} aria-label="Mostrar u ocultar contraseña" className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500">{showPassword ? <EyeOff size={18} /> : <Eye size={18} />}</button></div></label>}
                                <label className="text-sm font-bold text-slate-700">Dependencia<input value={form.dependency} onChange={(e) => setForm({ ...form, dependency: e.target.value })} className="mt-1 w-full border border-slate-200 rounded-lg px-3 py-2.5 font-normal" /></label>
                                <label className="text-sm font-bold text-slate-700">Cargo<input value={form.position} onChange={(e) => setForm({ ...form, position: e.target.value })} className="mt-1 w-full border border-slate-200 rounded-lg px-3 py-2.5 font-normal" /></label>
                                <label className="text-sm font-bold text-slate-700">Nivel máximo<select value={form.data_level_max} onChange={(e) => setForm({ ...form, data_level_max: Number(e.target.value) })} className="mt-1 w-full border border-slate-200 rounded-lg px-3 py-2.5 bg-white font-normal"><option value="1">N1 · Público</option><option value="2">N2 · Institucional</option><option value="3">N3 · Restringido</option></select></label>
                            </div>
                            <fieldset><legend className="text-sm font-bold text-slate-700 mb-3">Roles</legend><div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-2">{ROLE_OPTIONS.map((role) => <label key={role.code} className={`flex items-start gap-3 border rounded-lg p-3 cursor-pointer ${form.role_codes.includes(role.code) ? 'border-primary bg-primary/5' : 'border-slate-200'}`}><input type="checkbox" checked={form.role_codes.includes(role.code)} onChange={() => toggleRole(role)} className="mt-0.5 accent-[#281FD0]" /><span><span className="block text-sm font-bold text-slate-800">{role.name}</span><span className="block text-[10px] text-slate-500">Requiere N{role.minLevel}</span></span></label>)}</div></fieldset>
                            <div className="flex justify-end gap-3 border-t border-slate-200 pt-4"><button type="button" onClick={() => setEditor(null)} className="px-4 py-2.5 rounded-lg border border-slate-200 font-bold text-sm">Cancelar</button><button disabled={saving} className="px-4 py-2.5 rounded-lg bg-primary text-white font-bold text-sm inline-flex items-center gap-2 disabled:opacity-60">{saving && <LoaderCircle size={17} className="animate-spin" />}{editor.mode === 'create' ? 'Crear usuario' : 'Guardar cambios'}</button></div>
                        </form>
                    </div>
                </div>
            )}

            {resetUser && (
                <div className="fixed inset-0 z-50 bg-slate-950/50 flex items-center justify-center p-4" role="dialog" aria-modal="true">
                    <form onSubmit={resetPassword} className="bg-white rounded-lg shadow-2xl w-full max-w-lg p-6 space-y-5">
                        <div className="flex items-start justify-between"><div><h3 className="text-xl font-black text-slate-900">Restablecer contraseña</h3><p className="text-sm text-slate-500 mt-1">Cuenta: {resetUser.full_name || resetUser.username}</p></div><button type="button" onClick={() => setResetUser(null)} aria-label="Cerrar"><X size={20} /></button></div>
                        <label className="text-sm font-bold text-slate-700">Contraseña temporal<div className="relative mt-1"><input required minLength="12" type={showPassword ? 'text' : 'password'} value={temporaryPassword} onChange={(e) => setTemporaryPassword(e.target.value)} className="w-full border border-slate-200 rounded-lg px-3 py-2.5 pr-11 font-mono font-normal" /><button type="button" onClick={() => setShowPassword(!showPassword)} aria-label="Mostrar u ocultar contraseña" className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500">{showPassword ? <EyeOff size={18} /> : <Eye size={18} />}</button></div></label>
                        <p className="text-xs text-amber-800 bg-amber-50 border border-amber-100 rounded-lg p-3">Al confirmar se cerrarán las sesiones anteriores. Comparta esta clave únicamente por un canal institucional seguro.</p>
                        <div className="flex justify-end gap-3"><button type="button" onClick={() => setTemporaryPassword(generateTemporaryPassword())} className="px-3 py-2.5 rounded-lg border border-slate-200 font-bold text-sm">Generar otra</button><button disabled={saving} className="px-4 py-2.5 rounded-lg bg-primary text-white font-bold text-sm">Restablecer</button></div>
                    </form>
                </div>
            )}

            {statusUser && (
                <div className="fixed inset-0 z-50 bg-slate-950/50 flex items-center justify-center p-4" role="dialog" aria-modal="true">
                    <div className="bg-white rounded-lg shadow-2xl w-full max-w-md p-6">
                        <div className={`w-11 h-11 rounded-lg flex items-center justify-center mb-4 ${statusUser.is_active ? 'bg-red-50 text-red-700' : 'bg-emerald-50 text-emerald-700'}`}><Power size={22} /></div>
                        <h3 className="text-xl font-black text-slate-900">{statusUser.is_active ? 'Desactivar cuenta' : 'Reactivar cuenta'}</h3>
                        <p className="text-sm text-slate-600 mt-2">{statusUser.is_active ? 'Se cerrará su acceso inmediatamente y se invalidarán las sesiones existentes.' : 'La persona podrá volver a ingresar con sus roles actuales.'}</p>
                        <div className="flex justify-end gap-3 mt-6"><button onClick={() => setStatusUser(null)} className="px-4 py-2.5 rounded-lg border border-slate-200 font-bold text-sm">Cancelar</button><button disabled={saving} onClick={updateStatus} className={`px-4 py-2.5 rounded-lg text-white font-bold text-sm ${statusUser.is_active ? 'bg-red-700' : 'bg-emerald-700'}`}>{statusUser.is_active ? 'Desactivar' : 'Reactivar'}</button></div>
                    </div>
                </div>
            )}
        </div>
    );
};

export default UsersManagement;
