import test from 'node:test';
import assert from 'node:assert/strict';
import { asesorKey, readAsesor, clearAsesor } from './asesorSession.js';

const storage = () => {
  const values = new Map();
  return { get length() { return values.size; }, key: (i) => [...values.keys()][i],
    getItem: (key) => values.get(key), setItem: (key, value) => values.set(key, value), removeItem: (key) => values.delete(key) };
};

test('conversations are isolated and legacy ownerless data is removed', () => {
  const store = storage();
  store.setItem(asesorKey({ id: 'a' }), JSON.stringify([{ rol: 'usuario', texto: 'Pregunta privada' }]));
  store.setItem('sisc_asesor_conversacion', 'old');
  assert.equal(readAsesor(store, { id: 'b' }).length, 0);
  assert.equal(readAsesor(store, { id: 'a' }).length, 1);
  assert.equal(store.getItem('sisc_asesor_conversacion'), undefined);
  assert.deepEqual(readAsesor(store, null), []);
});

test('logout removes chat history but preserves other storage', () => {
  const store = storage();
  store.setItem(asesorKey({ id: 'a' }), '[]'); store.setItem('unrelated', 'keep');
  clearAsesor(store);
  assert.equal(store.length, 1); assert.equal(store.getItem('unrelated'), 'keep');
});

test('malformed stored histories cannot break the chat', () => {
  const store = storage(); const user = { id: 'a' };
  for (const value of ['null', '{}', 'invalid', '[{"rol":"asesor","texto":"x","fuentes":{}}]']) {
    store.setItem(asesorKey(user), value); assert.deepEqual(readAsesor(store, user), []);
  }
});
