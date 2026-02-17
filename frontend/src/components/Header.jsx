import { Bell, User, Search, Menu } from 'lucide-react';

const Header = ({ onMenuClick, isPublic }) => {
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

export default Header;
