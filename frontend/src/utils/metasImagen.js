// Imagen sencilla para WhatsApp con las metas del PISCC (tabla 16): casos del año, meta anual,
// diferencia con el año pasado y un semáforo. La ven concejales y Policía, así que va en lenguaje llano.
// Se dibuja en un canvas con los mismos datos de la tabla (/observatory/piscc-goals).

const NAVY = '#14325C';
const ORO = '#C9A227';
const TINTA = '#1E293B';
const GRIS = '#5B6575';
const LINEA = '#D5DCE6';
const COLORES = { rojo: '#B42318', ambar: '#C2410C', verde: '#1E7B45', gris: '#64748B' };

// Un indicador dentro de la meta se marca "al límite" si su proyección (o su acumulado, en metas
// pequeñas) llega a este porcentaje de la meta.
export const UMBRAL_LIMITE = 0.95;

const ORDEN = { rojo: 0, ambar: 1, verde: 2, gris: 3 };

const unir = (nombres) => (nombres.length > 1 ? `${nombres.slice(0, -1).join(', ')} y ${nombres[nombres.length - 1]}` : nombres[0] || '');

export const formatoNumero = (valor) => Number(valor).toLocaleString('es-CO');

const fechaLarga = (iso) => new Date(`${iso}T12:00:00`).toLocaleDateString('es-CO', { day: 'numeric', month: 'long', year: 'numeric' });
const mesAnio = (iso) => new Date(`${iso}T12:00:00`).toLocaleDateString('es-CO', { month: 'long', year: 'numeric' });

export const estadoSencillo = (item) => {
    if (item.status === 'SUPERADA') return { color: 'rojo', etiqueta: 'Superó la meta' };
    if (item.status === 'DESVIACION') return { color: 'ambar', etiqueta: 'En riesgo' };
    if (item.status === 'EN_META') {
        const referencia = item.projection ?? item.count;
        const alLimite = referencia != null && item.goal_2027 > 0 && referencia >= item.goal_2027 * UMBRAL_LIMITE;
        return { color: 'verde', etiqueta: alLimite ? 'Bien (al límite)' : 'Bien' };
    }
    if (item.status === 'PRELIMINAR') return { color: 'gris', etiqueta: 'Preliminar' };
    return { color: 'gris', etiqueta: 'Sin datos' };
};

export const frenteAnioPasado = (item) => {
    if (item.count == null || item.previous == null) return '—';
    const diferencia = item.count - item.previous;
    if (diferencia > 0) return `▲ ${formatoNumero(diferencia)} más`;
    if (diferencia < 0) return `▼ ${formatoNumero(-diferencia)} menos`;
    return 'igual';
};

// Datos listos para dibujar; separado del canvas para poder probarlo.
export const prepararMetas = (data) => {
    const filas = (data?.indicators || []).map((item) => ({
        indicador: item.label,
        casos: item.count,
        meta: item.goal_2027,
        frente: frenteAnioPasado(item),
        ...estadoSencillo(item),
    }));
    filas.sort((a, b) => ORDEN[a.color] - ORDEN[b.color]);

    // Fuentes agrupadas por corte, sin repetir y sin la aclaración entre paréntesis:
    // "MinDefensa / Policía Nacional y MinDefensa / GAULA Policía, corte 30 de septiembre de 2026".
    const porCorte = new Map();
    (data?.indicators || []).forEach((item) => {
        if (!item.source || !item.cutoff) return;
        const nombre = item.source.replace(/\s*\(.*\)\s*$/, '').trim();
        if (!porCorte.has(item.cutoff)) porCorte.set(item.cutoff, []);
        if (!porCorte.get(item.cutoff).includes(nombre)) porCorte.get(item.cutoff).push(nombre);
    });
    const fuentes = [...porCorte.entries()]
        .sort(([a], [b]) => a.localeCompare(b))
        .map(([corte, nombres]) => `${unir(nombres)}, corte ${fechaLarga(corte)}`);

    const conteo = { rojo: 0, ambar: 0, verde: 0, gris: 0 };
    filas.forEach((fila) => { conteo[fila.color] += 1; });
    const anio = (data?.indicators || []).find((item) => item.cutoff)?.cutoff?.slice(0, 4) || (data?.as_of || '').slice(0, 4);
    return {
        filas,
        fuentes,
        conteo,
        anio,
        edicion: data?.as_of ? mesAnio(data.as_of) : '',
    };
};

