import React, { useEffect, useMemo, useState } from 'react';
import { useInstitutionalIndicators } from '../hooks/useInstitutionalIndicators';

const readable = (value) => String(value || '')
  .replace(/proteccion/gi, 'protección')
  .replace(/actuacion/gi, 'actuación')
  .replace(/tramites/gi, 'trámites')
  .replace(/perdida/gi, 'pérdida')
  .replace(/defuncion/gi, 'defunción')
  .replace(/urbanisticas/gi, 'urbanísticas');

const formatPeriod = (period) => {
  if (!/^\d{4}-\d{2}$/.test(period || '')) return period || 'Sin periodo';
  const [year, month] = period.split('-').map(Number);
  const text = new Intl.DateTimeFormat('es-CO', { month: 'long', year: 'numeric' }).format(new Date(year, month - 1, 1));
  return text.charAt(0).toUpperCase() + text.slice(1);
};

const formatValue = (record) => {
  const value = Number(record.value);
  if (String(record.unit || '').toUpperCase() === 'COP') return '$' + value.toLocaleString('es-CO') + ' COP';
  return value.toLocaleString('es-CO') + ' ' + readable(record.unit || 'registros');
};

const PublicInspectionManagement = ({ onBack, onNavigate }) => {
  const { records, status } = useInstitutionalIndicators('INSPECCIONES');
  const [entity, setEntity] = useState('ALL');
  const [period, setPeriod] = useState('');
  const [indicator, setIndicator] = useState('ALL');

  const entities = useMemo(() => [...new Set(records.map((item) => item.reporting_entity))].sort(), [records]);
  const periods = useMemo(() => [...new Set(records.map((item) => item.period))].sort().reverse(), [records]);

  useEffect(() => {
    if (!period && periods.length) setPeriod(periods[0]);
  }, [period, periods]);

  const filteredByContext = useMemo(() => records.filter((item) => {
    const sameEntity = entity === 'ALL' || item.reporting_entity === entity;
    const samePeriod = !period || item.period === period;
    return sameEntity && samePeriod;
  }), [entity, period, records]);

  const indicators = useMemo(() => [...new Set(filteredByContext.map((item) => item.indicator))].sort(), [filteredByContext]);

  useEffect(() => {
    if (indicator !== 'ALL' && !indicators.includes(indicator)) setIndicator('ALL');
  }, [indicator, indicators]);

  const visibleRecords = indicator === 'ALL'
    ? filteredByContext
    : filteredByContext.filter((item) => item.indicator === indicator);

  const groups = useMemo(() => {
    const result = {};
    visibleRecords.forEach((item) => {
      if (!result[item.reporting_entity]) result[item.reporting_entity] = [];
      result[item.reporting_entity].push(item);
    });
    return result;
  }, [visibleRecords]);

  const cutoffs = [...new Set(filteredByContext.map((item) => item.cutoff_date).filter(Boolean))].sort();

  return (
    <main style={{ minHeight: '100vh', background: 'radial-gradient(circle at 90% 2%, #f6dfaa 0, transparent 28%), radial-gradient(circle at 0 42%, #dcecf0 0, transparent 34%), #f7f3e9', color: '#18283b' }}>
      <section style={{ maxWidth: 1180, margin: '0 auto', padding: '28px 18px 60px' }}>
        <div style={{ alignItems: 'center', display: 'flex', flexWrap: 'wrap', gap: 14, justifyContent: 'space-between', marginBottom: 22 }}>
          <button type="button" onClick={onBack} style={{ background: 'transparent', border: 0, color: '#175c68', cursor: 'pointer', fontWeight: 850, padding: 0 }}>Volver al portal ciudadano</button>
          <span style={{ background: '#fff', border: '1px solid #d7e1dd', borderRadius: 999, color: '#476173', fontSize: 13, fontWeight: 750, padding: '8px 13px' }}>
            {cutoffs.length ? 'Corte: ' + cutoffs.join(' · ') : 'Solo información revisada y aprobada'}
          </span>
        </div>

        <header style={{ background: 'linear-gradient(125deg, #173f5f 0%, #146b70 68%, #cb8a24 135%)', borderRadius: 30, boxShadow: '0 24px 55px rgba(24, 55, 72, .2)', color: '#fff', overflow: 'hidden', padding: 'clamp(28px, 6vw, 58px)', position: 'relative' }}>
          <div style={{ background: 'rgba(255,255,255,.08)', border: '1px solid rgba(255,255,255,.12)', borderRadius: '50%', height: 260, position: 'absolute', right: -90, top: -120, width: 260 }} />
          <p style={{ color: '#beece4', fontSize: 13, fontWeight: 850, letterSpacing: '.09em', margin: 0, textTransform: 'uppercase' }}>Inspecciones de Policía</p>
          <h1 style={{ fontFamily: 'Georgia, serif', fontSize: 'clamp(36px, 6vw, 62px)', lineHeight: .98, margin: '13px 0 18px', maxWidth: 760, position: 'relative' }}>Trámites y actuaciones, explicados con claridad</h1>
          <p style={{ color: '#eefcf8', fontSize: 18, lineHeight: 1.55, margin: 0, maxWidth: 790, position: 'relative' }}>Consulta cifras agregadas de la Inspección Segunda y la Inspección Tercera. Aquí se informa qué gestión fue reportada, en qué periodo y por cuál dependencia.</p>
        </header>

        <section style={{ display: 'grid', gap: 14, gridTemplateColumns: 'repeat(auto-fit, minmax(210px, 1fr))', margin: '22px 0' }}>
          {[
            ['Procesos policivos', 'Actuaciones y trámites reportados por cada inspección.'],
            ['Servicios y certificados', 'Cifras agregadas, sin nombres ni expedientes.'],
            ['Medidas correctivas', 'Consulta separada para entender la gestión de convivencia.']
          ].map(([title, text], index) => (
            <article key={title} style={{ background: index === 1 ? '#fff8e7' : '#fff', border: '1px solid #dbe3df', borderRadius: 17, padding: 19 }}>
              <span style={{ color: '#c17d17', fontSize: 12, fontWeight: 900 }}>0{index + 1}</span>
              <h2 style={{ fontFamily: 'Georgia, serif', fontSize: 20, margin: '7px 0' }}>{title}</h2>
              <p style={{ color: '#506576', fontSize: 14, lineHeight: 1.5, margin: 0 }}>{text}</p>
            </article>
          ))}
        </section>

        {records.length > 0 && (
          <section aria-label="Filtros de gestión" style={{ background: '#fff', border: '1px solid #d7e1dd', borderRadius: 20, boxShadow: '0 12px 28px rgba(28, 55, 65, .08)', display: 'grid', gap: 14, gridTemplateColumns: 'repeat(auto-fit, minmax(210px, 1fr))', padding: 20 }}>
            <label style={{ color: '#385163', display: 'grid', fontSize: 13, fontWeight: 850, gap: 7 }}>Inspección
              <select value={entity} onChange={(event) => setEntity(event.target.value)} style={{ background: '#f8faf8', border: '1px solid #cbd8d2', borderRadius: 12, color: '#18283b', fontSize: 15, padding: '12px 13px' }}>
                <option value="ALL">Todas, por separado</option>
                {entities.map((item) => <option key={item} value={item}>{readable(item)}</option>)}
              </select>
            </label>
            <label style={{ color: '#385163', display: 'grid', fontSize: 13, fontWeight: 850, gap: 7 }}>Periodo
              <select value={period} onChange={(event) => setPeriod(event.target.value)} style={{ background: '#f8faf8', border: '1px solid #cbd8d2', borderRadius: 12, color: '#18283b', fontSize: 15, padding: '12px 13px' }}>
                {periods.map((item) => <option key={item} value={item}>{formatPeriod(item)}</option>)}
              </select>
            </label>
            <label style={{ color: '#385163', display: 'grid', fontSize: 13, fontWeight: 850, gap: 7 }}>Qué quieres consultar
              <select value={indicator} onChange={(event) => setIndicator(event.target.value)} style={{ background: '#f8faf8', border: '1px solid #cbd8d2', borderRadius: 12, color: '#18283b', fontSize: 15, padding: '12px 13px' }}>
                <option value="ALL">Toda la gestión reportada</option>
                {indicators.map((item) => <option key={item} value={item}>{readable(item)}</option>)}
              </select>
            </label>
          </section>
        )}

        <aside style={{ background: '#fff8dd', border: '1px solid #ead58c', borderRadius: 17, color: '#594814', lineHeight: 1.55, margin: '20px 0', padding: '16px 19px' }}>
          <strong>Importante: </strong>estas cifras describen gestión institucional, no delitos. Los informes de cada inspección se presentan por separado y no se suman automáticamente.
        </aside>

        {status === 'loading' && <p style={{ padding: 30, textAlign: 'center' }}>Consultando informes aprobados...</p>}
        {status === 'fallback' && <p style={{ background: '#fff', borderRadius: 18, padding: 24 }}>No fue posible consultar la información en este momento.</p>}
        {status === 'ready' && records.length === 0 && (
          <section style={{ background: '#fff', border: '1px solid #d8e2de', borderRadius: 22, boxShadow: '0 10px 25px rgba(31, 57, 66, .07)', padding: 'clamp(24px, 5vw, 42px)', textAlign: 'center' }}>
            <span style={{ background: '#e7f1ee', borderRadius: 999, color: '#176269', display: 'inline-block', fontSize: 12, fontWeight: 900, padding: '7px 11px', textTransform: 'uppercase' }}>En validación</span>
            <h2 style={{ fontFamily: 'Georgia, serif', fontSize: 30, margin: '16px 0 10px' }}>Aún no hay cifras aprobadas para publicar</h2>
            <p style={{ color: '#526879', lineHeight: 1.6, margin: '0 auto', maxWidth: 680 }}>El Observatorio está revisando los informes de las inspecciones. Cuando una carga sea validada, esta página se actualizará automáticamente. No mostramos cifras provisionales ni estimadas.</p>
          </section>
        )}

        {Object.entries(groups).map(([name, items]) => (
          <section key={name} style={{ marginTop: 26 }}>
            <div style={{ alignItems: 'end', display: 'flex', flexWrap: 'wrap', gap: 10, justifyContent: 'space-between', marginBottom: 12 }}>
              <div>
                <p style={{ color: '#bb7613', fontSize: 12, fontWeight: 900, letterSpacing: '.08em', margin: '0 0 5px', textTransform: 'uppercase' }}>{formatPeriod(period)}</p>
                <h2 style={{ fontFamily: 'Georgia, serif', fontSize: 'clamp(26px, 4vw, 36px)', margin: 0 }}>{readable(name)}</h2>
              </div>
              <span style={{ color: '#526879', fontSize: 13 }}>{items[0]?.reporting_basis === 'CUMULATIVE' ? 'Informe acumulado' : 'Informe mensual'}</span>
            </div>
            <div style={{ display: 'grid', gap: 14, gridTemplateColumns: 'repeat(auto-fit, minmax(230px, 1fr))' }}>
              {items.map((item) => (
                <article key={name + '-' + item.period + '-' + item.indicator} style={{ background: '#fff', border: '1px solid #dbe3df', borderRadius: 18, boxShadow: '0 7px 18px rgba(28, 54, 61, .06)', minHeight: 126, padding: 20 }}>
                  <span style={{ color: '#506576', display: 'block', fontSize: 14, fontWeight: 800, lineHeight: 1.4 }}>{readable(item.indicator)}</span>
                  <strong style={{ color: '#146b70', display: 'block', fontFamily: 'Georgia, serif', fontSize: 30, marginTop: 13 }}>{formatValue(item)}</strong>
                </article>
              ))}
            </div>
          </section>
        ))}

        <section style={{ alignItems: 'center', background: '#173f5f', borderRadius: 22, color: '#fff', display: 'flex', flexWrap: 'wrap', gap: 18, justifyContent: 'space-between', marginTop: 28, padding: '24px clamp(20px, 4vw, 32px)' }}>
          <div style={{ maxWidth: 680 }}>
            <h2 style={{ fontFamily: 'Georgia, serif', fontSize: 24, margin: '0 0 7px' }}>Consulta medidas correctivas y convivencia</h2>
            <p style={{ color: '#dcebf1', lineHeight: 1.5, margin: 0 }}>Explora indicadores agregados sin información personal ni detalles de comparendos individuales.</p>
          </div>
          <button type="button" onClick={() => onNavigate('public-measures')} style={{ background: '#efb74e', border: 0, borderRadius: 12, color: '#233446', cursor: 'pointer', fontWeight: 900, padding: '13px 18px' }}>Ver medidas correctivas</button>
        </section>

        <p style={{ color: '#526879', fontSize: 14, lineHeight: 1.55, margin: '20px 4px 0' }}>Esta publicación no incluye nombres, documentos, direcciones, comparendos ni expedientes. Ante una emergencia, llama al <strong>123</strong>.</p>
      </section>
    </main>
  );
};

export default PublicInspectionManagement;