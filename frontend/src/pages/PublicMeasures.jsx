import React, { useEffect, useMemo, useState } from 'react';

const API_BASE_URL = import.meta.env.VITE_API_URL || '/api';
const number = (value) => new Intl.NumberFormat('es-CO').format(Number(value || 0));
const percent = (value) => (value >= 0 ? '+' : '') + value.toFixed(1).replace('.', ',') + '%';

const PublicMeasures = ({ onBack }) => {
  const [payload, setPayload] = useState({ metadata: {}, records: [] });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const controller = new AbortController();
    fetch(API_BASE_URL + '/intelligence/public/rnmc-history', { signal: controller.signal })
      .then((response) => {
        if (!response.ok) throw new Error('No fue posible consultar los datos abiertos.');
        return response.json();
      })
      .then(setPayload)
      .catch((requestError) => {
        if (requestError.name !== 'AbortError') setError(requestError.message);
      })
      .finally(() => setLoading(false));
    return () => controller.abort();
  }, []);

  const data = useMemo(() => {
    const records = payload.records || [];
    const totals = records
      .filter((item) => item.indicador === 'Ordenes de comparendo' && item.categoria === 'Total')
      .map((item) => ({ ...item, value: Number(item.valor || 0) }));
    const annualMap = new Map();
    totals.forEach((item) => annualMap.set(item.anio, (annualMap.get(item.anio) || 0) + item.value));
    const years = [...annualMap.entries()]
      .map(([year, value]) => ({ year: Number(year), value }))
      .sort((a, b) => a.year - b.year);
    const latest = years.at(-1);
    const previous = years.at(-2);
    const variation = latest && previous && previous.value
      ? ((latest.value - previous.value) / previous.value) * 100
      : null;
    const latestYear = latest?.year;
    const categories = (indicator) => records
      .filter((item) => item.anio === String(latestYear)
        && item.indicador === indicator
        && item.categoria !== 'Otros u ocultados por privacidad')
      .map((item) => ({ label: item.categoria, value: Number(item.valor || 0) }))
      .sort((a, b) => b.value - a.value)
      .slice(0, 6);

    return {
      years,
      latest,
      variation,
      behaviors: categories('Comportamiento contrario a la convivencia'),
      measures: categories('Medida correctiva')
    };
  }, [payload]);

  const hasData = Boolean(payload.metadata?.available && data.latest);

  const download = () => {
    const headers = ['conjunto', 'fecha_corte', 'anio', 'periodo', 'indicador', 'categoria', 'zona_general', 'valor', 'fuente', 'regla_privacidad'];
    const quote = (value) => '"' + String(value ?? '').replaceAll('"', '""') + '"';
    const csv = [headers.join(','), ...(payload.records || []).map((record) => headers.map((header) => quote(record[header])).join(','))].join('\n');
    const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8;' }));
    const link = document.createElement('a');
    link.href = url;
    link.download = 'SISC_Jamundi_medidas_correctivas_agregado.csv';
    link.click();
    URL.revokeObjectURL(url);
  };

  const maxYear = Math.max(...data.years.map((item) => item.value), 1);

  return (
    <main style={{ minHeight: '100vh', background: '#f6f3ed', color: '#15233b' }}>
      <section style={{ maxWidth: 1180, margin: '0 auto', padding: '32px 20px 56px' }}>
        <div style={{ alignItems: 'center', display: 'flex', flexWrap: 'wrap', gap: 16, justifyContent: 'space-between', marginBottom: 28 }}>
          <button type="button" onClick={onBack} style={{ background: 'transparent', border: 0, color: '#184e77', cursor: 'pointer', fontWeight: 700, padding: 0 }}>Volver al portal ciudadano</button>
          <button type="button" onClick={download} disabled={!payload.records?.length} style={{ background: '#fff', border: '1px solid #163f63', borderRadius: 10, color: '#12355b', cursor: payload.records?.length ? 'pointer' : 'not-allowed', fontWeight: 800, padding: '11px 15px' }}>Descargar datos abiertos CSV</button>
        </div>

        <header style={{ background: 'linear-gradient(135deg, #12355b, #1f6f8b)', borderRadius: 24, color: '#fff', padding: '32px clamp(22px, 5vw, 52px)', boxShadow: '0 18px 40px rgba(21, 35, 59, .16)' }}>
          <p style={{ color: '#bde9e4', fontWeight: 800, letterSpacing: '.08em', margin: 0, textTransform: 'uppercase', fontSize: 13 }}>Convivencia ciudadana</p>
          <h1 style={{ fontSize: 'clamp(30px, 5vw, 48px)', lineHeight: 1.04, margin: '10px 0 14px' }}>Medidas correctivas</h1>
          <p style={{ fontSize: 18, lineHeight: 1.55, margin: 0, maxWidth: 800 }}>Consulta la evoluci&oacute;n de las &oacute;rdenes de comparendo registradas en Jamund&iacute;. La informaci&oacute;n se presenta de forma agregada para proteger a las personas.</p>
        </header>

        {loading && <p style={{ padding: '28px 0' }}>Cargando datos abiertos...</p>}
        {error && <p style={{ background: '#fff1f0', borderRadius: 12, color: '#a61b1b', padding: 18 }}>{error}</p>}

        {!loading && !error && !hasData && (
          <section style={{ background: '#fff', border: '1px solid #e1e5e9', borderRadius: 18, marginTop: 24, padding: 28, textAlign: 'center' }}>
            <h2 style={{ margin: '0 0 10px' }}>Información aún no disponible</h2>
            <p style={{ color: '#4f5f70', lineHeight: 1.55, margin: 0 }}>La serie agregada de medidas correctivas todavía no está disponible para consulta. Esto no significa que se hayan registrado cero medidas.</p>
          </section>
        )}

        {!loading && !error && hasData && (
          <>
            <section style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 16, margin: '24px 0' }}>
              <article style={{ background: '#fff', border: '1px solid #e1e5e9', borderRadius: 18, padding: 22 }}>
                <p style={{ color: '#55708a', fontWeight: 700, fontSize: 14, margin: 0 }}>Órdenes de comparendo registradas en {data.latest?.year || 'el último corte'}</p>
                <strong style={{ color: '#12355b', display: 'block', fontSize: 36, margin: '9px 0' }}>{number(data.latest?.value)}</strong>
                <p style={{ color: '#4f5f70', fontSize: 14, margin: 0 }}>Total anual consolidado de órdenes de comparendo.</p>
              </article>
              <article style={{ background: '#fff', border: '1px solid #e1e5e9', borderRadius: 18, padding: 22 }}>
                <p style={{ color: '#55708a', fontWeight: 700, fontSize: 14, margin: 0 }}>Variaci&oacute;n anual</p>
                <strong style={{ color: data.variation >= 0 ? '#b54708' : '#16794b', display: 'block', fontSize: 36, margin: '9px 0' }}>{data.variation === null ? 'Sin comparaci&oacute;n' : percent(data.variation)}</strong>
                <p style={{ color: '#4f5f70', fontSize: 14, margin: 0 }}>Frente al a&ntilde;o anterior.</p>
              </article>
              <article style={{ background: '#fff8dd', border: '1px solid #f0df9b', borderRadius: 18, padding: 22 }}>
                <p style={{ color: '#6b5607', fontWeight: 700, fontSize: 14, margin: 0 }}>Protecci&oacute;n de datos</p>
                <strong style={{ color: '#5d4800', display: 'block', fontSize: 22, margin: '10px 0' }}>Datos agregados</strong>
                <p style={{ color: '#6b5607', fontSize: 14, margin: 0 }}>No incluye nombres, comparendos, direcciones ni expedientes.</p>
              </article>
            </section>

            <section style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1.2fr) minmax(280px, .8fr)', gap: 20, alignItems: 'start' }}>
              <article style={{ background: '#fff', border: '1px solid #e1e5e9', borderRadius: 18, padding: 22 }}>
                <h2 style={{ margin: 0 }}>Evoluci&oacute;n anual</h2>
                <p style={{ color: '#4f5f70', marginTop: 6 }}>Total de &oacute;rdenes de comparendo registradas por a&ntilde;o.</p>
                <div style={{ alignItems: 'end', display: 'flex', gap: 10, height: 190, marginTop: 22 }}>
                  {data.years.map((item) => (
                    <div key={item.year} style={{ flex: 1, minWidth: 34, textAlign: 'center' }}>
                      <div title={String(item.year) + ': ' + number(item.value)} style={{ background: '#1f6f8b', borderRadius: '8px 8px 0 0', height: Math.max((item.value / maxYear) * 145, 5) + 'px' }} />
                      <strong style={{ display: 'block', fontSize: 12, marginTop: 8 }}>{item.year}</strong>
                      <span style={{ color: '#4f5f70', fontSize: 11 }}>{number(item.value)}</span>
                    </div>
                  ))}
                </div>
              </article>
              <aside style={{ background: '#fff', border: '1px solid #e1e5e9', borderRadius: 18, padding: 22 }}>
                <h2 style={{ fontSize: 21, margin: 0 }}>Lectura ciudadana</h2>
                <p style={{ color: '#4f5f70', lineHeight: 1.55 }}>Una medida correctiva busca restablecer la convivencia. No equivale a una condena penal.</p>
                <p style={{ color: '#4f5f70', lineHeight: 1.55, marginBottom: 0 }}>Fuente: RNMC. Corte disponible: {payload.metadata?.updated_at || 'sin dato'}.</p>
              </aside>
            </section>

            <section style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: 20, marginTop: 20 }}>
              {[
                ['Comportamientos mas registrados', data.behaviors],
                ['Medidas correctivas mas utilizadas', data.measures]
              ].map(([title, items]) => (
                <article key={title} style={{ background: '#fff', border: '1px solid #e1e5e9', borderRadius: 18, padding: 22 }}>
                  <h2 style={{ fontSize: 21, margin: 0 }}>{title}</h2>
                  <div style={{ marginTop: 14 }}>
                    {items.map((item) => (
                      <div key={item.label} style={{ borderBottom: '1px solid #edf0f2', display: 'flex', gap: 16, justifyContent: 'space-between', padding: '12px 0' }}>
                        <span style={{ lineHeight: 1.35 }}>{item.label}</span>
                        <strong style={{ color: '#1d6b70', whiteSpace: 'nowrap' }}>{number(item.value)}</strong>
                      </div>
                    ))}
                  </div>
                </article>
              ))}
            </section>
          </>
        )}
      </section>
    </main>
  );
};

export default PublicMeasures;