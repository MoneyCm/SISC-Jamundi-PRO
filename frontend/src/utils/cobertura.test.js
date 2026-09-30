import test from 'node:test';
import assert from 'node:assert/strict';
import { mesesIncompletos, mesesSinDatos, textoCobertura } from './cobertura.js';

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
