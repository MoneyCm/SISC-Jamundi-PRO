import { apiFetch, readApiError } from './apiClient';

// Hoja ejecutiva semanal (una página A4, generada en el servidor) para imprimir.
export async function downloadHojaEjecutiva() {
    const response = await apiFetch('/reportes/hoja-ejecutiva');
    if (!response.ok) throw new Error(await readApiError(response, 'No fue posible generar la hoja ejecutiva.'));
    const match = /filename="([^"]+)"/.exec(response.headers.get('Content-Disposition') || '');
    const url = URL.createObjectURL(await response.blob());
    const link = document.createElement('a');
    link.href = url;
    link.download = match ? match[1] : 'Hoja_ejecutiva_SISC.pdf';
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
}
