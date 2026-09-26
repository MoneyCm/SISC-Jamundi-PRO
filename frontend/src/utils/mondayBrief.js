// Resumen del lunes: color de cada respuesta y la frase de arriba.

export const BRIEF_LEVELS = {
    ALTA: { label: 'Actuar ya', badge: 'bg-red-600 text-white' },
    MEDIA: { label: 'Revisar esta semana', badge: 'bg-amber-400 text-slate-950' },
    INFO: { label: 'Contexto', badge: 'bg-slate-200 text-slate-700' },
    OK: { label: 'Al día', badge: 'bg-emerald-100 text-emerald-800' },
};

export const briefHeadline = (data) => {
    const urgent = data.answers.filter((item) => item.level === 'ALTA').length;
    if (!data.attention) return 'Las ocho respuestas están al día.';
    const parts = [`${data.attention} de 8 piden atención`];
    if (urgent) parts.push(`${urgent} ${urgent === 1 ? 'es' : 'son'} para actuar ya`);
    return `${parts.join('; ')}. Rojo: actuar ya · Ámbar: esta semana · Verde: al día.`;
};
