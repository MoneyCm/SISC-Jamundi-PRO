// Imagen vertical para WhatsApp con la comparación de municipios (Contexto comparado).
// Se dibuja en un canvas: no depende de lo que se vea en pantalla, así que salen todas las filas.

const AZUL = '#281FD0';
const TINTA = '#0F172A';
const GRIS = '#64748B';
const ROJO = '#DC2626';
const VERDE = '#047857';

export const formatoNumero = (valor, decimales = 0) => Number(valor).toLocaleString('es-CO', {
    minimumFractionDigits: decimales, maximumFractionDigits: decimales,
});

// Datos listos para dibujar; separado del canvas para poder probarlo.
export const prepararRanking = ({ rows = [], objetivo }) => {
    const filas = rows.filter((row) => row.tasa_por_100k != null);
    const maxima = Math.max(...filas.map((row) => Number(row.tasa_por_100k)), 1);
    const meta = filas.find((row) => row.es_objetivo) || filas.find((row) => row.municipio === objetivo);
    return {
        filas: filas.map((row) => ({
            posicion: row.posicion,
            municipio: row.municipio,
            casos: row.casos,
            tasa: Number(row.tasa_por_100k),
            proporcion: Number(row.tasa_por_100k) / maxima,
            diferencia: row.es_objetivo ? null : row.diferencia_tasa_objetivo,
            objetivo: Boolean(row.es_objetivo),
        })),
        objetivo: meta ? { posicion: meta.posicion, municipio: meta.municipio, tasa: Number(meta.tasa_por_100k), casos: meta.casos } : null,
        total: filas.length,
    };
};

const cargarImagen = (src) => new Promise((resolve) => {
    const imagen = new Image();
    imagen.onload = () => resolve(imagen);
    imagen.onerror = () => resolve(null);
    imagen.src = src;
});

const partirTexto = (ctx, texto, ancho) => {
    const palabras = String(texto).split(' ');
    const lineas = [];
    let actual = '';
    palabras.forEach((palabra) => {
        const prueba = actual ? `${actual} ${palabra}` : palabra;
        if (ctx.measureText(prueba).width > ancho && actual) { lineas.push(actual); actual = palabra; } else { actual = prueba; }
    });
    if (actual) lineas.push(actual);
    return lineas;
};

