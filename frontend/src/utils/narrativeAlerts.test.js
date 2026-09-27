import test from 'node:test';
import assert from 'node:assert/strict';
import { checkText, cleanLines, formatProbability, whatsappUrl } from './narrativeAlerts.js';

test('las líneas vacías no cuentan', () => {
    assert.deepEqual(cleanLines('uno\n\n  \ndos  '), ['uno', 'dos']);
    assert.deepEqual(checkText('uno\n\ndos'), { lines: 2, chars: 7, error: '' });
});

test('máximo seis líneas y texto no vacío', () => {
    assert.match(checkText(['a', 'b', 'c', 'd', 'e', 'f', 'g'].join('\n')).error, /7 líneas/);
    assert.match(checkText('   ').error, /vacío/);
    assert.match(checkText('x'.repeat(1201)).error, /caracteres/);
});

test('cada tipo tiene su propio límite', () => {
    const twelve = Array.from({ length: 12 }, (_, i) => `línea ${i}`).join('\n');
    assert.equal(checkText(twelve, 12, 2400).error, '');
    assert.match(checkText(twelve, 10, 2000).error, /12 líneas; el máximo es 10/);
});

test('enlace de WhatsApp con el texto codificado', () => {
    assert.equal(whatsappUrl('*Hola* Jamundí\nlínea 2'), 'https://wa.me/?text=*Hola*%20Jamund%C3%AD%0Al%C3%ADnea%202');
});

test('probabilidad legible', () => {
    assert.equal(formatProbability(0.00001), 'menos de 1 en 10.000');
    assert.equal(formatProbability(0.0063), '0,63 %');
    assert.equal(formatProbability(0.0225), '2,3 %');
});
