// Imagen sencilla para WhatsApp con las metas del PISCC (tabla 16): meta anual, los dos últimos
// años completos con su semáforo, lo que va del año y cómo va. La ven concejales y Policía, así que va en lenguaje llano.
// Se dibuja en un canvas con los mismos datos de la tabla (/observatory/piscc-goals).

const NAVY = '#14325C';
const ORO = '#C9A227';
const TINTA = '#1E293B';
const GRIS = '#5B6575';
const LINEA = '#D5DCE6';
const COLORES = { rojo: '#B42318', ambar: '#B97A00', verde: '#1E7B45', gris: '#64748B' };

// Un indicador dentro de la meta se marca "al límite" si su proyección (o su acumulado, en metas
// pequeñas) llega a este porcentaje de la meta.
export const UMBRAL_LIMITE = 0.95;

const ORDEN = { rojo: 0, ambar: 1, verde: 2, gris: 3 };

const unir = (nombres) => (nombres.length > 1 ? `${nombres.slice(0, -1).join(', ')} y ${nombres[nombres.length - 1]}` : nombres[0] || '');

export const formatoNumero = (valor) => Number(valor).toLocaleString('es-CO');

const fechaLarga = (iso) => new Date(`${iso}T12:00:00`).toLocaleDateString('es-CO', { day: 'numeric', month: 'long', year: 'numeric' });
const mesAnio = (iso) => new Date(`${iso}T12:00:00`).toLocaleDateString('es-CO', { month: 'long', year: 'numeric' });

export const estadoSencillo = (item) => {
    if (item.status === 'SUPERADA') return { color: 'rojo', etiqueta: 'Superó' };
    if (item.status === 'DESVIACION') return { color: 'ambar', etiqueta: 'En riesgo' };
    if (item.status === 'EN_META') {
        const referencia = item.projection ?? item.count;
        const alLimite = referencia != null && item.goal_2027 > 0 && referencia >= item.goal_2027 * UMBRAL_LIMITE;
        return { color: 'verde', etiqueta: alLimite ? 'Al límite' : 'Bien' };
    }
    if (item.status === 'PRELIMINAR') return { color: 'gris', etiqueta: 'Preliminar' };
    return { color: 'gris', etiqueta: 'Sin datos' };
};

// Semáforo de un año cerrado (piscc_historico.semaforo): verde dentro de la meta, ámbar mejor
// que la línea base 2023 sin llegar a la meta, rojo igual o peor que 2023. Sin semáforo (año con
// reportes incompletos), gris.
const COLOR_SEMAFORO = { VERDE: 'verde', AMARILLO: 'ambar', ROJO: 'rojo' };

export const aniosCerrados = (item, anios) => anios.map((anio) => {
    const dato = (item.closed_years || []).find((year) => year.anio === anio);
    const total = dato?.total ?? null;
    return { anio, total, color: total == null ? 'gris' : (COLOR_SEMAFORO[dato.semaforo] || 'gris'), completo: Boolean(dato?.semaforo) };
});

