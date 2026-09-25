import { getDocument, GlobalWorkerOptions } from 'pdfjs-dist';
import workerUrl from 'pdfjs-dist/build/pdf.worker.min.mjs?url';

GlobalWorkerOptions.workerSrc = workerUrl;

export async function extractOperations(data: Uint8Array) {
  const task = getDocument({ data, isEvalSupported: false });
  try {
    const document = await task.promise;
    let text = '';
    for (let page = 1; page <= document.numPages; page++) {
      const content = await (await document.getPage(page)).getTextContent();
      text += content.items.map(item => 'str' in item ? item.str : '').join(' ') + '\n';
    }
    if (!text.trim()) throw new Error('El PDF no contiene texto extraíble.');
    const count = (...keywords: string[]) => {
      for (const keyword of keywords) {
        const match = text.match(new RegExp(`${keyword}[^0-9]*([0-9]+)`, 'i'));
        if (match) return Number(match[1]);
      }
      return 0;
    };
    return {
      capturas: count('capturas', 'captura'),
      armasIncautadas: count('armas incautadas', 'armas de fuego', 'armas'),
      estupefacientes: count('estupefacientes', 'kilos de marihuana', 'marihuana'),
      motosRecuperadas: count('motos recuperadas', 'vehículos recuperados', 'motos'),
    };
  } finally { await task.destroy(); }
}
