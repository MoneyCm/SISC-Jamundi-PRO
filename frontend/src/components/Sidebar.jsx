import React from 'react';
import { LayoutDashboard, Map, FileText, Database, Settings, Shield, ChevronRight } from 'lucide-react';

const Sidebar = ({ activePage, setActivePage }) => {
    const menuItems = [
        { id: 'dashboard', label: 'Tablero de Control', icon: LayoutDashboard },
        { id: 'map', label: 'Mapa del Delito', icon: Map },
        { id: 'reports', label: 'Boletines y Reportes', icon: FileText },
        { id: 'data', label: 'Gestión de Datos', icon: Database },
    ];

    return (
        <aside className="w-72 bg-slate-900 text-white min-h-screen flex flex-col shadow-2xl relative overflow-hidden">
            {/* Background decoration */}
            <div className="absolute top-0 left-0 w-full h-full bg-gradient-to-b from-slate-800/50 to-transparent pointer-events-none" />

            <div className="p-6 flex items-center space-x-4 border-b border-slate-800/50 relative z-10">
                <div className="bg-primary/20 p-2 rounded-lg">
                    <Shield className="w-8 h-8 text-primary" />
                </div>
                <div>
                    <h1 className="text-xl font-bold tracking-wider text-white">SISC</h1>
                    <p className="text-xs text-slate-400 font-medium tracking-wide">JAMUNDÍ</p>
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
                                            ? 'bg-primary text-white shadow-lg shadow-primary/20'
                                            : 'text-slate-400 hover:bg-slate-800 hover:text-white'
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
                <button className="flex items-center space-x-3 text-slate-400 hover:text-white hover:bg-slate-800 px-4 py-3 rounded-xl transition-all w-full group">
                    <Settings size={20} className="group-hover:rotate-90 transition-transform duration-500" />
                    <span className="font-medium">Configuración</span>
                </button>
            </div>
        </aside>
    );
};

export default Sidebar;
