import React, { useState, useEffect } from 'react';
import { FileText, Search, User, Shield, Clock, Globe, Laptop, Activity } from 'lucide-react';
import { API_BASE_URL } from '../utils/apiConfig';

const AuditLog = () => {
    const [logs, setLogs] = useState([]);
    const [loading, setLoading] = useState(true);
    const [searchTerm, setSearchTerm] = useState('');

    const fetchLogs = async () => {
        try {
            const res = await fetch(`${API_BASE_URL}/users/audit?limit=200`, {
                headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` }
            });
            const data = await res.json();
            if (Array.isArray(data)) {
                setLogs(data);
            } else {
                setLogs([]);
            }
        } catch (err) {
            console.error(err);
            setLogs([]);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => { fetchLogs(); }, []);

    const filteredLogs = logs.filter(log =>
        log.action.toLowerCase().includes(searchTerm.toLowerCase()) ||
        log.module?.toLowerCase().includes(searchTerm.toLowerCase()) ||
        log.actor?.toLowerCase().includes(searchTerm.toLowerCase())
    );

    const getLevelColor = (level) => {
        switch (level) {
            case 3: return 'bg-red-50 text-red-700 border-red-100';
            case 2: return 'bg-amber-50 text-amber-700 border-amber-100';
            default: return 'bg-blue-50 text-blue-700 border-blue-100';
        }
    };

    return (
        <div className="space-y-6 max-w-7xl mx-auto">
            <div className="flex justify-between items-center bg-white p-8 rounded-[2.5rem] shadow-xl border border-slate-100">
                <div>
                    <h2 className="text-4xl font-black text-slate-800 tracking-tight">Trazabilidad Total</h2>
                    <p className="text-slate-500 font-bold mt-1 flex items-center gap-2 uppercase tracking-widest text-[10px]">
                        <Activity size={14} className="text-primary" /> Log de Auditoría Institucional
                    </p>
                </div>
                <div className="relative group">
                    <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400 group-focus-within:text-primary transition-colors" size={20} />
                    <input
                        type="text"
                        placeholder="Buscar por acción, módulo o usuario..."
                        className="pl-12 pr-6 py-4 bg-slate-50 border-none rounded-2xl w-80 text-sm font-bold text-slate-700 focus:ring-2 focus:ring-primary/20 transition-all outline-none"
                        value={searchTerm}
                        onChange={(e) => setSearchTerm(e.target.value)}
                    />
                </div>
            </div>

            <div className="bg-white rounded-[3rem] shadow-2xl overflow-hidden border border-slate-100">
                <div className="overflow-x-auto">
                    <table className="w-full text-left border-collapse">
                        <thead>
                            <tr className="bg-slate-50/50 border-b border-slate-100">
                                <th className="px-8 py-6 text-[10px] font-black text-slate-400 uppercase tracking-widest">Fecha / Nodo</th>
                                <th className="px-6 py-6 text-[10px] font-black text-slate-400 uppercase tracking-widest">Actor (ID)</th>
                                <th className="px-6 py-6 text-[10px] font-black text-slate-400 uppercase tracking-widest">Acción / Módulo</th>
                                <th className="px-6 py-6 text-[10px] font-black text-slate-400 uppercase tracking-widest">Nivel</th>
                                <th className="px-6 py-6 text-[10px] font-black text-slate-400 uppercase tracking-widest">Origen</th>
                                <th className="px-6 py-6 text-[10px] font-black text-slate-400 uppercase tracking-widest">Target Ref</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-50">
                            {filteredLogs.map(log => (
                                <tr key={log.id} className="hover:bg-slate-50/50 transition-colors">
                                    <td className="px-8 py-6">
                                        <div className="flex items-center gap-3">
                                            <div className="bg-slate-100 p-2 rounded-xl text-slate-400">
                                                <Clock size={16} />
                                            </div>
                                            <div>
                                                <p className="text-sm font-black text-slate-700 leading-none">
                                                    {new Date(log.created_at).toLocaleTimeString()}
                                                </p>
                                                <p className="text-[10px] font-bold text-slate-400 mt-1 uppercase">
                                                    {new Date(log.created_at).toLocaleDateString()}
                                                </p>
                                            </div>
                                        </div>
                                    </td>
                                    <td className="px-6 py-6">
                                        <div className="flex items-center gap-2">
                                            <User size={14} className="text-slate-300" />
                                            <code className="text-[10px] font-mono text-slate-500 bg-slate-50 px-2 py-0.5 rounded border border-slate-100">
                                                {(log.actor || 'Sistema').slice(0, 8)}...
                                            </code>
                                        </div>
                                    </td>
                                    <td className="px-6 py-6">
                                        <div>
                                            <p className="text-sm font-black text-slate-800 tracking-tight leading-none uppercase">{log.action}</p>
                                            <p className="text-[10px] font-bold text-primary mt-1 tracking-widest">{log.module || 'AUTH'}</p>
                                        </div>
                                    </td>
                                    <td className="px-6 py-6">
                                        <span className={`px-2.5 py-1 rounded-full text-[9px] font-black border ${getLevelColor(log.level)} uppercase`}>
                                            Nivel {log.level}
                                        </span>
                                    </td>
                                    <td className="px-6 py-6">
                                        <div className="space-y-1">
                                            <div className="flex items-center gap-2 text-[10px] font-bold text-slate-500">
                                                <Globe size={12} /> {log.ip}
                                            </div>
                                            <div className="flex items-center gap-2 text-[10px] font-bold text-slate-400 truncate max-w-[150px]">
                                                <Laptop size={12} /> {log.user_agent}
                                            </div>
                                        </div>
                                    </td>
                                    <td className="px-6 py-6">
                                        {log.target ? (
                                            <pre className="text-[9px] font-mono bg-slate-900 text-emerald-400 p-2 rounded-lg max-w-[200px] overflow-hidden truncate">
                                                {JSON.stringify(log.target)}
                                            </pre>
                                        ) : (
                                            <span className="text-[9px] font-bold text-slate-300 italic">None</span>
                                        )}
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    );
};

export default AuditLog;