// Datos listos para dibujar; separado del canvas para poder probarlo.
export const prepararMetas = (data) => {
    const indicadores = data?.indicators || [];
    // Los dos últimos años cerrados que trae la tabla (hoy 2024 y 2025).
    const anios = [...new Set(indicadores.flatMap((item) => (item.closed_years || []).map((year) => year.anio)))]
        .sort((a, b) => a - b).slice(-2);
    const filas = indicadores.map((item) => ({
        indicador: item.label,
        casos: item.count,
        meta: item.goal_2027,
        anios: aniosCerrados(item, anios),
        ...estadoSencillo(item),
    }));
    filas.sort((a, b) => ORDEN[a.color] - ORDEN[b.color]);

    // Fuentes agrupadas por corte, sin repetir y sin la aclaración entre paréntesis:
    // "MinDefensa / Policía Nacional y MinDefensa / GAULA Policía, corte 30 de septiembre de 2026".
    const porCorte = new Map();
    indicadores.forEach((item) => {
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
    const anio = indicadores.find((item) => item.cutoff)?.cutoff?.slice(0, 4) || (data?.as_of || '').slice(0, 4);
    const incompletos = filas.some((fila) => fila.anios.some((dato) => dato.total != null && !dato.completo));
    return { filas, fuentes, conteo, anio, anios, incompletos, edicion: data?.as_of ? mesAnio(data.as_of) : '' };
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
    const { filas, fuentes, anio, anios, incompletos, edicion } = prepararMetas(data);
    const W = 1080;
    const M = 60;
    const fuente = (peso, tam) => `${peso} ${tam}px Calibri, Carlito, "Segoe UI", Arial, sans-serif`;
    // Columnas: indicador | meta | años cerrados | año en curso | cómo va el año en curso.
    const COL = { indicador: M + 4, anchoIndicador: 300, meta: 455, anios: [580, 705], actual: 830, estado: 852 };
    const LINEA_NOMBRE = 31;

    const medidor = document.createElement('canvas').getContext('2d');
    medidor.font = fuente(700, 27);
    const alturas = filas.map((fila) => {
        const lineas = partirTexto(medidor, fila.indicador, COL.anchoIndicador);
        return { lineas, alto: Math.max(82, 34 + lineas.length * LINEA_NOMBRE) };
    });
    const altoTabla = alturas.reduce((suma, fila) => suma + fila.alto, 0);
    const titulo = '¿Cómo vamos frente a las metas de seguridad?';
    medidor.font = fuente(700, 46);
    const lineasTitulo = partirTexto(medidor, titulo, W - 2 * M);
    medidor.font = fuente(400, 23);
    const periodo = anios.length ? `Años ${anios.join(' y ')} completos y lo que va de ${anio}, frente a la meta anual del PISCC 2024-2027` : `Lo que va de ${anio} frente a la meta anual del PISCC 2024-2027`;
    const lineasSubtitulo = partirTexto(medidor, `${periodo}${edicion ? ` · ${edicion}` : ''}`, W - 2 * M);
    medidor.font = fuente(400, 18);
    const notaIncompletos = incompletos ? ' Gris: año con reportes incompletos.' : '';
    const lineasFuentes = partirTexto(medidor, `Fuentes: ${fuentes.join(' · ')}. La meta es el máximo de casos al año que se propone el PISCC 2024-2027.${notaIncompletos}`, W - 2 * M);
    // Alto: encabezado y título, tabla, leyenda y pie; nunca menos de 1080 x 1350 (formato 4:5).
    const inicioTabla = 222 + lineasTitulo.length * 54 + (lineasSubtitulo.length - 1) * 30 + 60 + 41;
    const finLeyenda = inicioTabla + altoTabla + 40 + 5 * 30 + 8;
    const altoPie = 32 + (lineasFuentes.length + 1) * 25 + 30;
    const H = Math.max(1350, finLeyenda + 20 + altoPie);

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
    ctx.fillStyle = NAVY; ctx.font = fuente(700, 46);
    let y = 222;
    lineasTitulo.forEach((linea) => { ctx.fillText(linea, M, y); y += 54; });
    ctx.fillStyle = GRIS; ctx.font = fuente(400, 23);
    lineasSubtitulo.forEach((linea, i) => { ctx.fillText(linea, M, y); if (i < lineasSubtitulo.length - 1) y += 30; });

    // Encabezado de la tabla, en dos renglones para que las columnas no se junten
    y += 60;
    ctx.fillStyle = GRIS; ctx.font = fuente(700, 18);
    ctx.fillText('INDICADOR', COL.indicador, y + 23);
    ctx.textAlign = 'right';
    ctx.fillText('META', COL.meta, y); ctx.fillText('ANUAL', COL.meta, y + 23);
    anios.forEach((cerrado, i) => { ctx.fillText('AÑO', COL.anios[i], y); ctx.fillText(String(cerrado), COL.anios[i], y + 23); });
    ctx.fillStyle = NAVY;
    ctx.fillText(String(anio), COL.actual, y); ctx.fillText('A LA FECHA', COL.actual, y + 23);
    ctx.textAlign = 'left';
    ctx.fillText(`CÓMO VA ${anio}`, COL.estado, y + 23);
    y += 38;
    ctx.fillStyle = NAVY; ctx.fillRect(M, y, W - 2 * M, 3);
    y += 3;

    // Cifra en el color del semáforo de ese año (gris si no hay semáforo).
    const cifra = (texto, x, base, color, tam, peso) => {
        ctx.font = fuente(peso, tam);
        ctx.textAlign = 'right';
        ctx.fillStyle = color === 'gris' ? GRIS : COLORES[color];
        ctx.fillText(texto, x, base);
        ctx.textAlign = 'left';
    };

    filas.forEach((fila, i) => {
        const { lineas, alto } = alturas[i];
        const centro = y + alto / 2;
        // En el año en curso se resalta la columna con un fondo suave.
        ctx.fillStyle = '#F1F5F9'; ctx.fillRect(COL.actual - 100, y, 112, alto - 1);
        ctx.fillStyle = TINTA; ctx.font = fuente(700, 27);
        const inicio = centro - ((lineas.length - 1) * LINEA_NOMBRE) / 2 + 9;
        lineas.forEach((linea, j) => ctx.fillText(linea, COL.indicador, inicio + j * LINEA_NOMBRE));
        ctx.textAlign = 'right'; ctx.fillStyle = TINTA; ctx.font = fuente(700, 28);
        ctx.fillText(formatoNumero(fila.meta), COL.meta, centro + 10);
        ctx.textAlign = 'left';
        fila.anios.forEach((dato, j) => cifra(dato.total == null ? '—' : formatoNumero(dato.total), COL.anios[j], centro + 10, dato.color, 28, 400));
        cifra(fila.casos == null ? '—' : formatoNumero(fila.casos), COL.actual, centro + 11, fila.color, 32, 700);
        const color = COLORES[fila.color];
        ctx.fillStyle = color; ctx.beginPath(); ctx.arc(COL.estado + 10, centro, 10, 0, Math.PI * 2); ctx.fill();
        ctx.font = fuente(700, 24);
        ctx.fillText(fila.etiqueta, COL.estado + 28, centro + 8);
        y += alto;
        ctx.fillStyle = LINEA; ctx.fillRect(M, y - 1, W - 2 * M, 1);
    });

    // Leyenda: el estado del año en curso y el color de los años cerrados.
    y += 40;
    const punto = (color, x, base) => { ctx.fillStyle = COLORES[color]; ctx.beginPath(); ctx.arc(x + 7, base - 7, 7, 0, Math.PI * 2); ctx.fill(); };
    const renglon = (color, titulo, texto) => {
        punto(color, M, y);
        ctx.fillStyle = TINTA; ctx.font = fuente(700, 20); ctx.fillText(titulo, M + 24, y);
        const ancho = ctx.measureText(`${titulo} `).width;
        ctx.font = fuente(400, 20); ctx.fillText(texto, M + 24 + ancho, y);
        y += 30;
    };
    renglon('rojo', `Superó (${anio}):`, 'ya hay más casos que el máximo previsto para todo el año.');
    renglon('ambar', 'En riesgo:', 'si sigue al mismo ritmo, terminaría el año por encima de la meta.');
    renglon('verde', 'Bien / Al límite:', 'va por debajo de la meta («al límite» si está muy cerca).');
    if (anios.length) {
        ctx.fillStyle = TINTA; ctx.font = fuente(700, 20);
        ctx.fillText(`Años ${anios.join(' y ')} (año completo), color del número:`, M, y + 4);
        y += 34;
        let x = M;
        [['verde', 'dentro de la meta'], ['ambar', 'mejor que 2023, sin llegar a la meta'], ['rojo', 'igual o peor que 2023']].forEach(([color, texto]) => {
            punto(color, x, y);
            ctx.fillStyle = TINTA; ctx.font = fuente(400, 20); ctx.fillText(texto, x + 22, y);
            x += 22 + ctx.measureText(texto).width + 30;
        });
    }

    // Pie: fuentes y cortes
    let pieY = H - 30 - lineasFuentes.length * 25 - 25;
    ctx.fillStyle = LINEA; ctx.fillRect(M, pieY - 32, W - 2 * M, 1);
    ctx.fillStyle = GRIS; ctx.font = fuente(400, 18);
    lineasFuentes.forEach((linea) => { ctx.fillText(linea, M, pieY); pieY += 25; });
    ctx.fillText('Observatorio del Delito · Sistema de Información para la Seguridad y Convivencia (SISC)', M, pieY);

    return new Promise((resolve, reject) => canvas.toBlob((blob) => (blob ? resolve(blob) : reject(new Error('No se pudo crear la imagen.'))), 'image/png'));
}
