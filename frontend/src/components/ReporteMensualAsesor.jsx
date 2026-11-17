import React from 'react';
import { AlertTriangle, CheckCircle2, XCircle } from 'lucide-react';
import { AZUL, AMARILLO, TINTA, BotonImagen, Cuadro, Encabezado, fmt, td, th, useDescargaImagen } from './ReporteSemanalAsesor';

// Reporte mensual para la Secretaria: metas del PISCC (con su estado) y respuesta judicial de la Fiscalía.
// Lo arma el backend (services/reporte_mensual.py). El estado va con ícono y palabra, no solo con color.

const ESTADOS = {
    EN_META: { Icono: CheckCircle2, color: '#067647', fondo: '#ECFDF3', corto: 'Dentro' },
    DESVIACION: { Icono: AlertTriangle, color: '#B54708', fondo: '#FFFAEB', corto: 'En riesgo' },
    SUPERADA: { Icono: XCircle, color: '#B42318', fondo: '#FEF3F2', corto: 'Pasó el límite' },
};

const fechaCorta = (iso) => (iso ? new Date(`${String(iso).slice(0, 10)}T00:00:00`).toLocaleDateString('es-CO', { day: 'numeric', month: 'short' }) : '');

const Estado = ({ estado, texto }) => {
    const e = ESTADOS[estado];
    if (!e) return <span className="text-slate-500">{texto || '—'}</span>;
    return (
        <span className="inline-flex items-center gap-1 whitespace-nowrap rounded-full px-2 py-0.5 text-[11px] font-black"
            style={{ color: e.color, background: e.fondo }} title={texto}>
            <e.Icono size={12} /> {e.corto}
        </span>
    );
};

export default function ReporteMensualAsesor({ reporte }) {
    const { tarjeta, descargando, descargar } = useDescargaImagen(`Reporte mensual seguridad - ${reporte.fecha_iso}.png`);
    const fiscalia = reporte.fiscalia;

    return (
        <div>
            <div ref={tarjeta} className="overflow-hidden rounded-xl border border-slate-200 bg-white" style={{ color: TINTA }}>
                <Encabezado titulo={reporte.titulo} franja={reporte.subtitulo} />

                <div className="px-4 pb-3">
                    <Cuadro titulo={`Metas del PISCC: lo que va de ${reporte.anio} frente al límite anual`}>
                        <thead>
                            <tr style={{ background: AZUL }}>
                                <th className={th}>Meta</th><th className={th}>Van</th>
                                <th className={th}>Límite</th><th className={th}>Estado</th>
                            </tr>
                        </thead>
                        <tbody>
                            {reporte.metas.map((m) => (
                                <tr key={m.nombre}>
                                    <td className={`${td} !whitespace-normal`}>
                                        {m.nombre}
                                        <span className="block text-[10px] font-normal text-slate-500">
                                            {m.anterior != null ? `${reporte.anio_anterior}: ${fmt(m.anterior)} · ` : ''}al {fechaCorta(m.corte)}
                                            {m.reciente ? ` · después: +${fmt(m.reciente.despues)} en la sábana al ${fechaCorta(m.reciente.corte)}` : ''}
                                            {m.reciente?.van != null ? ` (año: ${fmt(m.reciente.van)})` : ''}
                                        </span>
                                    </td>
                                    <td className={`${td} text-[14px] font-black`} style={{ color: AZUL }}>{fmt(m.van)}</td>
                                    <td className={`${td} text-slate-500`}>{fmt(m.limite)}</td>
                                    <td className={td}><Estado estado={m.estado} texto={m.estado_texto} /></td>
                                </tr>
                            ))}
                        </tbody>
                    </Cuadro>

                    {fiscalia?.filas?.length > 0 && (
                        <Cuadro titulo="Fiscalía: procesos que llegaron a juicio o condena">
                            <thead>
                                <tr style={{ background: TINTA }}>
                                    <th className={th}>Procesos por hechos de</th><th className={th}>Procesos</th>
                                    <th className={th}>Juicio o condena</th>
                                </tr>
                            </thead>
                            <tbody>
                                {fiscalia.filas.map((f) => (
                                    <tr key={`${f.nombre}${f.anio}`}>
                                        <td className={`${td} !whitespace-normal`}>{f.nombre} · {f.anio}</td>
                                        <td className={`${td} text-slate-500`}>{fmt(f.procesos)}</td>
                                        <td className={td}>
                                            <span className="text-[14px] font-black">{fmt(f.juicio_o_condena)}</span>
                                            <span className="ml-1 text-[11px] text-slate-500">({String(f.porcentaje).replace('.', ',')} %)</span>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </Cuadro>
                    )}
                    {fiscalia?.nota && <p className="mt-1 text-[10px] text-slate-500">{fiscalia.nota}</p>}
                </div>

                <footer className="px-4 py-2 text-white" style={{ background: TINTA, borderTop: `4px solid ${AMARILLO}` }}>
                    <p className="text-[11px] font-black">Observatorio del Delito · SISC Jamundí · {reporte.fecha}</p>
                    {(reporte.fuentes || []).map((f) => <p key={f} className="text-[10px] text-white/70">{f}.</p>)}
                    {(reporte.notas || []).map((n) => <p key={n} className="text-[10px] text-white/60">{n}</p>)}
                </footer>
            </div>
            <BotonImagen descargando={descargando} descargar={descargar} />
        </div>
    );
}
