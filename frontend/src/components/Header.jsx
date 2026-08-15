import { Bell, User, Search, Menu, ShieldCheck } from 'lucide-react';

const LegacyHeader = ({ onMenuClick, isPublic }) => {
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

const PAGE_LABELS = {
    dashboard: 'Resumen operativo',
    users: 'Gestión de usuarios',
    access_requests: 'Solicitudes de acceso',
    audit: 'Auditoría',
    sources: 'Centro de fuentes',
    reports: 'Reportes',
    stats: 'Estadísticas',
    map: 'Mapa institucional',
    intelligence: 'Contexto comparado',
    alerts: 'Alertas estadísticas',
};

const ROLE_LABELS = {
    TI_ADMIN: 'Administración TI',
    FUNC_ADMIN: 'Administración funcional',
    DATA_OWNER: 'Responsable de datos',
    DIRECTIVE: 'Perfil directivo',
    ANALYST: 'Perfil analista',
    SOURCE_UPLOADER: 'Carga de fuentes',
};

const Header = ({ onMenuClick, isPublic, currentUser, activePage }) => {
    if (isPublic) return <LegacyHeader onMenuClick={onMenuClick} isPublic />;

    const primaryRole = currentUser?.roles?.[0];
    const displayName = currentUser?.full_name || currentUser?.username || 'Usuario institucional';

    return (
        <header className="bg-white border-b border-slate-200 min-h-16 flex items-center justify-between gap-4 px-4 md:px-8 z-10 sticky top-0">
            <div className="flex items-center gap-3 min-w-0">
                <button onClick={onMenuClick} aria-label="Abrir navegación" className="p-2 -ml-2 text-slate-600 hover:bg-slate-50 rounded-lg md:hidden">
                    <Menu size={24} />
                </button>
                <div className="min-w-0">
                    <p className="text-[10px] font-bold uppercase text-slate-400">Centro de mando SISC</p>
                    <h1 className="text-sm md:text-base font-black text-slate-800 truncate">{PAGE_LABELS[activePage] || 'Gestión institucional'}</h1>
                </div>
            </div>

            <div className="flex items-center gap-3 pl-4 border-l border-slate-200 min-w-0">
                <div className="hidden sm:block text-right min-w-0">
                    <p className="text-sm font-bold text-slate-800 truncate max-w-56">{displayName}</p>
                    <p className="text-[10px] text-slate-500 font-semibold truncate max-w-56">
                        {ROLE_LABELS[primaryRole] || currentUser?.dependency || 'Acceso institucional'} · N{currentUser?.data_level_max || 1}
                    </p>
                </div>
                <div className="w-9 h-9 bg-primary/5 rounded-full flex items-center justify-center text-primary border border-primary/10" title={displayName}>
                    {primaryRole?.includes('ADMIN') ? <ShieldCheck size={18} /> : <User size={18} />}
                </div>
            </div>
        </header>
    );
};

export default Header;
