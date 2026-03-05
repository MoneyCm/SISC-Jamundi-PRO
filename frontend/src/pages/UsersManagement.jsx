import React, { useState, useEffect } from 'react';
import { User, Shield, Key, Mail, Building, Plus, Trash2, CheckCircle2, AlertTriangle, ShieldCheck } from 'lucide-react';
import { API_BASE_URL } from '../utils/apiConfig';

const UsersManagement = () => {
    const [users, setUsers] = useState([]);
    const [loading, setLoading] = useState(true);
    const [showModal, setShowModal] = useState(false);
    const [newUser, setNewUser] = useState({
        username: '',
        email: '',
        password: '',
        full_name: '',
        dependency: '',
        position: '',
        data_level_max: 1,
        role_codes: ['ANALYST']
    });

    const rolesList = [
        { code: 'TI_ADMIN', name: 'Admin TI' },
        { code: 'FUNC_ADMIN', name: 'Admin Funcional' },
        { code: 'DATA_OWNER', name: 'Dueño de Datos' },
        { code: 'ANALYST', name: 'Analista' },
        { code: 'DIRECTIVE', name: 'Directivo' },
        { code: 'SOURCE_UPLOADER', name: 'Ingesta' },
    ];

    const fetchUsers = async () => {
        try {
            const res = await fetch(`${API_BASE_URL}/users/`, {
                headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` }
            });
            const data = await res.json();
            if (Array.isArray(data)) {
                setUsers(data);
            } else {
                console.warn('API /users/ no devolvió un array:', data);
                setUsers([]);
            }
        } catch (err) {
            console.error(err);
            setUsers([]);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => { fetchUsers(); }, []);

    const handleCreate = async (e) => {
        e.preventDefault();
        try {
            const res = await fetch(`${API_BASE_URL}/users/`, {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${localStorage.getItem('token')}`,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(newUser)
            });
            if (res.ok) {
                alert('Usuario creado con éxito');
                setShowModal(false);
                fetchUsers();
                setNewUser({
                    username: '', email: '', password: '', full_name: '',
                    dependency: '', position: '', data_level_max: 1, role_codes: ['ANALYST']
                });
            } else {
                const errorData = await res.json();
                alert(`Error al crear usuario: ${errorData.detail || 'Error desconocido'}`);
            }
        } catch (err) {
            console.error(err);
            alert('Error crítico de conexión con el servidor');
        }
    };

    const handleDisable = async (id) => {
        if (!confirm('¿Desactivar este usuario?')) return;
        try {
            await fetch(`${API_BASE_URL}/users/${id}/disable`, {
                method: 'POST',
                headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` }
            });
            fetchUsers();
        } catch (err) { console.error(err); }
    };

    return (
        <div className="space-y-6">
            <div className="flex justify-between items-center">
                <div>
                    <h2 className="text-3xl font-black text-slate-800">SISC | Usuarios</h2>
                    <p className="text-slate-500 font-medium">Gestión Institucional de Accesos</p>
                </div>
                <button
                    onClick={() => setShowModal(true)}
                    className="bg-primary text-white px-6 py-3 rounded-2xl font-bold flex items-center gap-2 shadow-lg shadow-primary/20 hover:-translate-y-1 transition-all"
                >
                    <Plus size={20} /> Nuevo Usuario
                </button>
            </div>

            <div className="bg-white rounded-3xl shadow-xl overflow-hidden border border-slate-100">
                <table className="w-full text-left">
                    <thead className="bg-slate-50 border-b border-slate-100">
                        <tr>
                            <th className="px-6 py-4 text-xs font-black text-slate-400 uppercase tracking-widest">Usuario</th>
                            <th className="px-6 py-4 text-xs font-black text-slate-400 uppercase tracking-widest">Dependencia</th>
                            <th className="px-6 py-4 text-xs font-black text-slate-400 uppercase tracking-widest">Nivel / Roles</th>
                            <th className="px-6 py-4 text-xs font-black text-slate-400 uppercase tracking-widest">Estado</th>
                            <th className="px-6 py-4 text-xs font-black text-slate-400 uppercase tracking-widest">Acciones</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-50">
                        {Array.isArray(users) && users.length > 0 ? users.map(u => (
                            <tr key={u.id} className="hover:bg-slate-50/50 transition-colors">
                                <td className="px-6 py-4">
                                    <div className="flex items-center gap-3">
                                        <div className="w-10 h-10 bg-primary/10 rounded-xl flex items-center justify-center text-primary font-bold">
                                            {(u.username?.[0] || 'U').toUpperCase()}
                                        </div>
                                        <div>
                                            <p className="font-bold text-slate-800">{u.full_name}</p>
                                            <p className="text-xs text-slate-500">@{u.username}</p>
                                        </div>
                                    </div>
                                </td>
                                <td className="px-6 py-4">
                                    <p className="text-sm font-bold text-slate-700">{u.dependency || 'N/A'}</p>
                                    <p className="text-xs text-slate-400 uppercase tracking-wider font-medium">{u.position || '-'}</p>
                                </td>
                                <td className="px-6 py-4">
                                    <div className="flex flex-wrap gap-1.5">
                                        <span className={`px-2 py-0.5 rounded-lg text-[10px] font-black uppercase tracking-tighter ${u.data_level_max === 3 ? 'bg-red-100 text-red-600' :
                                            u.data_level_max === 2 ? 'bg-amber-100 text-amber-600' : 'bg-slate-100 text-slate-600'
                                            }`}>N{u.data_level_max}</span>
                                        {u.roles?.map(r => (
                                            <span key={r.code} className="bg-primary/5 text-primary border border-primary/10 px-2 py-0.5 rounded-lg text-[10px] font-bold">
                                                {r.code || 'N/A'}
                                            </span>
                                        ))}
                                    </div>
                                </td>
                                <td className="px-6 py-4">
                                    {u.is_active ? (
                                        <span className="flex items-center gap-1.5 text-xs font-bold text-emerald-600">
                                            <CheckCircle2 size={14} /> Activo
                                        </span>
                                    ) : (
                                        <span className="flex items-center gap-1.5 text-xs font-bold text-slate-400">
                                            <AlertTriangle size={14} /> Inactivo
                                        </span>
                                    )}
                                </td>
                                <td className="px-6 py-4">
                                    {u.is_active && u.username !== 'admin' && (
                                        <button
                                            onClick={() => handleDisable(u.id)}
                                            className="p-2 text-slate-400 hover:text-red-500 hover:bg-red-50 rounded-lg transition-all"
                                        >
                                            <Trash2 size={18} />
                                        </button>
                                    )}
                                </td>
                            </tr>
                        )) : (
                            <tr>
                                <td colSpan="5" className="px-6 py-20 text-center text-slate-400 italic">
                                    No hay usuarios registrados o no tiene permisos suficientes.
                                </td>
                            </tr>
                        )}
                    </tbody>
                </table>
            </div>

            {/* Modal de Creación */}
            {showModal && (
                <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-sm z-50 flex items-center justify-center p-4">
                    <div className="bg-white rounded-[2rem] w-full max-w-lg shadow-2xl animate-fade-in overflow-hidden border border-slate-100">
                        <div className="bg-[#281FD0] p-6 text-white text-center">
                            <h3 className="text-2xl font-black">Nuevo Usuario</h3>
                            <p className="text-white/60 text-sm font-medium">Credenciales Institucionales</p>
                        </div>
                        <form onSubmit={handleCreate} className="p-8 space-y-4">
                            <div className="grid grid-cols-2 gap-4">
                                <div className="space-y-1">
                                    <label className="text-[10px] font-black text-slate-400 uppercase tracking-widest ml-1">Username</label>
                                    <input required placeholder="j.perez" className="w-full bg-slate-50 border-slate-200 rounded-xl px-4 py-2.5 text-sm font-bold"
                                        value={newUser.username} onChange={e => setNewUser({ ...newUser, username: e.target.value })} />
                                </div>
                                <div className="space-y-1">
                                    <label className="text-[10px] font-black text-slate-400 uppercase tracking-widest ml-1">Contraseña</label>
                                    <input required type="password" placeholder="••••••••" className="w-full bg-slate-50 border-slate-200 rounded-xl px-4 py-2.5 text-sm font-bold"
                                        value={newUser.password} onChange={e => setNewUser({ ...newUser, password: e.target.value })} />
                                </div>
                            </div>
                            <div className="space-y-1">
                                <label className="text-[10px] font-black text-slate-400 uppercase tracking-widest ml-1">Nombre Completo</label>
                                <input required placeholder="Juan Pérez" className="w-full bg-slate-50 border-slate-200 rounded-xl px-4 py-2.5 text-sm font-bold"
                                    value={newUser.full_name} onChange={e => setNewUser({ ...newUser, full_name: e.target.value })} />
                            </div>
                            <div className="grid grid-cols-2 gap-4">
                                <div className="space-y-1">
                                    <label className="text-[10px] font-black text-slate-400 uppercase tracking-widest ml-1">Email</label>
                                    <input required type="email" placeholder="email@jamundi.gov.co" className="w-full bg-slate-50 border-slate-200 rounded-xl px-4 py-2.5 text-sm font-bold"
                                        value={newUser.email} onChange={e => setNewUser({ ...newUser, email: e.target.value })} />
                                </div>
                                <div className="space-y-1">
                                    <label className="text-[10px] font-black text-slate-400 uppercase tracking-widest ml-1">Nivel Máx</label>
                                    <select className="w-full bg-slate-50 border-slate-200 rounded-xl px-4 py-2.5 text-sm font-bold"
                                        value={newUser.data_level_max} onChange={e => setNewUser({ ...newUser, data_level_max: parseInt(e.target.value) })}>
                                        <option value={1}>N1 - Público</option>
                                        <option value={2}>N2 - Institucional</option>
                                        <option value={3}>N3 - Restringido</option>
                                    </select>
                                </div>
                            </div>

                            <div className="space-y-1 pb-4">
                                <label className="text-[10px] font-black text-slate-400 uppercase tracking-widest ml-1">Roles Base</label>
                                <div className="flex flex-wrap gap-2 pt-1">
                                    {rolesList.map(r => (
                                        <button type="button" key={r.code}
                                            onClick={() => {
                                                const codes = newUser.role_codes.includes(r.code)
                                                    ? newUser.role_codes.filter(c => c !== r.code)
                                                    : [...newUser.role_codes, r.code];
                                                setNewUser({ ...newUser, role_codes: codes });
                                            }}
                                            className={`px-3 py-1.5 rounded-xl text-xs font-black transition-all ${newUser.role_codes.includes(r.code) ? 'bg-primary text-white' : 'bg-slate-100 text-slate-500'
                                                }`}
                                        >
                                            {r.name}
                                        </button>
                                    ))}
                                </div>
                            </div>

                            <div className="flex gap-4 pt-2">
                                <button type="button" onClick={() => setShowModal(false)} className="flex-1 px-4 py-3 bg-slate-100 text-slate-500 rounded-2xl font-black hover:bg-slate-200 transition-colors uppercase tracking-widest text-xs">Cancelar</button>
                                <button type="submit" className="flex-1 px-4 py-3 bg-primary text-white rounded-2xl font-black shadow-lg shadow-primary/20 hover:-translate-y-1 transition-all uppercase tracking-widest text-xs">Crear Usuario</button>
                            </div>
                        </form>
                    </div>
                </div>
            )}
        </div>
    );
};

export default UsersManagement;
