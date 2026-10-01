import test from 'node:test';
import assert from 'node:assert/strict';
import { fechaActa, filtrarActas, resumenPorInstancia, sinActaOficial, tamanoArchivo } from './archivoActas.js';

const actas = [
    { read_id: '1', instance: 'CONSEJO_SEGURIDAD', instance_label: 'Consejo de Seguridad', act_date: '2026-09-21', status: 'CONFIRMADA', has_file: false, filename: 'Nota de Gemini – Consejo (sin acta oficial)' },
    { read_id: '2', instance: 'CONSEJO_SEGURIDAD', instance_label: 'Consejo de Seguridad', act_date: '2025-03-10', status: 'HISTORICA', has_file: true, filename: 'Acta 03.pdf' },
    { read_id: '3', instance: 'COMITE_ORDEN_PUBLICO', instance_label: 'Comité de Orden Público', act_date: '2026-07-16', status: 'PENDIENTE', has_file: false, filename: 'COP julio.docx' },
];

test('resumen por instancia', () => {
    const [consejo, cop] = resumenPorInstancia(actas);
    assert.deepEqual([consejo.total, consejo.sinArchivo, consejo.sinOficial, consejo.ultima], [2, 1, 1, '2026-09-21']);
    assert.deepEqual([cop.total, cop.pendientes], [1, 1]);
});

test('filtros y marcas', () => {
    assert.equal(filtrarActas(actas, { anio: '2026' }).length, 2);
    assert.equal(filtrarActas(actas, { instancia: 'CONSEJO_SEGURIDAD', estado: 'HISTORICA' }).length, 1);
    assert.equal(sinActaOficial(actas[0]), true);
    assert.equal(sinActaOficial(actas[1]), false);
    assert.equal(fechaActa('2026-09-21'), '21 de septiembre de 2026');
    assert.equal(tamanoArchivo(350 * 1024), '350 KB');
    assert.equal(tamanoArchivo(2.5 * 1024 * 1024), '2,5 MB');
});
