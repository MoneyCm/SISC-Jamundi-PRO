import React, { useState, useEffect } from 'react';
import { Bell, CheckCircle2, XCircle, Info, Calendar, ShieldCheck, User, ShieldAlert, FileText } from 'lucide-react';
import { apiFetch, apiJson, readApiError } from '../utils/apiClient';

const AccessRequests = ({ userRoles = [] }) => {
    const [requests, setRequests] = useState([]);
    const [loading, setLoading] = useState(true);
    const [stats, setStats] = useState({ pending: 0, high_level: 0 });

    const fetchRequests = async () => {
        try {
            const data = await apiJson('/users/access-requests/pending');
            const safeData = Array.isArray(data) ? data : [];
            setRequests(safeData);
            setStats({
                pending: safeData.length,
                high_level: safeData.filter(r => r.requested_data_level === 3).length
            });
        } catch (err) {
            console.error(err);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => { fetchRequests(); }, []);

    const handleApprove = async (id) => {
        try {
            const res = await apiFetch(`/users/access-requests/${id}/approve`, { method: 'POST' });
            if (res.ok) fetchRequests();
            else {
                alert(await readApiError(res, 'No fue posible aprobar la solicitud.'));
            }
        } catch (err) { console.error(err); }
    };

    const handleReject = async (id) => {
        try {
            const res = await apiFetch(`/users/access-requests/${id}/reject`, { method: 'POST' });
            if (res.ok) fetchRequests();
            else alert(await readApiError(res, 'No fue posible rechazar la solicitud.'));
        } catch (err) {
            console.error(err);
        }
    };

    return (
        <div className="space-y-6 max-w-6xl mx-auto">
            <div className="flex justify-between items-center bg-white p-8 rounded-[2.5rem] shadow-xl border border-slate-100 relative overflow-hidden">
                <div className="absolute top-0 right-0 w-32 h-32 bg-primary/5 rounded-bl-full -mr-10 -mt-10" />
                <div className="relative z-10">
                    <h2 className="text-4xl font-black text-slate-800 tracking-tight">Solicitudes de Acceso</h2>
                    <p className="text-slate-500 font-bold mt-1 flex items-center gap-2 uppercase tracking-widest text-[10px]">
                        <ShieldCheck size={14} className="text-primary" /> Control de Privilegios Institucional
                    </p>
                </div>
                <div className="flex gap-4 relative z-10">
                    <div className="bg-slate-50 px-6 py-3 rounded-2xl border border-slate-100 text-center min-w-[120px]">
                        <p className="text-xs font-black text-slate-400 uppercase tracking-widest leading-tight">Pendientes</p>
                        <p className="text-3xl font-black text-primary">{stats.pending}</p>
                    </div>
                    <div className="bg-red-50 px-6 py-3 rounded-2xl border border-red-100 text-center min-w-[120px]">
                        <p className="text-xs font-black text-red-400 uppercase tracking-widest leading-tight">Críticas (N3)</p>
                        <p className="text-3xl font-black text-red-600">{stats.high_level}</p>
                    </div>
                </div>
            </div>

            <div className="grid grid-cols-1 gap-4">
                {requests.length === 0 ? (
                    <div className="bg-white p-20 rounded-[3rem] text-center border-2 border-dashed border-slate-100 shadow-sm opacity-60">
                        <div className="bg-slate-50 w-20 h-20 rounded-full flex items-center justify-center mx-auto mb-6 text-slate-300">
                            <CheckCircle2 size={40} />
                        </div>
                        <h3 className="text-2xl font-black text-slate-400 italic">Bandeja despejada</h3>
                        <p className="text-slate-400 font-medium max-w-sm mx-auto mt-2 italic text-sm">No hay solicitudes pendientes de autorización en este momento.</p>
                    </div>
                ) : requests.map(req => (
                    <div key={req.id} className="bg-white rounded-[2rem] p-6 shadow-xl border border-slate-100 hover:border-primary/20 transition-all group relative overflow-hidden">
                        {req.requested_data_level === 3 && (
                            <div className="absolute top-0 left-0 w-1.5 h-full bg-red-600" />
                        )}
                        <div className="flex flex-col md:flex-row gap-6 items-start">
                            <div className="flex-1 space-y-4">
                                <div className="flex items-center gap-4">
                                    <div className="w-12 h-12 bg-slate-100 rounded-2xl flex items-center justify-center text-slate-400">
                                        <User size={24} />
                                    </div>
                                    <div>
                                        <div className="flex items-center gap-3">
                                            <h4 className="text-xl font-black text-slate-800 tracking-tight">Usuario CID: {req.user_id.slice(0, 8)}</h4>
                                            <span className={`px-2.5 py-1 rounded-full text-[9px] font-black uppercase tracking-widest ${req.requested_data_level === 3 ? 'bg-red-600 text-white animate-pulse' :
                                                    req.requested_data_level === 2 ? 'bg-amber-500 text-white' : 'bg-slate-200 text-slate-600'
                                                }`}>
                                                SOLICITA NIVEL {req.requested_data_level}
                                            </span>
                                        </div>
                                        <p className="text-xs font-bold text-slate-400 flex items-center gap-2 mt-1 uppercase tracking-widest">
                                            <Calendar size={12} /> Creada el {new Date(req.created_at).toLocaleDateString('es-CO', { day: 'numeric', month: 'long', year: 'numeric' })}
                                        </p>
                                    </div>
                                </div>

                                <div className="bg-slate-50/80 rounded-2xl p-5 border border-slate-100/50">
                                    <div className="flex items-start gap-3 mb-2">
                                        <FileText size={16} className="text-primary mt-1" />
                                        <p className="text-sm font-bold text-slate-700 leading-relaxed italic line-clamp-2">"{req.justification}"</p>
                                    </div>
                                    <div className="flex flex-wrap gap-2 mt-4 pt-4 border-t border-slate-200/40">
                                        <span className="text-[10px] font-black text-slate-400 uppercase tracking-widest mr-2">Roles Solicitados:</span>
                                        {req.requested_roles.map(r => (
                                            <span key={r} className="bg-white px-3 py-1 rounded-lg border border-slate-200 text-[10px] font-black text-slate-600 uppercase">
                                                {r}
                                            </span>
                                        ))}
                                    </div>
                                </div>
                            </div>

                            <div className="flex flex-row md:flex-col gap-3 min-w-[200px] w-full md:w-auto">
                                <button
                                    onClick={() => handleApprove(req.id)}
                                    className="flex-1 bg-emerald-600 text-white px-6 py-4 rounded-2xl font-black text-sm flex items-center justify-center gap-3 shadow-lg shadow-emerald-600/20 hover:-translate-y-1 active:scale-95 transition-all uppercase tracking-widest"
                                >
                                    <ShieldCheck size={20} /> Aprobar
                                </button>
                                <button
                                    onClick={() => handleReject(req.id)}
                                    className="flex-1 bg-slate-100 text-slate-400 px-6 py-4 rounded-2xl font-black text-sm flex items-center justify-center gap-3 hover:bg-red-50 hover:text-red-500 transition-all uppercase tracking-widest"
                                >
                                    <XCircle size={20} /> Rechazar
                                </button>
                            </div>
                        </div>
                    </div>
                ))}
            </div>

            <div className="bg-amber-50 rounded-3xl p-6 border border-amber-100 flex items-start gap-4">
                <div className="bg-amber-200/50 p-2 rounded-xl text-amber-700">
                    <Info size={24} />
                </div>
                <div className="space-y-1">
                    <h5 className="font-black text-amber-900 leading-none">Aviso de Privacidad SISC</h5>
                    <p className="text-sm text-amber-800/80 font-medium">Las solicitudes de Nivel 3 (Restringido) requieren validación manual del Dueño de Datos (Data Owner) y se registran en el log de auditoría del sistema institucional.</p>
                </div>
            </div>
        </div>
    );
};

export default AccessRequests;
