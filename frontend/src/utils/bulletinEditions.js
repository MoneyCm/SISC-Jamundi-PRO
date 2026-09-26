// Boletines publicados: nombre de la edición y periodo legibles, y la lista separada por edición.

const MONTHS = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre'];

export const EDITIONS = [
    { type: 'monthly', label: 'Boletín mensual', group: 'Mensuales' },
    { type: 'weekly', label: 'Boletín semanal', group: 'Semanales' },
    { type: 'semester', label: 'Boletín semestral', group: 'Semestrales' },
    { type: 'annual', label: 'Boletín anual', group: 'Anuales' },
];

const parts = (iso) => {
    const [year, month, day] = String(iso || '').slice(0, 10).split('-').map(Number);
    return { year, month, day };
};
const lastDay = (year, month) => new Date(Date.UTC(year, month, 0)).getUTCDate();
const longDate = ({ day, month, year }) => `${day} de ${MONTHS[month - 1]} de ${year}`;

export const editionLabel = (type) => EDITIONS.find((item) => item.type === type)?.label || 'Boletín';

export const bulletinPeriod = ({ edition_type: type, period_start: startIso, period_end: endIso }) => {
    const start = parts(startIso);
    const end = parts(endIso);
    if (!start.year || !end.year) return '';
    const fullMonth = start.day === 1 && start.month === end.month && start.year === end.year && end.day === lastDay(end.year, end.month);
    if (type === 'monthly' && fullMonth) {
        const name = MONTHS[start.month - 1];
        return `${name.charAt(0).toUpperCase()}${name.slice(1)} de ${start.year}`;
    }
    if (start.year === end.year && start.month === end.month) {
        return `Del ${start.day} al ${end.day} de ${MONTHS[end.month - 1]} de ${end.year}`;
    }
    return `Del ${longDate(start)} al ${longDate(end)}`;
};

/** Grupos en el orden de EDITIONS, solo los que tienen boletines; conserva el orden recibido dentro de cada uno. */
export const groupByEdition = (rows) => {
    const known = EDITIONS.map((edition) => ({ ...edition, items: rows.filter((row) => row.edition_type === edition.type) }));
    const other = rows.filter((row) => !EDITIONS.some((edition) => edition.type === row.edition_type));
    return [...known, { type: 'other', label: 'Boletín', group: 'Otros', items: other }].filter((group) => group.items.length);
};
