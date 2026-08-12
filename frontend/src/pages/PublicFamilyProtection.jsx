import React, { useEffect, useMemo, useState } from 'react';
import { useInstitutionalIndicators } from '../hooks/useInstitutionalIndicators';

const normalize = (value) => String(value || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();

const readable = (value) => String(value || '')
  .replace(/acompanamientos/gi, 'acompañamientos')
  .replace(/psicologicos/gi, 'psicológicos')
  .replace(/proteccion/gi, 'protección')
  .replace(/psicologia/gi, 'psicología')
  .replace(/verificacion\b/gi, 'verificación')
  .replace(/genero/gi, 'género')
  .replace(/institucionalizacion/gi, 'institucionalización');

const indicatorStatus = (value) => {
  const key = normalize(value);
  if (key === 'procesos administrativos de restablecimiento de derechos') {
    return { label: 'Comparable', background: '#dff3e6', color: '#216440' };
  }
  if (key.includes('violencia') || key.includes('denuncias') || key.includes('verificacion') || key.includes('adultos mayores')) {
    return { label: 'Definición diferente', background: '#fff0c7', color: '#715400' };
  }
  return { label: 'Solo informado por esta comisaría', background: '#e8eef8', color: '#36577d' };
};

const formatPeriod = (period) => {
  if (!/^\d{4}-\d{2}$/.test(period || '')) return period || 'Sin periodo';
  const [year, month] = period.split('-').map(Number);
  const label = new Intl.DateTimeFormat('es-CO', { month: 'long', year: 'numeric' }).format(new Date(year, month - 1, 1));
  return label.charAt(0).toUpperCase() + label.slice(1);
};

const formatValue = (record) => {
  const value = Number(record.value);
  if (String(record.unit || '').toUpperCase() === 'COP') return '$' + value.toLocaleString('es-CO') + ' COP';
  return value.toLocaleString('es-CO') + ' ' + readable(record.unit || 'casos');
};

const PublicFamilyProtection = ({ onBack }) => {
  const { records, status } = useInstitutionalIndicators('COMISARIAS');
  const [entity, setEntity] = useState('ALL');
  const [period, setPeriod] = useState('');
  const [indicator, setIndicator] = useState('ALL');

  const entities = useMemo(() => [...new Set(records.map((item) => item.reporting_entity))].sort(), [records]);
  const periods = useMemo(() => [...new Set(records.map((item) => item.period))].sort().reverse(), [records]);

  const defaultPeriod = useMemo(() => {
    const coverage = {};
    records.forEach((item) => {
      if (!coverage[item.period]) coverage[item.period] = new Set();
      coverage[item.period].add(item.reporting_entity);
    });
    return periods.find((item) => coverage[item]?.size > 1) || periods[0] || '';
  }, [periods, records]);

  useEffect(() => {
    if (!period && defaultPeriod) setPeriod(defaultPeriod);
  }, [defaultPeriod, period]);

  const periodRecords = useMemo(() => records.filter((item) => {
    const matchesPeriod = !period || item.period === period;
    const matchesEntity = entity === 'ALL' || item.reporting_entity === entity;
    return matchesPeriod && matchesEntity;
  }), [records, period, entity]);

  const indicators = useMemo(() => [...new Set(periodRecords.map((item) => item.indicator))].sort(), [periodRecords]);

  useEffect(() => {
    if (indicator !== 'ALL' && !indicators.includes(indicator)) setIndicator('ALL');
  }, [indicator, indicators]);

  const visibleRecords = indicator === 'ALL'
    ? periodRecords
    : periodRecords.filter((item) => normalize(item.indicator) === normalize(indicator));

  const groups = useMemo(() => {
    const result = {};
    visibleRecords.forEach((item) => {
      if (!result[item.reporting_entity]) result[item.reporting_entity] = [];
      result[item.reporting_entity].push(item);
    });
    return result;
  }, [visibleRecords]);

  const cutoffs = [...new Set(periodRecords.map((item) => item.cutoff_date).filter(Boolean))].sort();

  return (
    <main style={{ minHeight: '100vh', background: 'radial-gradient(circle at 8% 0%, #d8efe8 0, transparent 34%), #f6f2e8', color: '#17253a' }}>
      <section style={{ maxWidth: 1180, margin: '0 auto', padding: '28px 18px 60px' }}>
        <div style={{ display: 'flex', gap: 16, justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', marginBottom: 22 }}>
          <button type="button" onClick={onBack} style={{ background: 'transparent', border: 0, color: '#176269', cursor: 'pointer', fontWeight: 800, padding: 0 }}>Volver al portal ciudadano</button>
          <span style={{ background: '#fff', border: '1px solid #d9e3dd', borderRadius: 999, color: '#355267', fontSize: 13, fontWeight: 750, padding: '8px 13px' }}>
            {cutoffs.length ? 'Corte: ' + cutoffs.join(' · ') : 'Cifras institucionales aprobadas'}
          </span>
        </div>

        <header style={{ background: 'linear-gradient(125deg, #0d4f59, #17766c 62%, #d09a22 140%)', borderRadius: 28, boxShadow: '0 22px 50px rgba(20, 69, 67, .18)', color: '#fff', padding: 'clamp(26px, 5vw, 52px)' }}>
          <p style={{ color: '#c9f4e8', fontSize: 13, fontWeight: 850, letterSpacing: '.09em', margin: 0, textTransform: 'uppercase' }}>Comisarías de Familia</p>
          <h1 style={{ fontFamily: 'Georgia, serif', fontSize: 'clamp(34px, 6vw, 58px)', fontWeight: 700, lineHeight: 1, margin: '12px 0 16px', maxWidth: 820 }}>Protección familiar, en cifras claras</h1>
          <p style={{ color: '#edfdf8', fontSize: 18, lineHeight: 1.55, margin: 0, maxWidth: 820 }}>Consulta resultados agregados de cada comisaría. Puedes elegir periodo e indicador sin exponer personas, familias ni expedientes.</p>
        </header>

        <section aria-label="Filtros de consulta" style={{ background: '#fff', border: '1px solid #d9e3dd', borderRadius: 20, boxShadow: '0 12px 30px rgba(25, 52, 58, .08)', display: 'grid', gap: 14, gridTemplateColumns: 'repeat(auto-fit, minmax(210px, 1fr))', marginTop: -18, padding: 20, position: 'relative', zIndex: 1 }}>
          <label style={{ color: '#344b5b', display: 'grid', fontSize: 13, fontWeight: 800, gap: 7 }}>Comisaría
            <select value={entity} onChange={(event) => setEntity(event.target.value)} style={{ background: '#f8faf8', border: '1px solid #cbd8d2', borderRadius: 12, color: '#17253a', fontSize: 15, padding: '12px 13px' }}>
              <option value="ALL">Todas, por separado</option>
              {entities.map((item) => <option key={item} value={item}>{item}</option>)}
            </select>
          </label>
          <label style={{ color: '#344b5b', display: 'grid', fontSize: 13, fontWeight: 800, gap: 7 }}>Periodo
            <select value={period} onChange={(event) => setPeriod(event.target.value)} style={{ background: '#f8faf8', border: '1px solid #cbd8d2', borderRadius: 12, color: '#17253a', fontSize: 15, padding: '12px 13px' }}>
              {periods.map((item) => <option key={item} value={item}>{formatPeriod(item)}</option>)}
            </select>
          </label>
          <label style={{ color: '#344b5b', display: 'grid', fontSize: 13, fontWeight: 800, gap: 7 }}>Indicador
            <select value={indicator} onChange={(event) => setIndicator(event.target.value)} style={{ background: '#f8faf8', border: '1px solid #cbd8d2', borderRadius: 12, color: '#17253a', fontSize: 15, padding: '12px 13px' }}>
              <option value="ALL">Todos los indicadores</option>
              {indicators.map((item) => <option key={item} value={item}>{readable(item)}</option>)}
            </select>
          </label>
        </section>

        <aside style={{ background: '#fff8dd', border: '1px solid #ead58c', borderRadius: 16, color: '#594814', lineHeight: 1.5, margin: '20px 0', padding: '15px 18px' }}>
          <strong>Cómo leer esta información: </strong>cada tarjeta pertenece a una dependencia y a su propio corte. Las cifras acumuladas no se suman automáticamente entre comisarías.
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginTop: 12 }}>
            {[['Comparable', '#dff3e6', '#216440'], ['Definición diferente', '#fff0c7', '#715400'], ['Solo informado por una comisaría', '#e8eef8', '#36577d']].map(([label, background, color]) => (
              <span key={label} style={{ background, borderRadius: 999, color, fontSize: 12, fontWeight: 800, padding: '6px 10px' }}>{label}</span>
            ))}
          </div>
        </aside>

        {status === 'loading' && <p style={{ padding: 28, textAlign: 'center' }}>Consultando cifras aprobadas...</p>}
        {status === 'fallback' && <p style={{ background: '#fff', borderRadius: 16, padding: 24 }}>No fue posible consultar las cifras en este momento.</p>}
        {status === 'ready' && !visibleRecords.length && <p style={{ background: '#fff', borderRadius: 16, padding: 24 }}>No hay indicadores públicos aprobados para esta selección.</p>}

        {Object.entries(groups).map(([name, items]) => (
          <section key={name} style={{ marginTop: 26 }}>
            <div style={{ alignItems: 'end', display: 'flex', flexWrap: 'wrap', gap: 8, justifyContent: 'space-between', marginBottom: 12 }}>
              <div>
                <p style={{ color: '#b17913', fontSize: 12, fontWeight: 850, letterSpacing: '.08em', margin: '0 0 5px', textTransform: 'uppercase' }}>{formatPeriod(period)}</p>
                <h2 style={{ fontFamily: 'Georgia, serif', fontSize: 'clamp(24px, 4vw, 34px)', margin: 0 }}>{name}</h2>
              </div>
              <span style={{ color: '#536878', fontSize: 13 }}>{items[0]?.reporting_basis === 'CUMULATIVE' ? 'Reporte acumulado' : 'Reporte mensual'}</span>
            </div>
            <div style={{ display: 'grid', gap: 14, gridTemplateColumns: 'repeat(auto-fit, minmax(230px, 1fr))' }}>
              {items.map((item) => (
                <article key={name + '-' + item.period + '-' + item.indicator} style={{ background: '#fff', border: '1px solid #dbe5e0', borderRadius: 17, boxShadow: '0 7px 18px rgba(28, 54, 61, .055)', minHeight: 128, padding: 20 }}>
                  <span style={{ color: '#52697a', display: 'block', fontSize: 14, fontWeight: 750, lineHeight: 1.35 }}>{readable(item.indicator)}</span>
                  <span style={{ background: indicatorStatus(item.indicator).background, borderRadius: 999, color: indicatorStatus(item.indicator).color, display: 'inline-block', fontSize: 11, fontWeight: 850, marginTop: 10, padding: '5px 8px' }}>{indicatorStatus(item.indicator).label}</span>
                  <strong style={{ color: '#10665e', display: 'block', fontFamily: 'Georgia, serif', fontSize: 30, marginTop: 12 }}>{formatValue(item)}</strong>
                </article>
              ))}
            </div>
          </section>
        ))}

        <section style={{ background: '#eaf2f7', border: '1px solid #d0dee8', borderRadius: 18, display: 'grid', gap: 12, marginTop: 30, padding: 22 }}>
          <h2 style={{ color: '#174f78', fontSize: 20, margin: 0 }}>Privacidad y orientación</h2>
          <p style={{ lineHeight: 1.55, margin: 0 }}>No se publican nombres, direcciones, expedientes, medidas individuales ni datos que permitan identificar a niñas, niños, adolescentes o personas afectadas por violencias familiares.</p>
          <p style={{ lineHeight: 1.55, margin: 0 }}>Ante una emergencia, llama al <strong>123</strong>.</p>
        </section>
      </section>
    </main>
  );
};

export default PublicFamilyProtection;