const cargarImagen = (src) => new Promise((resolve) => {
    const imagen = new Image();
    imagen.onload = () => resolve(imagen);
    imagen.onerror = () => resolve(null);
    imagen.src = src;
});

const partirTexto = (ctx, texto, ancho) => {
    const lineas = [];
    let actual = '';
    String(texto).split(' ').forEach((palabra) => {
        const prueba = actual ? `${actual} ${palabra}` : palabra;
        if (ctx.measureText(prueba).width > ancho && actual) { lineas.push(actual); actual = palabra; } else { actual = prueba; }
    });
    if (actual) lineas.push(actual);
    return lineas;
};

export async function crearImagenMetas(data, { escudo = '/boletin-escudo.png' } = {}) {
    const { filas, fuentes, anio, edicion } = prepararMetas(data);
    const W = 1080;
    const M = 60;
    const fuente = (peso, tam) => `${peso} ${tam}px Calibri, Carlito, "Segoe UI", Arial, sans-serif`;
    // Columnas: indicador | casos | meta | frente al año pasado | cómo vamos.
    const COL = { indicador: M + 4, anchoIndicador: 350, casos: 530, meta: 640, frente: 805, estado: 825 };

    const medidor = document.createElement('canvas').getContext('2d');
    medidor.font = fuente(700, 29);
    const alturas = filas.map((fila) => {
        const lineas = partirTexto(medidor, fila.indicador, COL.anchoIndicador);
        return { lineas, alto: Math.max(82, 36 + lineas.length * 33) };
    });
    const altoTabla = alturas.reduce((suma, fila) => suma + fila.alto, 0);
    medidor.font = fuente(700, 50);
    const lineasTitulo = partirTexto(medidor, '¿Cómo vamos frente a las metas de seguridad?', W - 2 * M);
    medidor.font = fuente(400, 18);
    const lineasFuentes = partirTexto(medidor, `Fuentes: ${fuentes.join(' · ')}. La meta es el máximo de casos al año que se propone el PISCC 2024-2027.`, W - 2 * M);
    // Alto: encabezado y título, tabla, leyenda y pie; nunca menos de 1080 x 1350 (formato 4:5).
    const inicioTabla = 230 + lineasTitulo.length * 58 + 64 + 40;
    const finLeyenda = inicioTabla + altoTabla + 44 + 3 * 32;
    const altoPie = 32 + (lineasFuentes.length + 1) * 25 + 34;
    const H = Math.max(1350, finLeyenda + 24 + altoPie);

    const canvas = document.createElement('canvas');
    canvas.width = W; canvas.height = H;
    const ctx = canvas.getContext('2d');
    ctx.fillStyle = '#FFFFFF'; ctx.fillRect(0, 0, W, H);

    // Membrete
    ctx.fillStyle = NAVY; ctx.fillRect(0, 0, W, 144);
    ctx.fillStyle = ORO; ctx.fillRect(0, 144, W, 6);
    const imagen = await cargarImagen(escudo);
    let textoX = M;
    if (imagen) {
        ctx.fillStyle = '#FFFFFF'; ctx.beginPath(); ctx.roundRect(M, 26, 72, 92, 6); ctx.fill();
        const alto = 80; const ancho = alto * (imagen.width / imagen.height);
        ctx.drawImage(imagen, M + (72 - ancho) / 2, 32, ancho, alto);
        textoX = M + 92;
    }
    ctx.fillStyle = '#FFFFFF'; ctx.font = fuente(700, 32); ctx.fillText('ALCALDÍA DE JAMUNDÍ', textoX, 68);
    ctx.fillStyle = '#D6E0EE'; ctx.font = fuente(400, 22);
    ctx.fillText('Secretaría de Seguridad y Convivencia · Observatorio del Delito', textoX, 102);

    // Título
    ctx.fillStyle = NAVY; ctx.font = fuente(700, 50);
    let y = 230;
    lineasTitulo.forEach((linea) => { ctx.fillText(linea, M, y); y += 58; });
    ctx.fillStyle = GRIS; ctx.font = fuente(400, 24);
    ctx.fillText(`Casos de ${anio} y meta anual del PISCC 2024-2027${edicion ? ` · ${edicion}` : ''}`, M, y);

    // Encabezado de la tabla, en dos renglones para que las columnas no se junten
    y += 64;
    ctx.fillStyle = GRIS; ctx.font = fuente(700, 19);
    ctx.fillText('INDICADOR', COL.indicador, y + 24);
    ctx.textAlign = 'right';
    [['CASOS', anio, COL.casos], ['META', 'ANUAL', COL.meta], ['FRENTE', `A ${Number(anio) - 1}`, COL.frente]].forEach(([arriba, abajo, x]) => {
        ctx.fillText(arriba, x, y); ctx.fillText(abajo, x, y + 24);
    });
    ctx.textAlign = 'left';
    ctx.fillText('CÓMO VAMOS', COL.estado, y + 24);
    y += 38;
    ctx.fillStyle = NAVY; ctx.fillRect(M, y, W - 2 * M, 3);
    y += 3;

    filas.forEach((fila, i) => {
        const { lineas, alto } = alturas[i];
        const centro = y + alto / 2;
        const color = COLORES[fila.color];
        ctx.fillStyle = TINTA; ctx.font = fuente(700, 29);
        const inicio = centro - ((lineas.length - 1) * 33) / 2 + 10;
        lineas.forEach((linea, j) => ctx.fillText(linea, COL.indicador, inicio + j * 33));
        ctx.textAlign = 'right';
        ctx.fillStyle = color; ctx.font = fuente(700, 34);
        ctx.fillText(fila.casos == null ? '—' : formatoNumero(fila.casos), COL.casos, centro + 12);
        ctx.fillStyle = GRIS; ctx.font = fuente(400, 29);
        ctx.fillText(formatoNumero(fila.meta), COL.meta, centro + 10);
        ctx.font = fuente(400, 25);
        ctx.fillText(fila.frente, COL.frente, centro + 9);
        ctx.textAlign = 'left';
        ctx.fillStyle = color; ctx.beginPath(); ctx.arc(COL.estado + 11, centro, 11, 0, Math.PI * 2); ctx.fill();
        ctx.font = fuente(700, 25);
        ctx.fillText(fila.etiqueta, COL.estado + 32, centro + 9);
        y += alto;
        ctx.fillStyle = LINEA; ctx.fillRect(M, y - 1, W - 2 * M, 1);
    });

    // Leyenda
    y += 44;
    [
        ['rojo', 'Superó la meta:', 'ya hay más casos que el máximo previsto para todo el año.'],
        ['ambar', 'En riesgo:', 'si sigue al mismo ritmo, terminaría el año por encima de la meta.'],
        ['verde', 'Bien:', 'va por debajo de la meta («al límite» si está muy cerca).'],
    ].forEach(([color, titulo, texto]) => {
        ctx.fillStyle = COLORES[color]; ctx.beginPath(); ctx.arc(M + 8, y - 7, 8, 0, Math.PI * 2); ctx.fill();
        ctx.fillStyle = TINTA; ctx.font = fuente(700, 21); ctx.fillText(titulo, M + 26, y);
        const ancho = ctx.measureText(`${titulo} `).width;
        ctx.font = fuente(400, 21); ctx.fillText(texto, M + 26 + ancho, y);
        y += 32;
    });

    // Pie: fuentes y cortes
    let pieY = H - 34 - lineasFuentes.length * 25 - 25;
    ctx.fillStyle = LINEA; ctx.fillRect(M, pieY - 32, W - 2 * M, 1);
    ctx.fillStyle = GRIS; ctx.font = fuente(400, 18);
    lineasFuentes.forEach((linea) => { ctx.fillText(linea, M, pieY); pieY += 25; });
    ctx.fillText('Observatorio del Delito · Sistema de Información para la Seguridad y Convivencia (SISC)', M, pieY);

    return new Promise((resolve, reject) => canvas.toBlob((blob) => (blob ? resolve(blob) : reject(new Error('No se pudo crear la imagen.'))), 'image/png'));
}
