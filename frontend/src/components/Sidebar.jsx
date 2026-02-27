import React from 'react';
import { LayoutDashboard, Map, FileText, Database, Settings, ChevronRight, X, Globe, CheckCircle2, Zap, ShieldCheck, ShieldAlert, Layers, Bell, Activity } from 'lucide-react';

const Sidebar = ({ activePage, setActivePage, isOpen, onClose, onLogout, isPublic, userRoles = [] }) => {
    const isAdmin = userRoles.includes('TI_ADMIN') || userRoles.includes('FUNC_ADMIN');
    const isAnalyst = userRoles.includes('ANALYST') || isAdmin;
    const isDirective = userRoles.includes('DIRECTIVE') || isAdmin;
    const isUploader = userRoles.includes('SOURCE_UPLOADER') || isAdmin;
    const isSteward = userRoles.includes('STEWARD') || isAdmin;

    const allItems = [
        { id: 'dashboard', label: 'Inicio', icon: LayoutDashboard, category: 'HOME', show: true },

        { id: 'users', label: 'Gestión Usuarios', icon: ShieldAlert, category: 'ADMINISTRACIÓN', show: isAdmin },
        { id: 'access_requests', label: 'Solicitudes', icon: Bell, category: 'ADMINISTRACIÓN', show: isAdmin || userRoles.includes('DATA_OWNER') },
        { id: 'audit', label: 'Audit Log', icon: Activity, category: 'ADMINISTRACIÓN', show: isAdmin },

        { id: 'ingesta_universal', label: 'Carga de Datos', icon: Zap, category: 'OPERACIONES', show: isUploader },
        { id: 'monitoring', label: 'Fuentes Externas', icon: Globe, category: 'OPERACIONES', show: isUploader || isSteward },
        { id: 'dq', label: 'Calidad (DQ)', icon: ShieldCheck, category: 'OPERACIONES', show: isSteward },

        { id: 'map', label: 'Mapa Interactivo', icon: Map, category: 'ESTRATEGIA', show: isAnalyst || isDirective },
        { id: 'intelligence', label: 'Análisis IA', icon: Zap, category: 'ESTRATEGIA', show: isAnalyst || isDirective },
        { id: 'alerts', label: 'Alertas Tempranas', icon: Bell, category: 'ESTRATEGIA', show: isAnalyst || isDirective },
        { id: 'rnmc', label: 'Medidas Policia', icon: FileText, category: 'ESTRATEGIA', show: isAnalyst },

        { id: 'reports', label: 'Reportes PDF', icon: FileText, category: 'SALIDA', show: isDirective || isAnalyst },
        { id: 'data', label: 'Descarga CSV/XLS', icon: Database, category: 'SALIDA', show: isAnalyst },
    ];

    const menuItems = isPublic ? [
        { id: 'dashboard', label: 'Portal Ciudadano', icon: LayoutDashboard, category: 'HOME', show: true },
        { id: 'map', label: 'Mapa Público', icon: Map, category: 'HOME', show: true },
    ] : allItems.filter(item => item.show);

    // Helper to render grouped items
    const categories = [...new Set(menuItems.map(item => item.category))];

    return (
        <aside className={`fixed inset-y-0 left-0 z-30 w-72 bg-[#281FD0] text-white flex flex-col shadow-2xl transition-transform duration-300 ease-in-out md:relative md:translate-x-0 overflow-hidden ${isOpen ? 'translate-x-0' : '-translate-x-full'
            }`}>
            {/* Background decoration - subtle gradient */}
            <div className="absolute top-0 left-0 w-full h-full bg-gradient-to-b from-white/10 to-transparent pointer-events-none" />

            <div className="p-6 flex flex-col items-center relative z-10 border-b border-slate-800/50">
                <button
                    onClick={onClose}
                    className="md:hidden absolute top-4 right-4 text-white/60 hover:text-white transition-colors"
                >
                    <X size={24} />
                </button>

                <div className="flex flex-col items-center space-y-4">
                    <div className="bg-white p-3 rounded-2xl shadow-xl flex items-center justify-center transform group-hover:scale-105 transition-transform">
                        <img src="/assets/escudo.png" alt="Escudo Jamundí" className="w-20 h-20 object-contain" />
                    </div>
                    <div className="text-center">
                        <h1 className="text-5xl font-black tracking-tighter text-white">SISC</h1>
                        <p className="text-[10px] text-white/70 font-bold uppercase tracking-[0.2em]">Jamundí | Seguridad</p>
                    </div>
                </div>
            </div>

            <nav className="flex-1 py-6 px-4 relative z-10 overflow-y-auto custom-scrollbar">
                {categories.map((category) => (
                    <div key={category || 'uncategorized'} className="mb-6 last:mb-0">
                        {category && category !== 'HOME' && (
                            <p className="px-4 text-[10px] font-black text-slate-400 uppercase tracking-[0.2em] mb-3 opacity-80">
                                {category}
                            </p>
                        )}
                        <ul className="space-y-1.5">
                            {menuItems
                                .filter(item => item.category === category)
                                .map((item) => {
                                    const Icon = item.icon;
                                    const isActive = activePage === item.id;
                                    return (
                                        <li key={item.id}>
                                            <button
                                                onClick={() => {
                                                    setActivePage(item.id);
                                                    onClose();
                                                }}
                                                className={`w-full flex items-center justify-between px-4 py-3 rounded-xl transition-all duration-300 group
                                                    ${isActive
                                                        ? 'bg-white/20 text-white shadow-lg backdrop-blur-md border border-white/10'
                                                        : 'text-white/70 hover:bg-white/10 hover:text-white'
                                                    }`}
                                            >
                                                <div className="flex items-center space-x-3">
                                                    <Icon size={18} className={isActive ? 'text-white' : 'text-slate-400 group-hover:text-white transition-colors'} />
                                                    <span className={`text-sm ${isActive ? 'font-black' : 'font-bold'}`}>{item.label}</span>
                                                </div>
                                                {isActive && <ChevronRight size={14} className="text-white/70" />}
                                            </button>
                                        </li>
                                    );
                                })}
                        </ul>
                    </div>
                ))}
            </nav>

            <div className="p-4 border-t border-slate-800/50 relative z-10 space-y-2">
                <button className="flex items-center space-x-3 text-white/70 hover:text-white hover:bg-white/10 px-4 py-3 rounded-xl transition-all w-full group">
                    <Settings size={20} className="group-hover:rotate-90 transition-transform duration-500" />
                    <span className="font-medium">Configuración</span>
                </button>
                <button
                    onClick={onLogout}
                    className="flex items-center space-x-3 text-red-300 hover:text-white hover:bg-red-500/20 px-4 py-3 rounded-xl transition-all w-full group"
                >
                    <X size={20} className="group-hover:rotate-90 transition-transform" />
                    <span className="font-medium">Cerrar Sesión</span>
                </button>
            </div>
        </aside>
    );
};

export default Sidebar;
