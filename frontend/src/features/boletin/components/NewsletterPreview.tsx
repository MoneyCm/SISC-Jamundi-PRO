
import React, { useState, useEffect, useRef } from 'react';
import { LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import type { OperationsData, SiscIndicator, SiscPublication, StatsResult } from '../types/stats';

interface NewsletterPreviewProps {
  stats: StatsResult | null;
  operations: OperationsData;
  siscPublication: SiscPublication | null;
  includePisccPage?: boolean;
}

const NewsletterPreview: React.FC<NewsletterPreviewProps> = ({ stats, operations, siscPublication, includePisccPage = true }) => {
  const [editableText, setEditableText] = useState(() => stats?.generatedAnalysis ?? '');
  const textareaRef = useRef<HTMLTextAreaElement>(null);


  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${textareaRef.current.scrollHeight}px`;
    }
  }, [editableText]);

  if (!stats) {
    return (
      <div className="p-8 text-center text-gray-400">
        Carga un archivo SABANAS en Excel para generar la vista previa del boletín.
      </div>
    );
  }

  const {
    baseYear,
    prevYear,
    periodName,
    currentPeriodCount,
    prevPeriodCount,
    currentYTDCount,
    prevYTDCount,
    prevImmediatePeriodCount,
    last4WeeksAvg,
    selectedConducta,
    chartData,
    periodTableData,
    ytdTableData,
    periodType,
    fechaCorteInicio,
    fechaCorteFin,
    fechaExtraccion,
    nombreArchivo,
    hashArchivo,
    versionBoletin
  } = stats;

  const formatIsoDate = (isoStr?: string, withYear = false) => {
    if (!isoStr) return '';
    const parts = isoStr.split('-');
    if (parts.length < 3) return isoStr;
    const year = parts[0];
    const monthIndex = parseInt(parts[1], 10) - 1;
    const day = parseInt(parts[2], 10);
    const months = [
      'enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
      'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre'
    ];
    return `${day} de ${months[monthIndex]}${withYear ? ` de ${year}` : ''}`;
  };

  const formatDiffWoW = (curr: number, prev: number) => {
    const diff = curr - prev;
    if (diff < 0) return `${Math.abs(diff)} ${Math.abs(diff) === 1 ? 'hecho menos' : 'hechos menos'}`;
    if (diff > 0) return `${diff} ${diff === 1 ? 'hecho más' : 'hechos más'}`;
    return `Sin variación`;
  };

  const calcDiff = (curr: number, prev: number) => {
    if (prev === 0) return curr > 0 ? '+100%' : '0%';
    const diff = ((curr - prev) / prev) * 100;
    return `${diff > 0 ? '+' : ''}${diff.toFixed(1)} %`;
  };

  const isWeekly = periodType === 'semanal';
  const colorAzul = '#0033A0';
  const colorAmarillo = '#FFC000';
  
  const varYTD = calcDiff(currentYTDCount, prevYTDCount);
  const inspectionSource = siscPublication?.sources.find(source => source.code === 'INSPECCIONES_RNMC');
  const familySource = siscPublication?.sources.find(source => source.code === 'COMISARIAS_FAMILIA');
  const inspectionIndicators = siscPublication?.indicators.filter(
    indicator => indicator.source_code === 'INSPECCIONES_RNMC' && indicator.domain !== 'TERRITORIO',
  ) || [];
  const familyIndicators = siscPublication?.indicators.filter(
    indicator => indicator.source_code === 'COMISARIAS_FAMILIA',
  ) || [];
  const inspectionTotal = inspectionIndicators.find(indicator => indicator.indicator_code === 'convivencia.actuaciones');
  const inspectionMeasures = inspectionIndicators.filter(indicator => indicator.category === 'Medida').slice(0, 3);
  const hasOperations = Object.values(operations).some(value => value > 0);
  const showInstitutionalPage = Boolean(siscPublication || hasOperations);

  const formatIndicatorValue = (indicator: SiscIndicator) => {
    if (indicator.value == null) return '|||';
    return new Intl.NumberFormat('es-CO', { maximumFractionDigits: 1 }).format(indicator.value);
  };

  const comparisonText = (indicator: SiscIndicator) => {
    if (indicator.comparison_value === null) return 'Sin base comparable';
    if (indicator.variation_percentage === null) {
      return `Antes: ${new Intl.NumberFormat('es-CO').format(indicator.comparison_value)}`;
    }
    const sign = indicator.variation_percentage > 0 ? '+' : '';
    return `${sign}${indicator.variation_percentage.toFixed(1)}% vs ${siscPublication?.comparison_label || 'periodo comparable'}`;
  };

  const sourceMessage = (source: typeof inspectionSource, fallback: string) => {
    if (!source) return fallback;
    if (source.coverage_status === 'not_applicable') return 'Esta fuente se incorpora en el boletín mensual.';
    return source.status_note || fallback;
  };

  const coverageLabel = {
    aligned: 'Completa',
    partial: 'Parcial',
    stale: 'Desactualizada',
    missing: 'Sin datos',
    not_applicable: 'No aplica',
  } as const;

  const coverageTone = {
    aligned: 'border-emerald-500 bg-emerald-50 text-emerald-900',
    partial: 'border-amber-500 bg-amber-50 text-amber-900',
    stale: 'border-red-400 bg-red-50 text-red-900',
    missing: 'border-gray-400 bg-gray-50 text-gray-700',
    not_applicable: 'border-gray-300 bg-gray-50 text-gray-500',
  } as const;

  const periodReading = inspectionTotal
    ? `Inspecciones reporta ${formatIndicatorValue(inspectionTotal)} actuaciones con corte al ${inspectionSource?.last_cutoff_date || 'corte disponible'}. ${
        familyIndicators.length > 0
          ? `Comisarías aporta ${familyIndicators.length} indicadores agregados del mismo mes.`
          : 'Comisarías se incorporará cuando exista un corte aprobado para el mes.'
      }`
    : sourceMessage(inspectionSource, 'No hay actuaciones de Inspecciones publicables para este periodo.');

  return (
    <div className="newsletter-document-container w-full bg-gray-100 p-4 md:p-8 flex flex-col items-center gap-8">
      
      {/* PÁGINA 1 */}
      <div className="newsletter-document bg-white shadow-2xl relative slide-page" style={{ padding: '40px 50px', fontFamily: '"Inter", "Outfit", sans-serif', color: '#333' }}>
        
        {/* HEADER */}
        <div className="flex justify-between items-center border-b-[6px] pb-3 mb-5" style={{ borderColor: colorAmarillo }}>
           <div className="flex items-center gap-4">
              <img src="/boletin-escudo.png" alt="Escudo Jamundi" width={64} height={80} className="object-contain" />
              <div>
                 <h1 className="font-extrabold text-xl md:text-2xl leading-tight" style={{ color: colorAzul }}>
                    BOLETÍN ESTADÍSTICO DE<br/>SEGURIDAD Y CONVIVENCIA
                 </h1>
                 <p className="text-gray-500 font-semibold tracking-wider text-xs mt-1">ALCALDÍA MUNICIPAL DE JAMUNDÍ</p>
              </div>
           </div>
           <div className="text-right">
               <h2 className="font-bold text-sm md:text-base leading-tight" style={{ color: colorAzul }}>Secretaría de Seguridad y Convivencia</h2>
               <p className="text-gray-700 font-bold text-[11px] mt-1 uppercase">Carolina Obando Gómez</p>
               <p className="text-gray-500 text-[9px] uppercase tracking-wider">Secretaria de Seguridad</p>
               <p className="text-gray-400 text-[10px] mt-2">Observatorio del Delito | Corte: {fechaCorteFin ? formatIsoDate(fechaCorteFin, true) : `${periodName} de ${baseYear}`}</p>
            </div>
        </div>

        {/* 1. INTRODUCCIÓN Y ALCANCE */}
        <div className="mb-4">
            <div className="border-l-4 pl-3 mb-2" style={{ borderColor: colorAmarillo }}>
               <h2 className="font-extrabold text-base" style={{ color: colorAzul }}>1. INTRODUCCIÓN Y ALCANCE</h2>
            </div>
            
            {/* Fechas de corte exactas */}
            <div className="bg-gray-50 border border-gray-200 p-2.5 rounded-md text-xs space-y-1 mb-3">
              <div><strong>Periodo acumulado:</strong> 1 de enero al {fechaCorteFin ? formatIsoDate(fechaCorteFin, true) : `corte de la ${periodName} de ${baseYear}`}</div>
              {fechaCorteInicio && fechaCorteFin && (
                <div><strong>Periodo del boletín:</strong> del {formatIsoDate(fechaCorteInicio, false)} al {formatIsoDate(fechaCorteFin, true)}</div>
              )}
              <div><strong>Fecha de extracción de la base:</strong> {fechaExtraccion || 'No disponible'}</div>
            </div>

            <div className="bg-blue-50 border border-blue-100 p-2.5 rounded-md shadow-sm mb-3 print:hidden">
               <p className="text-xs text-blue-900 leading-relaxed font-medium">
                  <strong>Lectura correcta:</strong> el Panorama General corresponde al acumulado del año hasta la fecha de corte. El documento también incluye una sección separada con el comportamiento del periodo seleccionado.
               </p>
            </div>
            
            <div className="transparent-on-print print:hidden">
               <textarea 
                  ref={textareaRef}
                  value={editableText}
                  onChange={(e) => setEditableText(e.target.value)}
                  className="w-full bg-gray-50 border border-gray-200 rounded p-2 text-xs resize-y no-resize-on-print"
                  style={{ minHeight: '130px', color: '#333', overflow: 'hidden' }}
               />
            </div>
            <div className="hidden print:block text-[11px] text-justify leading-relaxed whitespace-pre-wrap mt-1 p-3 bg-gray-50 border border-gray-150 rounded-md font-sans">
               {editableText}
            </div>
        </div>

        {/* 2. PANORAMA GENERAL ACUMULADO */}
        <div className="mb-4">
            <div className="border-l-4 pl-3 mb-2" style={{ borderColor: colorAmarillo }}>
               <h2 className="font-extrabold text-base uppercase" style={{ color: colorAzul }}>2. PANORAMA GENERAL ACUMULADO</h2>
            </div>
            <p className="text-xs mb-2 text-gray-600">Periodo acumulado comparado: 1 de enero al {fechaCorteFin ? formatIsoDate(fechaCorteFin, true) : `corte de la ${periodName} de ${baseYear}`}, frente al mismo periodo de {prevYear}.</p>
            
            <div className="grid grid-cols-3 gap-3 mb-2">
                <div className="border rounded-lg p-3 text-center shadow-sm" style={{ borderTopWidth: '4px', borderTopColor: colorAzul }}>
                    <p className="text-[10px] font-bold text-gray-500 mb-1 uppercase">Total {prevYear} Acum.</p>
                    <p className="text-3xl font-extrabold" style={{ color: colorAzul }}>{prevYTDCount}</p>
                </div>
                <div className="border rounded-lg p-3 text-center shadow-sm" style={{ borderTopWidth: '4px', borderTopColor: colorAzul }}>
                    <p className="text-[10px] font-bold text-gray-500 mb-1 uppercase">Total {baseYear} Acum.</p>
                    <p className="text-3xl font-extrabold" style={{ color: colorAzul }}>{currentYTDCount}</p>
                </div>
                <div className="border rounded-lg p-3 text-center shadow-sm bg-green-50" style={{ borderTopWidth: '4px', borderTopColor: currentYTDCount < prevYTDCount ? '#00A34F' : '#E53E3E' }}>
                    <p className="text-[10px] font-bold text-gray-500 mb-1 uppercase">Variación Acumulada</p>
                    <p className="text-3xl font-extrabold" style={{ color: currentYTDCount < prevYTDCount ? '#00A34F' : '#E53E3E' }}>{varYTD}</p>
                    <p className="text-[10px] font-bold mt-1" style={{ color: currentYTDCount < prevYTDCount ? '#00A34F' : '#E53E3E' }}>
                       Diferencia: {currentYTDCount - prevYTDCount} {Math.abs(currentYTDCount - prevYTDCount) === 1 ? 'hecho' : 'hechos'}
                    </p>
                </div>
            </div>
        </div>

        {/* 3. COMPORTAMIENTO PUNTUAL */}
        <div className="mb-2">
            <div className="border-l-4 pl-3 mb-2" style={{ borderColor: colorAmarillo }}>
               <h2 className="font-extrabold text-base uppercase" style={{ color: colorAzul }}>3. COMPORTAMIENTO PUNTUAL ({periodName})</h2>
            </div>
            <p className="text-xs mb-3 text-gray-600">
               Análisis exclusivo del periodo actual frente al periodo inmediatamente anterior y frente al mismo periodo de {prevYear}.
            </p>
            
            <div className="grid grid-cols-4 gap-2">
                <div className="border rounded-lg p-2 text-center shadow-sm bg-gray-50" style={{ borderTopWidth: '4px', borderTopColor: colorAzul }}>
                    <p className="text-[9px] font-bold text-gray-500 mb-1 uppercase truncate">{periodName}</p>
                    <p className="text-2xl font-extrabold text-gray-800">{currentPeriodCount}</p>
                    <p className="text-[9px] text-gray-500 mt-1">{currentPeriodCount === 1 ? 'hecho del periodo' : 'hechos del periodo'}</p>
                </div>
                <div className="border rounded-lg p-2 text-center shadow-sm bg-gray-50" style={{ borderTopWidth: '4px', borderTopColor: '#E53E3E' }}>
                    <p className="text-[9px] font-bold text-gray-500 mb-1 uppercase truncate">{isWeekly ? 'Semana Anterior' : 'Per. Anterior'}</p>
                    <p className="text-2xl font-extrabold" style={{ color: '#E53E3E' }}>{prevImmediatePeriodCount || 0}</p>
                    <p className="text-[9px] font-bold mt-1" style={{ color: currentPeriodCount - (prevImmediatePeriodCount || 0) >= 0 ? '#E53E3E' : '#00A34F' }}>
                       {formatDiffWoW(currentPeriodCount, prevImmediatePeriodCount || 0)}
                    </p>
                </div>
                <div className="border rounded-lg p-2 text-center shadow-sm bg-gray-50" style={{ borderTopWidth: '4px', borderTopColor: '#DD6B20' }}>
                    <p className="text-[9px] font-bold text-gray-500 mb-1 uppercase truncate">Mismo periodo {prevYear}</p>
                    <p className="text-2xl font-extrabold" style={{ color: '#DD6B20' }}>{prevPeriodCount}</p>
                    <p className="text-[9px] font-bold mt-1" style={{ color: currentPeriodCount - prevPeriodCount >= 0 ? '#E53E3E' : '#00A34F' }}>
                       {formatDiffWoW(currentPeriodCount, prevPeriodCount)}
                    </p>
                </div>
                <div className="border rounded-lg p-2 text-center shadow-sm bg-gray-50" style={{ borderTopWidth: '4px', borderTopColor: '#D69E2E' }}>
                    <p className="text-[9px] font-bold text-gray-500 mb-1 uppercase truncate">Promedio móvil</p>
                    <p className="text-2xl font-extrabold" style={{ color: '#D69E2E' }}>{last4WeeksAvg ? last4WeeksAvg.toFixed(1) : 0}</p>
                    <p className="text-[9px] text-gray-500 mt-1">últimos {isWeekly ? '4 periodos semanales' : '4 periodos'}</p>
                </div>
            </div>
        </div>

        {/* FOOTER PÁGINA 1 */}
        <div className="absolute bottom-[40px] left-[50px] right-[50px] border-t border-gray-200 pt-3 flex justify-between items-center text-[9px] text-gray-400">
           <p><strong>Fuente:</strong> Registros oficiales (SIEDCO - Policía Nacional - Jamundí).</p>
           <p><strong>Página 1</strong> | Observatorio del Delito - Alcaldía de Jamundí</p>
        </div>

      </div>

      {/* PÁGINA 2 */}
      <div className="newsletter-document bg-white shadow-2xl relative slide-page" style={{ padding: '40px 50px', fontFamily: '"Inter", "Outfit", sans-serif', color: '#333' }}>
        
        {/* MINI HEADER */}
        <div className="flex justify-between items-center border-b-[4px] pb-2 mb-5" style={{ borderColor: colorAmarillo }}>
           <div className="flex items-center gap-2">
              <img src="/boletin-escudo.png" alt="Escudo Jamundi" width={32} height={40} className="object-contain" />
              <div>
                 <h1 className="font-bold text-xs" style={{ color: colorAzul }}>BOLETÍN ESTADÍSTICO DE SEGURIDAD Y CONVIVENCIA</h1>
                 <p className="text-gray-500 text-[9px]">ALCALDÍA MUNICIPAL DE JAMUNDÍ</p>
              </div>
           </div>
           <div className="text-right">
              <h2 className="font-bold text-xs" style={{ color: colorAzul }}>Secretaría de Seguridad y Convivencia</h2>
              <p className="text-gray-600 font-bold text-[9px] uppercase">Carolina Obando Gómez</p>
              <p className="text-gray-400 text-[9px] mt-1">Corte: {periodName} de {baseYear}</p>
           </div>
        </div>

        {/* 4. COMPARATIVO ACUMULADO POR DELITO */}
        <div className="mb-5">
            <div className="border-l-4 pl-3 mb-2" style={{ borderColor: colorAmarillo }}>
               <h2 className="font-extrabold text-base uppercase" style={{ color: colorAzul }}>4. COMPARATIVO ACUMULADO POR {selectedConducta === 'Todos' ? 'DELITO' : 'BARRIO'}</h2>
            </div>
            
            <table className="w-full text-left text-xs border-collapse">
              <thead className="text-white" style={{ backgroundColor: colorAzul }}>
                <tr>
                  <th className="px-3 py-1.5 font-bold uppercase">{selectedConducta === 'Todos' ? 'Delito' : 'Barrio'}</th>
                  <th className="px-2 py-1.5 font-bold uppercase text-center">{prevYear} acum.</th>
                  <th className="px-2 py-1.5 font-bold uppercase text-center">{baseYear} acum.</th>
                  <th className="px-2 py-1.5 font-bold uppercase text-center">Variación</th>
                  <th className="px-2 py-1.5 font-bold uppercase text-center">Variación %</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200 border border-gray-200">
                {ytdTableData?.map((row, idx: number) => {
                  const isPositive = row.diffAbs > 0;
                  return (
                    <tr key={idx} className={idx % 2 === 0 ? 'bg-white' : 'bg-gray-50'}>
                      <td className="px-3 py-1 font-medium text-gray-800">{row.name}</td>
                      <td className="px-2 py-1 text-center text-gray-600">{row.prev}</td>
                      <td className="px-2 py-1 text-center text-gray-800 font-bold">{row.current}</td>
                      <td className="px-2 py-1 text-center font-bold" style={{ color: isPositive ? '#E53E3E' : '#00A34F' }}>
                        {isPositive ? '+' : ''}{row.diffAbs}
                      </td>
                      <td className="px-2 py-1 text-center font-bold" style={{ color: row.varPct.startsWith('+') ? '#E53E3E' : '#00A34F' }}>
                        {row.varPct}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
        </div>

        {/* 5. COMPARATIVO PUNTUAL DEL PERIODO */}
        <div className="mb-5">
            <div className="border-l-4 pl-3 mb-2" style={{ borderColor: colorAmarillo }}>
               <h2 className="font-extrabold text-base uppercase" style={{ color: colorAzul }}>5. COMPARATIVO PUNTUAL ({periodName.toUpperCase()})</h2>
            </div>
            
            <table className="w-full text-left text-xs border-collapse mb-2">
              <thead className="text-white" style={{ backgroundColor: colorAzul }}>
                <tr>
                  <th className="px-3 py-1.5 font-bold uppercase">{selectedConducta === 'Todos' ? 'Delito' : 'Barrio'}</th>
                  <th className="px-2 py-1.5 font-bold uppercase text-center">Mismo Per. {prevYear}</th>
                  <th className="px-2 py-1.5 font-bold uppercase text-center">Per. Actual</th>
                  <th className="px-2 py-1.5 font-bold uppercase text-center">Per. Anterior</th>
                  <th className="px-2 py-1.5 font-bold uppercase text-center">Var. YoY</th>
                  <th className="px-2 py-1.5 font-bold uppercase text-center">{isWeekly ? 'Var. WoW' : 'Var. PoP'}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200 border border-gray-200">
                {periodTableData?.map((row, idx: number) => {
                  return (
                    <tr key={idx} className={idx % 2 === 0 ? 'bg-white' : 'bg-gray-50'}>
                      <td className="px-3 py-1 font-medium text-gray-800">{row.name}</td>
                      <td className="px-2 py-1 text-center text-gray-600">{row.prev}</td>
                      <td className="px-2 py-1 text-center text-gray-800 font-bold">{row.current}</td>
                      <td className="px-2 py-1 text-center text-gray-600">{row.prevImmediate || 0}</td>
                      <td className="px-2 py-1 text-center font-bold" style={{ color: row.diffYoY > 0 ? '#E53E3E' : '#00A34F' }}>
                        {row.diffYoY > 0 ? '+' : ''}{row.diffYoY}
                      </td>
                      <td className="px-2 py-1 text-center font-bold" style={{ color: (row.diffWoW || 0) > 0 ? '#E53E3E' : '#00A34F' }}>
                        {(row.diffWoW || 0) > 0 ? '+' : ''}{row.diffWoW || 0}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
            
            <div className="bg-blue-50 border border-blue-100 p-2 rounded-md shadow-sm">
               <p className="text-[10px] text-blue-900 leading-tight">
                  <strong>Dif. YoY:</strong> Periodo actual vs Mismo periodo año anterior. <strong>Dif. PoP:</strong> Periodo actual vs Periodo inmediatamente anterior.
               </p>
            </div>
        </div>

        {/* 6. COMPORTAMIENTO TEMPORAL (GRAFICA) */}
        <div>
            <div className="border-l-4 pl-3 mb-2" style={{ borderColor: colorAmarillo }}>
               <h2 className="font-extrabold text-base uppercase" style={{ color: colorAzul }}>6. EVOLUCIÓN TEMPORAL DEL DELITO</h2>
            </div>
            <div className="h-[200px] min-w-0 w-full border border-gray-200 rounded-lg p-2 bg-white shadow-sm overflow-hidden">
               <ResponsiveContainer width="100%" height="100%" minWidth={0} initialDimension={{ width: 760, height: 184 }}>
                 {chartData.length <= 1 ? (
                   <BarChart data={chartData} margin={{ top: 5, right: 10, left: -20, bottom: 0 }} barSize={30}>
                     <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#E2E8F0" />
                     <XAxis dataKey="name" axisLine={false} tickLine={false} tick={{ fontSize: 10, fill: '#A0AEC0' }} dy={10} />
                     <YAxis axisLine={false} tickLine={false} tick={{ fontSize: 10, fill: '#A0AEC0' }} />
                     <Tooltip contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)' }} />
                     <Legend iconType="circle" wrapperStyle={{ fontSize: '10px', paddingTop: '5px' }} />
                     <Bar dataKey="current" name={`Total ${baseYear}`} fill={colorAzul} radius={[4, 4, 0, 0]} />
                     <Bar dataKey="prev" name={`Total ${prevYear}`} fill="#A0AEC0" radius={[4, 4, 0, 0]} />
                   </BarChart>
                 ) : (
                   <LineChart data={chartData} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
                     <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#E2E8F0" />
                     <XAxis dataKey="name" axisLine={false} tickLine={false} tick={{ fontSize: 10, fill: '#A0AEC0' }} dy={10} />
                     <YAxis axisLine={false} tickLine={false} tick={{ fontSize: 10, fill: '#A0AEC0' }} />
                     <Tooltip contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)' }} />
                     <Legend iconType="circle" wrapperStyle={{ fontSize: '10px', paddingTop: '5px' }} />
                     <Line type="monotone" dataKey="current" name={`Curva ${baseYear}`} stroke={colorAzul} strokeWidth={3} dot={{ r: 3, fill: colorAzul, strokeWidth: 2, stroke: '#fff' }} activeDot={{ r: 6 }} />
                     <Line type="monotone" dataKey="prev" name={`Curva ${prevYear}`} stroke="#A0AEC0" strokeWidth={2} dot={{ r: 2, fill: '#A0AEC0' }} />
                   </LineChart>
                 )}
               </ResponsiveContainer>
            </div>
        </div>
        
        {/* FOOTER PÁGINA 2 CON CONTROL DE DOCUMENTOS */}
        <div className="absolute bottom-[40px] left-[50px] right-[50px] border-t border-gray-200 pt-3 text-[8px] text-gray-400 space-y-1">
           <div className="flex justify-between items-center text-[9px]">
              <p><strong>Fuente:</strong> Registros oficiales (SIEDCO - Policía Nacional - Jamundí).</p>
              <p><strong>Página 2</strong> | Observatorio del Delito - Alcaldía de Jamundí</p>
           </div>
           <div className="grid grid-cols-2 gap-4 border-t border-gray-100 pt-1.5 text-[8px] text-gray-400 font-mono mt-1">
              <div>
                 <strong>Archivo origen:</strong> {nombreArchivo || 'SABANAS MANUALES.xlsx'}<br/>
                 <strong>Hash de contenido:</strong> {hashArchivo || 'hash_manual'}
              </div>
              <div className="text-right">
                 <strong>Fecha de extracción:</strong> {fechaExtraccion || 'No disponible'}<br/>
                 <strong>Versión del boletín:</strong> {versionBoletin || 'v1.0 (Borrador)'}
              </div>
           </div>
        </div>

      </div>

      {showInstitutionalPage && (
        <div className="newsletter-document bg-white shadow-2xl relative slide-page" style={{ padding: '40px 50px', fontFamily: '"Inter", "Outfit", sans-serif', color: '#333' }}>
          <div className="flex justify-between items-center border-b-[4px] pb-2 mb-5" style={{ borderColor: colorAmarillo }}>
            <div className="flex items-center gap-3">
              <img src="/boletin-escudo.png" alt="Escudo Jamundi" width={40} height={50} className="object-contain" />
              <div>
                <h1 className="font-bold text-sm" style={{ color: colorAzul }}>BOLETÍN ESTADÍSTICO DE SEGURIDAD Y CONVIVENCIA</h1>
                <p className="text-gray-500 text-[9px]">ALCALDÍA MUNICIPAL DE JAMUNDÍ</p>
              </div>
            </div>
            <div className="text-right text-[9px] text-gray-500">
              <p className="font-bold" style={{ color: colorAzul }}>GESTIÓN INSTITUCIONAL</p>
              <p>{fechaCorteInicio && fechaCorteFin ? `${formatIsoDate(fechaCorteInicio)} al ${formatIsoDate(fechaCorteFin, true)}` : periodName}</p>
            </div>
          </div>

          <div className="mb-4">
            <div className="border-l-4 pl-3 mb-2" style={{ borderColor: colorAmarillo }}>
              <h2 className="font-extrabold text-base uppercase" style={{ color: colorAzul }}>7. GESTIÓN Y CONVIVENCIA</h2>
            </div>
            <p className="text-xs text-gray-600">Actuaciones de Inspecciones y atención de Comisarías, cada una con su propio corte y unidad de medida.</p>
          </div>

          {siscPublication && (
            <div className={`mb-4 border-l-4 px-3 py-2 text-[10px] ${siscPublication.governance.publication_ready ? 'border-emerald-500 bg-emerald-50 text-emerald-900' : 'border-amber-500 bg-amber-50 text-amber-900'}`}>
              <strong>{siscPublication.governance.publication_ready ? 'Fuentes alineadas.' : 'Revisión de cobertura pendiente.'}</strong>{' '}
              {siscPublication.governance.publication_ready
                ? 'El periodo está listo para generar el boletín público.'
                : siscPublication.governance.review_blockers?.[0] || 'Consulte las notas de cada fuente para interpretar correctamente el periodo.'}
            </div>
          )}

          <section className="mb-4">
            <div className="flex justify-between items-end border-b-2 border-gray-200 pb-1.5 mb-2">
              <div>
                <h3 className="font-extrabold text-sm" style={{ color: colorAzul }}>INSPECCIONES DE POLICÍA</h3>
                <p className="text-[9px] text-gray-500">Actuaciones y medidas registradas en el periodo.</p>
              </div>
              <p className="text-[9px] font-semibold text-gray-500">Corte: {inspectionSource?.last_cutoff_date || 'no disponible'}</p>
            </div>

            {inspectionTotal ? (
              <div className="grid grid-cols-[190px_1fr] gap-3">
                <div className="border border-blue-100 bg-blue-50 p-3">
                  <p className="text-[10px] font-bold uppercase text-blue-800">Actuaciones registradas</p>
                  <p className="text-4xl font-extrabold mt-1" style={{ color: colorAzul }}>{formatIndicatorValue(inspectionTotal)}</p>
                  <p className="text-[9px] text-gray-600 mt-1">{comparisonText(inspectionTotal)}</p>
                </div>
                <div className="divide-y divide-gray-200 border-y border-gray-200">
                  {inspectionMeasures.length > 0 ? inspectionMeasures.map(indicator => (
                    <div key={indicator.id} className="grid grid-cols-[1fr_55px] gap-2 py-2 items-center">
                      <div>
                        <p className="text-[10px] font-bold leading-tight text-gray-800">{indicator.indicator_name}</p>
                        {typeof indicator.metadata.public_detail === 'string' && (
                          <p className="text-[8px] leading-tight text-gray-500 mt-0.5">{indicator.metadata.public_detail}</p>
                        )}
                      </div>
                      <p className="text-lg font-extrabold text-right" style={{ color: colorAzul }}>{formatIndicatorValue(indicator)}</p>
                    </div>
                  )) : (
                    <p className="py-3 text-[10px] text-gray-500">No hay medidas clasificadas para destacar en este periodo.</p>
                  )}
                </div>
              </div>
            ) : (
              <div className="border border-dashed border-gray-300 bg-gray-50 p-3 text-[10px] text-gray-600">
                {sourceMessage(inspectionSource, 'No hay actuaciones publicables para este periodo.')}
              </div>
            )}
          </section>

          <section className="mb-4">
            <div className="flex justify-between items-end border-b-2 border-gray-200 pb-1.5 mb-2">
              <div>
                <h3 className="font-extrabold text-sm text-teal-800">COMISARÍAS DE FAMILIA</h3>
                <p className="text-[9px] text-gray-500">Atención y medidas de protección agregadas, sin datos personales.</p>
              </div>
              <p className="text-[9px] font-semibold text-gray-500">Corte: {familySource?.last_cutoff_date || 'no disponible'}</p>
            </div>

            {familyIndicators.length > 0 ? (
              <div className="grid grid-cols-2 gap-x-4 gap-y-2">
                {familyIndicators.slice(0, 4).map(indicator => {
                  const entity = typeof indicator.metadata.reporting_entity === 'string' ? indicator.metadata.reporting_entity : 'Comisarías de Familia';
                  const basis = indicator.metadata.reporting_basis === 'CUMULATIVE' ? 'Acumulado al corte' : 'Durante el mes';
                  const isContext = indicator.metadata?.coverage_type === 'CONTEXT' || indicator.coverage_type === 'CONTEXT';
                  return (
                    <div key={indicator.id} className={`border-l-4 px-3 py-2 ${isContext ? 'border-amber-500 bg-amber-50' : 'border-teal-600 bg-teal-50'}`}>
                      <div className="flex justify-between gap-2 items-start">
                        <p className="text-[10px] font-bold leading-tight text-gray-800">
                          {indicator.indicator_name}
                          {isContext && <span className="ml-1 text-[8px] text-amber-600 font-normal">(contexto)</span>}
                        </p>
                        <p className={`text-xl font-extrabold ${isContext ? 'text-amber-800' : 'text-teal-800'}`}>{formatIndicatorValue(indicator)}</p>
                      </div>
                      <p className="text-[8px] text-gray-500 mt-1">{indicator.unit} | {basis}</p>
                      <p className="text-[8px] text-gray-500 truncate">{entity}</p>
                    </div>
                  );
                })}
              </div>
            ) : (
              <div className="border border-dashed border-gray-300 bg-gray-50 p-3 text-[10px] text-gray-600">
                {sourceMessage(familySource, 'No hay un corte mensual aprobado para el periodo seleccionado.')}
              </div>
            )}
          </section>

          {hasOperations && (
            <section className="mb-3">
              <h3 className="font-extrabold text-xs text-gray-800 mb-2">RESULTADOS OPERATIVOS REPORTADOS</h3>
              <div className="grid grid-cols-4 divide-x divide-gray-200 border-y border-gray-200 py-2 text-center">
                {[
                  ['Capturas', operations.capturas],
                  ['Armas incautadas', operations.armasIncautadas],
                  ['Estupefacientes', operations.estupefacientes],
                  ['Motos recuperadas', operations.motosRecuperadas],
                ].map(([label, value]) => (
                  <div key={String(label)} className="px-2">
                    <p className="text-lg font-extrabold" style={{ color: colorAzul }}>{value}</p>
                    <p className="text-[8px] text-gray-500">{label}</p>
                  </div>
                ))}
              </div>
            </section>
          )}

          {siscPublication && (
            <section className="mb-3">
              <h3 className="font-extrabold text-xs text-gray-800 mb-2">COBERTURA DEL BOLETÍN</h3>
              <div className="grid grid-cols-3 gap-2">
                {siscPublication.sources.map(source => (
                  <div key={source.code} className={`border-l-4 px-2.5 py-2 ${coverageTone[source.coverage_status]}`}>
                    <p className="text-[9px] font-extrabold leading-tight">{source.name}</p>
                    <p className="text-[8px] font-bold mt-1">{coverageLabel[source.coverage_status]}</p>
                    <p className="text-[8px] opacity-80 mt-0.5">Corte: {source.last_cutoff_date || 'no disponible'}</p>
                  </div>
                ))}
              </div>
            </section>
          )}

          {siscPublication && (
            <section
              className={`border-l-4 px-4 py-3 text-white flex flex-col justify-center ${familyIndicators.length === 0 ? 'min-h-[170px]' : 'min-h-[90px]'}`}
              style={{ backgroundColor: colorAzul, borderColor: colorAmarillo }}
            >
              <h3 className="text-[10px] font-extrabold uppercase" style={{ color: colorAmarillo }}>Lectura del periodo</h3>
              <p className="mt-1 text-sm font-semibold leading-snug">{periodReading}</p>
            </section>
          )}

          <div className="mt-auto border border-gray-200 bg-gray-50 px-3 py-2 text-[9px] text-gray-600">
            <strong>Lectura correcta:</strong> los valores de Seguridad, Inspecciones y Comisarías describen gestiones distintas y no deben sumarse entre sí. Las cifras son agregadas y anonimizadas; cada fuente conserva su fecha de corte y advertencias de cobertura.
          </div>

          <div className="absolute bottom-[40px] left-[50px] right-[50px] border-t border-gray-200 pt-3 flex justify-between items-center text-[9px] text-gray-400">
            <p><strong>Fuente:</strong> SISC | Policía Nacional | Inspecciones de Policía | Comisarías de Familia.</p>
            <p><strong>Página 3</strong> | Observatorio del Delito - Alcaldía de Jamundí</p>
          </div>
        </div>
      )}

      {/* PÁGINA PISCC (TABLA 16) - SEGUIMIENTO CONSEJO DE SEGURIDAD */}
      {includePisccPage && stats.pisccTracking && (
        <div className="newsletter-document bg-white shadow-2xl relative slide-page" style={{ padding: '40px 50px', fontFamily: '"Inter", "Outfit", sans-serif', color: '#333' }}>
          {/* HEADER INSTITUCIONAL */}
          <div className="flex justify-between items-center border-b-[4px] pb-2 mb-4" style={{ borderColor: colorAmarillo }}>
            <div className="flex items-center gap-3">
              <img src="/boletin-escudo.png" alt="Escudo Jamundi" width={40} height={50} className="object-contain" />
              <div>
                <h1 className="font-bold text-sm" style={{ color: colorAzul }}>BOLETÍN ESTADÍSTICO DE SEGURIDAD Y CONVIVENCIA</h1>
                <p className="text-gray-500 text-[9px]">ALCALDÍA MUNICIPAL DE JAMUNDÍ — SECRETARÍA DE SEGURIDAD</p>
              </div>
            </div>
            <div className="text-right text-[9px] text-gray-500">
              <p className="font-extrabold uppercase text-xs" style={{ color: colorAzul }}>PLAN INTEGRAL DE SEGURIDAD Y CONVIVENCIA (PISCC)</p>
              <p className="font-semibold text-gray-700">Seguimiento a Metas de Resultado 2024–2027 (Tabla 16)</p>
              <p className="text-gray-400">Corte: {fechaCorteFin ? formatIsoDate(fechaCorteFin, true) : `${periodName} de ${baseYear}`}</p>
            </div>
          </div>

          {/* TÍTULO DE SECCIÓN */}
          <div className="mb-3">
            <div className="border-l-4 pl-3 mb-1" style={{ borderColor: colorAmarillo }}>
              <h2 className="font-extrabold text-base uppercase" style={{ color: colorAzul }}>
                {showInstitutionalPage ? '8.' : '7.'} SEGUIMIENTO A METAS DE RESULTADO — PISCC 2024–2027 (TABLA 16)
              </h2>
            </div>
            <p className="text-[11px] text-gray-600 leading-tight">
              Monitoreo estratégico y proyección de cierre anual para los indicadores clave de impacto fijados en el Plan Integral de Seguridad y Convivencia Ciudadana de Jamundí frente a la Línea Base 2023 y la Meta al cuatrienio 2027.
            </p>
          </div>

          {/* DIAGNÓSTICO ESTRATÉGICO PARA CONSEJO DE SEGURIDAD */}
          <div
            className="border-l-4 px-4 py-2.5 text-white mb-3.5 rounded-r-md shadow-sm"
            style={{ backgroundColor: colorAzul, borderColor: colorAmarillo }}
          >
            <div className="flex items-center justify-between mb-1">
              <span className="text-[10px] font-extrabold uppercase tracking-wider" style={{ color: colorAmarillo }}>
                DIAGNÓSTICO ESTRATÉGICO PARA CONSEJO DE SEGURIDAD
              </span>
              <span className="text-[9px] bg-white/20 px-2 py-0.5 rounded font-mono">
                Avance: {stats.pisccTracking.cutoffDescription} ({stats.pisccTracking.semanasTranscurridas}/52 sem)
              </span>
            </div>
            <p className="text-[10.5px] font-medium leading-relaxed">
              {stats.pisccTracking.resumenEjecutivo}
            </p>
          </div>

          {/* TABLA 16 OFICIAL */}
          <div className="mb-3.5 overflow-hidden border border-gray-200 rounded-md shadow-sm">
            <table className="w-full text-left text-[9.5px] border-collapse">
              <thead className="text-white" style={{ backgroundColor: colorAzul }}>
                <tr>
                  <th className="px-2.5 py-1.5 font-bold uppercase">Indicador de Resultado (PISCC)</th>
                  <th className="px-1.5 py-1.5 font-bold uppercase text-center">Unidad</th>
                  <th className="px-1.5 py-1.5 font-bold uppercase text-center bg-blue-900/40">Línea Base 2023</th>
                  <th className="px-1.5 py-1.5 font-bold uppercase text-center bg-blue-900/60">Meta 2027</th>
                  <th className="px-1.5 py-1.5 font-bold uppercase text-center">Acum. {prevYear}</th>
                  <th className="px-1.5 py-1.5 font-bold uppercase text-center font-extrabold bg-blue-950/50">Acum. {baseYear}</th>
                  <th className="px-1.5 py-1.5 font-bold uppercase text-center">Var. %</th>
                  <th className="px-2 py-1.5 font-bold uppercase text-center bg-yellow-400 text-blue-950 font-black">Proy. {baseYear}</th>
                  <th className="px-2.5 py-1.5 font-bold uppercase text-center">Estado / Trayectoria</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {stats.pisccTracking.indicadores.map((ind, idx) => {
                  const isAvailable = ind.disponibleEnSabana;
                  const hasData = ind.countBase !== null && ind.countPrev !== null;
                  const rowBg = idx % 2 === 0 ? 'bg-white' : 'bg-gray-50/70';

                  let statusBadge = (
                    <span className="inline-flex items-center px-2 py-0.5 rounded text-[8.5px] font-bold bg-gray-100 text-gray-600 border border-gray-200">
                      Fuente externa
                    </span>
                  );
                  if (ind.status === 'favorable') {
                    statusBadge = (
                      <span className="inline-flex items-center px-2 py-0.5 rounded text-[8.5px] font-bold bg-emerald-50 text-emerald-800 border border-emerald-300">
                        🟢 En Meta / Favorable
                      </span>
                    );
                  } else if (ind.status === 'alerta') {
                    statusBadge = (
                      <span className="inline-flex items-center px-2 py-0.5 rounded text-[8.5px] font-bold bg-amber-50 text-amber-800 border border-amber-300">
                        🟡 Alerta de Trayectoria
                      </span>
                    );
                  } else if (ind.status === 'critico') {
                    statusBadge = (
                      <span className="inline-flex items-center px-2 py-0.5 rounded text-[8.5px] font-bold bg-rose-50 text-rose-800 border border-rose-300">
                        🔴 Desviación Crítica
                      </span>
                    );
                  }

                  return (
                    <tr key={ind.id} className={`${rowBg} hover:bg-blue-50/40 transition-colors`}>
                      <td className="px-2.5 py-1.5 font-semibold text-gray-800">
                        {ind.indicador}
                        {!isAvailable && (
                          <span className="block text-[8px] font-normal text-gray-500">
                            Fuente: {ind.fuenteExterna ?? ind.fuenteDescripcion}{ind.fechaCorteExterno ? ` · Corte: ${ind.fechaCorteExterno}` : ''}
                          </span>
                        )}
                      </td>
                      <td className="px-1.5 py-1.5 text-center text-gray-600">{ind.unidad}</td>
                      <td className="px-1.5 py-1.5 text-center font-semibold text-gray-700 bg-gray-50/50">
                        {ind.lineaBase2023.toLocaleString('es-CO')}
                      </td>
                      <td className="px-1.5 py-1.5 text-center font-bold text-blue-900 bg-blue-50/40">
                        {ind.meta2027.toLocaleString('es-CO')}
                      </td>
                      <td className="px-1.5 py-1.5 text-center text-gray-600">
                        {hasData ? ind.countPrev!.toLocaleString('es-CO') : '—'}
                      </td>
                      <td className="px-1.5 py-1.5 text-center font-black text-gray-900 bg-gray-100/50">
                        {hasData ? ind.countBase!.toLocaleString('es-CO') : '—'}
                      </td>
                      <td className="px-1.5 py-1.5 text-center font-bold" style={{ color: (ind.variacionPct || 0) > 0 ? '#E53E3E' : (ind.variacionPct || 0) < 0 ? '#00A34F' : '#4B5563' }}>
                        {hasData ? ind.variacionStr : '—'}
                      </td>
                      <td className="px-2 py-1.5 text-center font-black text-[11px] text-blue-950 bg-yellow-50/70">
                        {hasData && ind.proyeccionAnual !== null ? `≈ ${ind.proyeccionAnual.toLocaleString('es-CO')}` : '—'}
                      </td>
                      <td className="px-2.5 py-1.5 text-center">
                        {statusBadge}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {/* CRITERIO Y RECOMENDACIÓN ESTRATÉGICA */}
          <div className="grid grid-cols-2 gap-3 mb-3.5">
            <div className="bg-gray-50 border border-gray-200 p-2.5 rounded-md">
              <h3 className="text-[9.5px] font-extrabold uppercase text-gray-800 mb-1 flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-blue-600 inline-block"></span>
                Criterio Metodológico de Proyección
              </h3>
              <p className="text-[9px] text-gray-600 leading-relaxed">
                La proyección anual se estima extrapolando la tasa semanal acumulada a las 52 semanas del año (<code className="text-gray-800 font-semibold">[Casos / Semanas transcurridas] × 52</code>). Permite anticipar desvíos tempranos frente a las metas cuatrienales fijadas por la administración municipal.
              </p>
            </div>

            <div className="bg-gray-50 border border-gray-200 p-2.5 rounded-md">
              <h3 className="text-[9.5px] font-extrabold uppercase text-gray-800 mb-1 flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-amber-500 inline-block"></span>
                Recomendación para el Consejo de Seguridad
              </h3>
              <p className="text-[9px] text-gray-600 leading-relaxed">
                Focalizar los planes de patrullaje focalizado y desarme en el <strong>Hurto a Motocicletas</strong> (desviación crítica sobre la meta cuatrienal) y sostener el control territorial de contención sobre el <strong>Homicidio</strong> para consolidar la trayectoria hacia la meta de 105 casos.
              </p>
            </div>
          </div>

          {/* CONTROL Y TRAZABILIDAD */}
          <div className="mt-auto border border-gray-200 bg-gray-50 px-3 py-2 text-[9px] text-gray-600 flex justify-between items-center">
            <div>
              <strong>Control Documental:</strong> Elaboró: César Alfonso Forero Molano (Obs. Delito) | Aprobó: Carolina Obando Gómez (Secretaria de Seguridad)
            </div>
            <div className="font-mono text-[8px] text-gray-500">
              PISCC Jamundí 2024–2027 · Plan de Desarrollo Municipal
            </div>
          </div>

          {/* FOOTER */}
          <div className="absolute bottom-[40px] left-[50px] right-[50px] border-t border-gray-200 pt-3 flex justify-between items-center text-[9px] text-gray-400">
            <p><strong>Fuente:</strong> SIEDCO Policía Nacional | Plan Integral de Seguridad y Convivencia Ciudadana (PISCC).</p>
            <p><strong>Página {showInstitutionalPage ? 4 : 3}</strong> | Observatorio del Delito - Alcaldía de Jamundí</p>
          </div>
        </div>
      )}
    </div>
  );
};

export default NewsletterPreview;
