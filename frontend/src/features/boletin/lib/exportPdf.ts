// PDF del boletín armado en el navegador, página por página, con el tamaño de diseño (900 × 1050).
// La impresión del navegador en el celular usa el ancho de la pantalla y descuadra el documento.

export const PAGE_WIDTH = 900;
export const PAGE_HEIGHT = 1050;
// Ancho de ventana simulado: el documento se arma como en un computador, aunque sea un celular.
const DESKTOP_WIDTH = 1440;

// Al ensanchar el documento, cada gráfica se vuelve a dibujar con el ancho de su recuadro.
function chartsFitTheirBoxes(root: HTMLElement) {
  if (Math.abs(root.querySelector('.newsletter-document')!.getBoundingClientRect().width - PAGE_WIDTH) > 1) return false;
  return Array.from(root.querySelectorAll<HTMLElement>('.recharts-responsive-container')).every((box) => {
    const surface = box.querySelector('svg.recharts-surface');
    return surface && Math.abs(Number(surface.getAttribute('width')) - box.getBoundingClientRect().width) <= 2;
  });
}

async function waitForChartsToFit(root: HTMLElement, maxMs = 5000) {
  const started = Date.now();
  while (Date.now() - started < maxMs && !chartsFitTheirBoxes(root)) {
    await new Promise((resolve) => setTimeout(resolve, 150));
  }
  await new Promise((resolve) => setTimeout(resolve, 150));
}

// Lo que la hoja de impresión oculta o muestra (clases print:* de Tailwind y ayudas de boletin.css).
function applyPrintLook(page: HTMLElement) {
  page.querySelectorAll<HTMLElement>('[class*="print:hidden"], .hide-on-print, .solo-pantalla').forEach((node) => { node.style.display = 'none'; });
  page.querySelectorAll<HTMLElement>('[class*="print:block"]').forEach((node) => { node.style.display = 'block'; });
  Object.assign(page.style, {
    width: `${PAGE_WIDTH}px`, maxWidth: `${PAGE_WIDTH}px`, height: `${PAGE_HEIGHT}px`,
    margin: '0', boxShadow: 'none',
  });
}

export async function downloadBulletinPdf(pages: HTMLElement[], fileName: string, onProgress?: (done: number, total: number) => void) {
  if (!pages.length) throw new Error('No hay páginas del boletín para descargar.');
  const [{ default: html2canvas }, { jsPDF }] = await Promise.all([import('html2canvas-pro'), import('jspdf')]);
  await document.fonts?.ready;
  const root = pages[0].closest<HTMLElement>('.boletin-replica');
  const narrow = pages[0].getBoundingClientRect().width < PAGE_WIDTH - 1;
  if (root && narrow) {
    root.classList.add('pdf-exporting');
    await waitForChartsToFit(root);
  }
  try {
    await renderPages(pages, fileName, html2canvas, jsPDF, onProgress);
  } finally {
    root?.classList.remove('pdf-exporting');
  }
}

type Html2Canvas = typeof import('html2canvas-pro').default;
type JsPdf = typeof import('jspdf').jsPDF;

async function renderPages(pages: HTMLElement[], fileName: string, html2canvas: Html2Canvas, jsPDF: JsPdf, onProgress?: (done: number, total: number) => void) {
  const pdf = new jsPDF({ orientation: 'portrait', unit: 'px', format: [PAGE_WIDTH, PAGE_HEIGHT], hotfixes: ['px_scaling'], compress: true });
  for (const [index, page] of pages.entries()) {
    const marker = `pdf-page-${index}`;
    page.dataset.pdfPage = marker;
    try {
      const canvas = await html2canvas(page, {
        scale: 2,
        backgroundColor: '#ffffff',
        useCORS: true,
        logging: false,
        windowWidth: DESKTOP_WIDTH,
        width: PAGE_WIDTH,
        height: PAGE_HEIGHT,
        onclone: (doc) => {
          const clone = doc.querySelector<HTMLElement>(`[data-pdf-page="${marker}"]`);
          if (clone) applyPrintLook(clone);
        },
      });
      if (index > 0) pdf.addPage([PAGE_WIDTH, PAGE_HEIGHT], 'portrait');
      pdf.addImage(canvas.toDataURL('image/jpeg', 0.92), 'JPEG', 0, 0, PAGE_WIDTH, PAGE_HEIGHT);
    } finally {
      delete page.dataset.pdfPage;
    }
    onProgress?.(index + 1, pages.length);
  }
  pdf.save(fileName);
}
