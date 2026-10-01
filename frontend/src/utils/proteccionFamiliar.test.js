import test from 'node:test';
import assert from 'node:assert/strict';
import { agruparPorTema, describir, esPublicable, fechaLarga, rangoPeriodo, resumenComisaria } from './proteccionFamiliar.js';

const fila = (indicator, value, extra = {}) => ({ indicator, value, period: '2026-06', reporting_basis: 'CUMULATIVE', ...extra });

test('nombres claros y siglas explicadas', () => {
    assert.equal(describir('Casos con poblacion migrante involucrada').nombre, 'Casos con población migrante');
    assert.match(describir('Procesos Administrativos de Restablecimiento de Derechos').explicacion, /PARD/);
    assert.equal(describir('Verificaciones de derechos de NNA').nombre, 'Verificaciones de derechos de niñas, niños y adolescentes');
    assert.equal(describir('Indicador nuevo').tema, 'otros');
});

test('los conteos por barrio no se publican', () => {
    assert.equal(esPublicable(fila('Denuncias en Terranova', 19)), false);
    const temas = agruparPorTema([fila('Denuncias en Bonanza', 14), fila('Audiencias realizadas', 234), fila('Casos en poblacion mestiza', 102)]);
    assert.deepEqual(temas.map((t) => t.id), ['atencion', 'quienes']);
    assert.match(temas[1].nota, /No indican/);
});

test('resumen de una comisaría', () => {
    const texto = resumenComisaria('Comisaría Primera de Familia', [
        fila('Nuevos procesos de violencia en el contexto familiar', 145),
        fila('Casos de violencia contra mujeres en el contexto familiar', 124),
        fila('Medidas de proteccion urgentes', 65),
    ]);
    assert.equal(texto, 'Comisaría Primera de Familia: 145 casos nuevos de violencia en la familia (enero a junio de 2026); 86 % contra mujeres; 65 medidas de protección urgentes.');
    assert.equal(resumenComisaria('X', [fila('Audiencias realizadas', 3)]), null);
});

test('fechas legibles', () => {
    assert.equal(fechaLarga('2026-06-24'), '24 de junio de 2026');
    assert.equal(rangoPeriodo('2026-06'), 'enero a junio de 2026');
    assert.equal(rangoPeriodo('2026-01'), 'enero de 2026');
});

test('lo principal primero dentro del tema', () => {
    const temas = agruparPorTema([fila('Casos de violencia contra hombres en el contexto familiar', 23),
        fila('Nuevos procesos de violencia en el contexto familiar', 148)]);
    assert.equal(temas[0].registros[0].nombre, 'Nuevos casos de violencia en la familia');
});
