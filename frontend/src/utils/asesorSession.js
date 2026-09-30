const PREFIX = 'sisc_asesor_conversacion';
export const asesorKey = (user) => user?.id || user?.username ? `${PREFIX}:${user.id || user.username}` : null;
export function readAsesor(storage, user) {
  try {
    storage.removeItem(PREFIX); // Old shared conversations have no reliable owner.
    const key = asesorKey(user);
    const messages = key ? JSON.parse(storage.getItem(key) || '[]') : [];
    return Array.isArray(messages) ? messages.filter((message) => message
      && ['usuario', 'asesor'].includes(message.rol) && typeof message.texto === 'string'
      && (!message.fuentes || (Array.isArray(message.fuentes) && message.fuentes.every((x) => typeof x === 'string')))
      && (!message.sugerencias || (Array.isArray(message.sugerencias) && message.sugerencias.every((x) => typeof x === 'string')))).slice(-20) : [];
  } catch { return []; }
}
export function clearAsesor(storage) {
  try {
    for (let i = storage.length - 1; i >= 0; i--) {
      const key = storage.key(i);
      if (key === PREFIX || key?.startsWith(`${PREFIX}:`)) storage.removeItem(key);
    }
  } catch { /* Storage may be unavailable. */ }
}
