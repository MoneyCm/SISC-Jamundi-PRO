import React from 'react';
import { LayoutDashboard, Map, FileText, Database, Settings, ChevronRight, X } from 'lucide-react';

const Sidebar = ({ activePage, setActivePage, isOpen, onClose, onLogout, isPublic }) => {
    const menuItems = isPublic ? [
        { id: 'dashboard', label: 'Portal Ciudadano', icon: LayoutDashboard },
        { id: 'map', label: 'Mapa de Incidencia', icon: Map },
    ] : [
        { id: 'dashboard', label: 'Tablero de Control', icon: LayoutDashboard },
        { id: 'map', label: 'Mapa del Delito', icon: Map },
        { id: 'reports', label: 'Boletines y Reportes', icon: FileText },
        { id: 'data', label: 'Gestión de Datos', icon: Database },
    ];

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

            <nav className="flex-1 py-8 px-4 relative z-10">
                <p className="px-4 text-xs font-bold text-slate-500 uppercase tracking-wider mb-4">Menu Principal</p>
                <ul className="space-y-2">
                    {menuItems.map((item) => {
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
                                        <Icon size={20} className={isActive ? 'text-white' : 'text-slate-500 group-hover:text-white transition-colors'} />
                                        <span className="font-medium">{item.label}</span>
                                    </div>
                                    {isActive && <ChevronRight size={16} className="text-white/70" />}
                                </button>
                            </li>
                        );
                    })}
                </ul>
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
