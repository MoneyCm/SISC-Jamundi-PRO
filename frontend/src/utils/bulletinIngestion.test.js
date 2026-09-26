import test from 'node:test';
import assert from 'node:assert/strict';
import { build } from 'esbuild';
import { fileURLToPath } from 'node:url';

// Execute the production adapter with only its HTTP transport replaced.
// All alias mapping, body forwarding and error handling remain real.
test('bulletin forwards the original upload and preserves gate responses', async () => {
    const result = await build({
        entryPoints: [fileURLToPath(new URL('../features/boletin/lib/bulletinApi.ts', import.meta.url))],
        bundle: true, write: false, format: 'esm', platform: 'node',
        plugins: [{ name: 'isolated-transport', setup(builder) {
            builder.onResolve({ filter: /utils\/apiClient$/ }, () => ({ path: 'transport', namespace: 'test' }));
            builder.onLoad({ filter: /.*/, namespace: 'test' }, () => ({ contents: 'export const apiFetch = (...args) => globalThis.__bulletinTransport(...args);' }));
            builder.onResolve({ filter: /\.\/pdfOperations$/ }, () => ({ path: 'pdf', namespace: 'unused' }));
            builder.onLoad({ filter: /.*/, namespace: 'unused' }, () => ({ contents: 'export function extractOperations() { throw new Error("Not part of ingestion"); }' }));
        } }],
    });
    const { bulletinFetch } = await import(`data:text/javascript;base64,${Buffer.from(result.outputFiles[0].text).toString('base64')}`);
    const calls = [];
    let payload = { status: 'accepted', ingestion_id: 'run-test' };
    let status = 200;
    globalThis.__bulletinTransport = async (path, options) => {
        calls.push({ path, options });
        return new Response(JSON.stringify(payload), { status });
    };
    try {
        const file = new File(['HECHOS_ID,FECHA_HECHO\nTEST-1,2026-09-01'], 'sabana.csv', { type: 'text/csv' });
        const body = new FormData();
        body.set('file', file);
        const controller = new AbortController();
        const options = { method: 'POST', body, signal: controller.signal };
        await bulletinFetch('/api/generator/ingestion/preflight', options);
        assert.equal(calls.at(-1).path, '/ingesta/policia/preflight');
        const response = await bulletinFetch('/api/generator/ingestion/upload', options);
        assert.equal(calls.at(-1).path, '/ingesta/gate/POLICIA_SEMANAL');
        assert.equal(calls.at(-1).options.body, body);
        assert.equal(calls.at(-1).options.signal, controller.signal);
        assert.equal(await calls.at(-1).options.body.get('file').text(), await file.text());
        assert.deepEqual(await response.json(), payload);
        payload = { status: 'skipped', ingestion_id: 'existing-run' };
        assert.deepEqual(await (await bulletinFetch('/api/generator/ingestion/upload', options)).json(), payload);
        await bulletinFetch('/api/generator/ingestion/existing-run', { cache: 'no-store' });
        assert.equal(calls.at(-1).path, '/ingesta/runs/existing-run');
        status = 422;
        payload = { detail: { message: 'Calidad bloqueada', semaforo: 'ROJO' } };
        const rejected = await bulletinFetch('/api/generator/ingestion/upload', options);
        assert.equal(rejected.status, 422);
        assert.equal((await rejected.json()).error, 'Calidad bloqueada');
        status = 401;
        payload = { detail: 'Sesión vencida' };
        assert.equal((await bulletinFetch('/api/generator/ingestion/upload', options)).status, 401);
    } finally {
        delete globalThis.__bulletinTransport;
    }
});

test('the bulletin leaves out Inspecciones when its data does not reach the period', async () => {
    const result = await build({
        entryPoints: [fileURLToPath(new URL('../features/boletin/lib/bulletinApi.ts', import.meta.url))],
        bundle: true, write: false, format: 'esm', platform: 'node',
        plugins: [{ name: 'isolated-transport', setup(builder) {
            builder.onResolve({ filter: /utils\/apiClient$/ }, () => ({ path: 'transport', namespace: 'test' }));
            builder.onLoad({ filter: /.*/, namespace: 'test' }, () => ({ contents: 'export const apiFetch = (...args) => globalThis.__bulletinTransport(...args);' }));
            builder.onResolve({ filter: /\.\/pdfOperations$/ }, () => ({ path: 'pdf', namespace: 'unused' }));
            builder.onLoad({ filter: /.*/, namespace: 'unused' }, () => ({ contents: 'export function extractOperations() { throw new Error("unused"); }' }));
        } }],
    });
    const { bulletinFetch, coveringBulletinSources } = await import(`data:text/javascript;base64,${Buffer.from(result.outputFiles[0].text).toString('base64')}`);
    const sources = [
        { code: 'POLICIA_SEMANAL', last_cutoff_date: '2026-09-12' },
        { code: 'INSPECCIONES_RNMC', last_cutoff_date: '2026-05-25' },
        { code: 'COMISARIAS_FAMILIA', last_cutoff_date: '2026-03-26' },
    ];
    // Semana de septiembre: Inspecciones (corte mayo) queda fuera; Comisarías sigue como contexto.
    assert.deepEqual(coveringBulletinSources(sources, '2026-09-06'), ['POLICIA_SEMANAL', 'COMISARIAS_FAMILIA']);
    assert.deepEqual(coveringBulletinSources(sources, '2026-05-01'), ['POLICIA_SEMANAL', 'INSPECCIONES_RNMC', 'COMISARIAS_FAMILIA']);
    // Medicina Legal publica por mes vencido: entra en el mensual, no en el semanal.
    assert.deepEqual(coveringBulletinSources(sources, '2026-08-01', 'monthly'), ['POLICIA_SEMANAL', 'COMISARIAS_FAMILIA', 'MEDICINA_LEGAL']);

    const calls = [];
    globalThis.__bulletinTransport = async (path, options) => {
        calls.push({ path, options });
        const body = path === '/sisc-cifras/sources' ? sources : { id: 'x', status: 'DRAFT' };
        return new Response(JSON.stringify(body), { status: 200 });
    };
    try {
        await bulletinFetch('/api/sisc-publication', { method: 'POST', body: JSON.stringify({
            edition_type: 'weekly', period_start: '2026-09-06', period_end: '2026-09-12', publish: true, warnings_acknowledged: true,
        }) });
        const sent = JSON.parse(calls.find(call => call.path === '/sisc-cifras/generate').options.body);
        assert.deepEqual(sent.source_codes, ['POLICIA_SEMANAL', 'COMISARIAS_FAMILIA']);
        assert.equal(sent.publish_automatically, true);
        assert.equal(sent.warnings_acknowledged, true);
    } finally {
        delete globalThis.__bulletinTransport;
    }
});
