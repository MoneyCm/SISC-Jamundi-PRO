// Calendario operativo: estados y texto del próximo Consejo.

export const CALENDAR_STATUS = {
    ATRASADO: { label: 'Atrasado', chip: 'bg-red-100 text-red-800' },
    PENDIENTE: { label: 'Pendiente', chip: 'bg-amber-100 text-amber-900' },
    PROXIMO: { label: 'Próximo', chip: 'bg-slate-100 text-slate-600' },
    HECHO: { label: 'Hecho', chip: 'bg-emerald-50 text-emerald-800' },
};

export const councilText = (council) => {
    const days = council.days_to;
    const when = council.source === 'ESTIMADA' && days <= 0
        ? 'esta semana'
        : days === 0 ? 'hoy' : days === 1 ? 'mañana' : `en ${days} días`;
    const origin = { REGISTRADA: 'fecha registrada', ACTA: 'según el acta cargada', ESTIMADA: 'estimado: el Consejo sesiona la última semana del mes' }[council.source];
    return `Próximo Consejo de Seguridad: ${council.label}, ${when} (${origin}).`;
};