export async function crearImagenRanking({ rows, objetivo, conducta, periodo, corte, alcance, unidad = 'casos' }) {
    const { filas, objetivo: meta, total } = prepararRanking({ rows, objetivo });
    const W = 1080;
    const FILA = 92;
    const arriba = 520;
    const H = Math.max(1350, arriba + filas.length * FILA + 330);
    const canvas = document.createElement('canvas');
    canvas.width = W; canvas.height = H;
    const ctx = canvas.getContext('2d');
    const fuente = (peso, tam) => `${peso} ${tam}px "Segoe UI", Arial, sans-serif`;

    ctx.fillStyle = '#FFFFFF'; ctx.fillRect(0, 0, W, H);
    ctx.fillStyle = AZUL; ctx.fillRect(0, 0, W, 150);
    ctx.fillStyle = '#FFE000'; ctx.fillRect(0, 150, W, 8);
    const escudo = await cargarImagen('/boletin-escudo.png');
    if (escudo) ctx.drawImage(escudo, 56, 22, 84, 106);
    ctx.fillStyle = '#FFFFFF';
    ctx.font = fuente(900, 40); ctx.fillText('SISC Jamundí', escudo ? 164 : 56, 78);
    ctx.font = fuente(600, 24); ctx.fillText('Observatorio del Delito · Secretaría de Seguridad y Convivencia', escudo ? 164 : 56, 116);

    ctx.fillStyle = TINTA; ctx.font = fuente(900, 50);
    let y = 240;
    partirTexto(ctx, `${conducta}: ${objetivo} frente a municipios comparables`, W - 112).forEach((linea) => { ctx.fillText(linea, 56, y); y += 60; });
    ctx.fillStyle = GRIS; ctx.font = fuente(600, 28);
    ctx.fillText(`Tasa por 100.000 habitantes · ${periodo} · ${alcance}`, 56, y + 6);

    if (meta) {
        const cajaY = y + 40;
        ctx.fillStyle = '#EEF2FF'; ctx.beginPath(); ctx.roundRect(56, cajaY, W - 112, 110, 22); ctx.fill();
        ctx.fillStyle = AZUL; ctx.font = fuente(900, 44);
        ctx.fillText(`${meta.municipio}: puesto ${meta.posicion} de ${total}`, 88, cajaY + 58);
        ctx.fillStyle = TINTA; ctx.font = fuente(600, 28);
        ctx.fillText(`Tasa ${formatoNumero(meta.tasa, 2)} · ${formatoNumero(meta.casos)} ${unidad}`, 88, cajaY + 94);
        y = cajaY + 110;
    }

    let filaY = Math.max(arriba, y + 50);
    ctx.font = fuente(900, 32);
    const anchoCifra = Math.max(...filas.map((f) => ctx.measureText(formatoNumero(f.tasa, 2)).width), 0);
    const anchoBarra = Math.max(120, 1010 - anchoCifra - 28 - 600);
    ctx.fillStyle = GRIS; ctx.font = fuente(800, 22);
    ctx.fillText('#', 70, filaY - 18); ctx.fillText('MUNICIPIO', 130, filaY - 18);
    ctx.textAlign = 'right'; ctx.fillText('TASA', 1010, filaY - 18); ctx.textAlign = 'left';
    filas.forEach((fila) => {
        if (fila.objetivo) { ctx.fillStyle = '#E0E7FF'; ctx.fillRect(40, filaY, W - 80, FILA - 8); }
        ctx.fillStyle = fila.objetivo ? AZUL : TINTA;
        ctx.font = fuente(900, 32); ctx.fillText(String(fila.posicion ?? '—'), 70, filaY + 40);
        ctx.font = fuente(fila.objetivo ? 900 : 700, 30); ctx.fillText(fila.municipio, 130, filaY + 38);
        ctx.fillStyle = GRIS; ctx.font = fuente(600, 21);
        const diferencia = fila.diferencia == null ? 'Base de comparación'
            : `${fila.diferencia > 0 ? '+' : ''}${formatoNumero(fila.diferencia, 2)} pts. vs ${objetivo}`;
        ctx.fillText(`${formatoNumero(fila.casos)} ${unidad} · ${diferencia}`, 130, filaY + 70);
        // La barra termina antes de la cifra más ancha, para que nunca se monten.
        const barraX = 600; const barraW = anchoBarra;
        ctx.fillStyle = '#E2E8F0'; ctx.beginPath(); ctx.roundRect(barraX, filaY + 26, barraW, 18, 9); ctx.fill();
        ctx.fillStyle = fila.objetivo ? AZUL : fila.diferencia > 0 ? ROJO : VERDE;
        ctx.beginPath(); ctx.roundRect(barraX, filaY + 26, Math.max(10, barraW * fila.proporcion), 18, 9); ctx.fill();
        ctx.fillStyle = fila.objetivo ? AZUL : TINTA; ctx.font = fuente(900, 32); ctx.textAlign = 'right';
        ctx.fillText(formatoNumero(fila.tasa, 2), 1010, filaY + 44); ctx.textAlign = 'left';
        ctx.fillStyle = '#E2E8F0'; ctx.fillRect(56, filaY + FILA - 4, W - 112, 2);
        filaY += FILA;
    });

    ctx.fillStyle = GRIS; ctx.font = fuente(600, 21);
    let pieY = H - 190;
    [
        'Rojo: tasa mayor que la de Jamundí · Verde: tasa menor.'.replace('Jamundí', objetivo),
        `Fuente: MinDefensa / Policía Nacional (datos.gov.co), corte ${corte}. Población: proyecciones DANE.`,
        'Cifras de enero a la fecha de corte; no son del año completo. Los municipios pequeños varían más.',
        `Elaborado por el SISC Jamundí el ${new Date().toLocaleDateString('es-CO', { day: 'numeric', month: 'long', year: 'numeric' })}.`,
    ].forEach((linea) => partirTexto(ctx, linea, W - 112).forEach((parte) => { ctx.fillText(parte, 56, pieY); pieY += 32; }));

    return new Promise((resolve, reject) => canvas.toBlob((blob) => (blob ? resolve(blob) : reject(new Error('No se pudo crear la imagen.'))), 'image/png'));
}

// En el celular abre "Compartir" (para elegir WhatsApp); si no se puede, descarga el archivo.
export async function compartirImagen(blob, nombre, texto) {
    const archivo = new File([blob], nombre, { type: 'image/png' });
    if (navigator.canShare?.({ files: [archivo] })) {
        try {
            await navigator.share({ files: [archivo], text: texto });
            return 'compartida';
        } catch (error) {
            if (error?.name === 'AbortError') return 'cancelada';
        }
    }
    const url = URL.createObjectURL(blob);
    const enlace = document.createElement('a');
    enlace.href = url; enlace.download = nombre;
    document.body.appendChild(enlace); enlace.click(); enlace.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    return 'descargada';
}
