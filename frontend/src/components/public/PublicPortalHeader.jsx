import React, { useState } from 'react';
import { LockKeyhole, Menu, X } from 'lucide-react';

const NAV_ITEMS = [
    { label: 'Inicio', page: 'hub' },
    { label: 'Explorar datos', page: 'transparency' },
    { label: 'Mapa', page: 'transparency', hash: 'mapa' },
    { label: 'Mi barrio', page: 'hub', hash: 'mi-barrio' },
    { label: 'SISC en cifras', page: 'sisc-cifras' },
    { label: 'Boletines', page: 'technical-bulletins' },
    { label: 'Datos abiertos', page: 'open-data' },
    { label: 'Metodología', page: 'transparency-info' },
];

const PublicPortalHeader = ({ currentPage = 'hub', onNavigate, onLoginClick }) => {
    const [open, setOpen] = useState(false);

    const navigate = (item) => {
        setOpen(false);
        if (item.page === currentPage && item.hash) {
            document.getElementById(item.hash)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
            return;
        }
        onNavigate?.(item.page, { hash: item.hash });
    };

    return (
        <header className="sticky top-0 z-[1001] border-b border-slate-200 bg-white/95 backdrop-blur">
            <div className="mx-auto flex min-h-16 max-w-[1440px] items-center gap-4 px-4 md:px-6">
                <button onClick={() => navigate({ page: 'hub' })} className="flex shrink-0 items-center gap-3 text-left" aria-label="Ir al inicio del portal ciudadano">
                    <img src="/assets/escudo-limpio.png" alt="" className="h-11 w-9 object-contain" />
                    <span className="leading-none">
                        <strong className="block text-lg font-black tracking-tight text-[#281FD0]">SISC Jamundí</strong>
                        <span className="mt-1 block text-[9px] font-bold uppercase tracking-[0.12em] text-slate-500">Alcaldía de Jamundí</span>
                    </span>
                </button>

                <nav className="ml-auto hidden items-center gap-0.5 xl:flex" aria-label="Navegación principal">
                    {NAV_ITEMS.map((item) => (
                        <button
                            key={`${item.page}-${item.hash || 'top'}`}
                            onClick={() => navigate(item)}
                            className={`min-h-11 px-3 text-[12px] font-bold transition-colors hover:text-[#281FD0] ${currentPage === item.page ? 'text-[#281FD0]' : 'text-slate-600'}`}
                        >
                            {item.label}
                        </button>
                    ))}
                </nav>

                <button onClick={onLoginClick} className="ml-auto hidden min-h-11 items-center gap-2 border-l border-slate-200 pl-4 text-xs font-bold text-slate-600 hover:text-[#281FD0] sm:inline-flex xl:ml-2">
                    <LockKeyhole size={16} /> Ingreso institucional
                </button>
                <button onClick={() => setOpen((value) => !value)} className="ml-auto inline-flex h-11 w-11 items-center justify-center border border-slate-200 text-slate-700 xl:hidden" aria-expanded={open} aria-controls="public-mobile-menu" aria-label={open ? 'Cerrar menú' : 'Abrir menú'}>
                    {open ? <X size={22} /> : <Menu size={22} />}
                </button>
            </div>
            {open && (
                <div id="public-mobile-menu" className="border-t border-slate-200 bg-white px-4 py-3 xl:hidden">
                    <nav className="grid gap-1 sm:grid-cols-2" aria-label="Navegación móvil">
                        {NAV_ITEMS.map((item) => (
                            <button key={`${item.page}-${item.hash || 'top'}`} onClick={() => navigate(item)} className="min-h-11 px-3 text-left text-sm font-bold text-slate-700 hover:bg-slate-50 hover:text-[#281FD0]">
                                {item.label}
                            </button>
                        ))}
                        <button onClick={() => { setOpen(false); onLoginClick?.(); }} className="inline-flex min-h-11 items-center gap-2 px-3 text-left text-sm font-bold text-slate-700 hover:bg-slate-50 hover:text-[#281FD0] sm:hidden">
                            <LockKeyhole size={16} /> Ingreso institucional
                        </button>
                    </nav>
                </div>
            )}
        </header>
    );
};

export default PublicPortalHeader;
