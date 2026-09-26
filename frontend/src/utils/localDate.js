// Fecha de hoy en la hora local del navegador (Colombia), no en UTC:
// toISOString() adelanta un día desde las 7 p. m.
export const localToday = (now = new Date()) => {
    const pad = (value) => String(value).padStart(2, '0');
    return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
};
