import React from 'react';
import { LayoutDashboard, Map, FileText, Database, Settings, ChevronRight } from 'lucide-react';

const Sidebar = ({ activePage, setActivePage }) => {
    const menuItems = [
        { id: 'dashboard', label: 'Tablero de Control', icon: LayoutDashboard },
        { id: 'map', label: 'Mapa del Delito', icon: Map },
        { id: 'reports', label: 'Boletines y Reportes', icon: FileText },
        { id: 'data', label: 'Gestión de Datos', icon: Database },
    ];

    return (
        <aside className="w-72 bg-[#281FD0] text-white min-h-screen flex flex-col shadow-2xl relative overflow-hidden">
            {/* Background decoration - subtle gradient */}
            <div className="absolute top-0 left-0 w-full h-full bg-gradient-to-b from-white/10 to-transparent pointer-events-none" />

            <div className="p-6 flex items-center space-x-4 border-b border-slate-800/50 relative z-10">
                <div className="bg-white p-1.5 rounded-xl shadow-inner flex items-center justify-center">
                    <img src="/assets/escudo.png" alt="Escudo Jamundí" className="w-10 h-12 object-contain" />
                </div>
                <div className="flex flex-col">
                    <h1 className="text-3xl font-black tracking-tighter text-white leading-none">SISC</h1>
                    <span className="text-xs text-white font-bold uppercase tracking-[0.1em] mt-1 opacity-90">
                        Jamundí <span className="opacity-60">| Valle</span>
                    </span>
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
                                    onClick={() => setActivePage(item.id)}
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

            <div className="p-4 border-t border-slate-800/50 relative z-10">
                <button className="flex items-center space-x-3 text-white/70 hover:text-white hover:bg-white/10 px-4 py-3 rounded-xl transition-all w-full group">
                    <Settings size={20} className="group-hover:rotate-90 transition-transform duration-500" />
                    <span className="font-medium">Configuración</span>
                </button>
            </div>
        </aside>
    );
};

export default Sidebar;
