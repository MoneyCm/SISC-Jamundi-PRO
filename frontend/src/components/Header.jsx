import React from 'react';
import { Bell, User, Search } from 'lucide-react';

const Header = () => {
    return (
        <header className="bg-white shadow-sm h-16 flex items-center justify-between px-8 z-10 sticky top-0">
            <div className="flex items-center bg-slate-100 rounded-full px-4 py-2 w-96">
                <Search size={18} className="text-slate-400 mr-2" />
                <input
                    type="text"
                    placeholder="Buscar reportes, zonas, indicadores..."
                    className="bg-transparent border-none outline-none text-sm text-slate-700 w-full placeholder-slate-400"
                />
            </div>

            <div className="flex items-center space-x-6">
                <button className="relative text-slate-500 hover:text-primary transition-colors">
                    <Bell size={20} />
                    <span className="absolute -top-1 -right-1 bg-red-500 text-white text-xs w-4 h-4 rounded-full flex items-center justify-center">3</span>
                </button>

                <div className="flex items-center space-x-3 pl-6 border-l border-slate-200">
                    <div className="text-right hidden md:block">
                        <p className="text-sm font-semibold text-slate-800">Observatorio del Delito</p>
                        <p className="text-xs text-slate-500">Administrador</p>
                    </div>
                    <div className="w-10 h-10 bg-primary/10 rounded-full flex items-center justify-center text-primary">
                        <User size={20} />
                    </div>
                </div>
            </div>
        </header>
    );
};

export default Header;
