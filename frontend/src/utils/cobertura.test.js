import test from 'node:test';
import assert from 'node:assert/strict';
import { mesesIncompletos, mesesSinDatos, motivoSinTasa, textoCobertura } from './cobertura.js';

test('reúne los meses faltantes sin repetirlos', () => {
    const meses = mesesIncompletos([
        { completa: false, meses_incompletos: ['diciembre de 2025'] },
        { completa: true, meses_incompletos: [] },
        { completa: false, meses_incompletos: ['diciembre de 2025', 'diciembre de 2024'] },
        null,
    ]);
    assert.deepEqual(meses, ['diciembre de 2025', 'diciembre de 2024']);
    assert.match(textoCobertura(meses), /no trae completo: diciembre de 2025, diciembre de 2024\./);
});

test('sin meses faltantes no hay aviso', () => {
    assert.equal(textoCobertura(mesesIncompletos([{ completa: true }])), '');
});

test('lista los meses vacíos de la tendencia', () => {
    assert.deepEqual(mesesSinDatos([{ name: 'Nov 2025' }, { name: 'Dic 2025', sin_datos: true }]), ['Dic 2025']);
});

test('texto ciudadano sin instrucciones internas', () => {
    const texto = textoCobertura(['diciembre de 2025'], { publico: true });
    assert.match(texto, /no incluye completo: diciembre de 2025\./);
    assert.doesNotMatch(texto, /conviene pedir/);
});

test('motivo de la tasa en blanco', () => {
    assert.match(motivoSinTasa({ cobertura: { completa: false } }), /faltan meses/);
    assert.match(motivoSinTasa({ cobertura: { completa: true } }, { territorio: 'Terranova' }), /todo el municipio/);
    assert.match(motivoSinTasa({}), /proyección de población/);
});

test('sin cifras cuando el filtro tiene muy pocos casos', () => {
    assert.match(motivoSinTasa({}, {}, { reason: 'territorio_pocos_casos' }), /muy pocos casos/);
});
