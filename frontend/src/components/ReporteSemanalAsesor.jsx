import React, { useRef, useState } from 'react';
import { ArrowDownRight, ArrowUpRight, Download, Loader2, Minus } from 'lucide-react';

// Reporte semanal para la Secretaria (homicidios y hurto de vehículos), en cuadros con la identidad de
// la Alcaldía. Lo arma el backend (services/reporte_semanal.py); aquí solo se dibuja y se descarga como imagen.

const AZUL = '#281FD0';
const AMARILLO = '#FFE000';
const TINTA = '#14162B';
const fmt = (n) => (n == null ? '—' : Number(n).toLocaleString('es-CO'));

const Cambio = ({ diferencia, porcentaje }) => {
    if (!diferencia) {
        return <span className="inline-flex items-center gap-0.5 font-bold text-slate-500"><Minus size={12} /> igual</span>;
    }
    const sube = diferencia > 0;
    const Icono = sube ? ArrowUpRight : ArrowDownRight;
    return (
        <span className={`inline-flex items-center gap-0.5 font-bold ${sube ? 'text-[#B42318]' : 'text-[#067647]'}`}>
            <Icono size={13} />
            {sube ? '+' : ''}{diferencia}{porcentaje != null ? ` (${sube ? '+' : ''}${String(porcentaje).replace('.', ',')} %)` : ''}
        </span>
    );
};

const Cuadro = ({ titulo, children }) => (
    <section className="mt-3">
        <h4 className="mb-1 text-[11px] font-black uppercase tracking-wider" style={{ color: AZUL }}>{titulo}</h4>
        <table className="w-full border-collapse overflow-hidden rounded-md text-[12px]">{children}</table>
    </section>
);

const th = 'px-2 py-1.5 text-right font-black text-white first:text-left';
const td = 'border-b border-slate-100 px-2 py-1.5 text-right tabular-nums first:text-left first:font-bold first:whitespace-nowrap';

const TablaMeses = ({ meses, anio, anterior }) => (
    <table className="w-full border-collapse text-[11.5px]">
        <thead>
            <tr style={{ background: '#E9E8FB' }}>
                <th className="px-2 py-1 text-left font-black" style={{ color: TINTA }}>Mes</th>
                <th className="px-2 py-1 text-right font-black" style={{ color: TINTA }}>{anio}</th>
                <th className="px-2 py-1 text-right font-black text-slate-500">{anterior}</th>
            </tr>
        </thead>
        <tbody>
            {meses.map((m) => (
                <tr key={m.mes} className="border-b border-slate-100">
                    <td className="px-2 py-1 font-bold">{m.mes}{m.parcial ? '*' : ''}</td>
                    <td className="px-2 py-1 text-right font-black tabular-nums" style={{ color: TINTA }}>{m.actual}</td>
                    <td className="px-2 py-1 text-right tabular-nums text-slate-500">{m.anterior}</td>
                </tr>
            ))}
        </tbody>
    </table>
);

export default function ReporteSemanalAsesor({ reporte }) {
    const tarjeta = useRef(null);
    const [descargando, setDescargando] = useState(false);
    const meses = reporte.homicidios_por_mes || [];
    const mitad = Math.ceil(meses.length / 2);
    const hayParcial = meses.some((m) => m.parcial);

    const descargar = async () => {
        if (!tarjeta.current || descargando) return;
        setDescargando(true);
        try {
            const { default: html2canvas } = await import('html2canvas-pro');
            const lienzo = await html2canvas(tarjeta.current, { scale: 3, backgroundColor: '#ffffff', useCORS: true });
            const enlace = document.createElement('a');
            enlace.href = lienzo.toDataURL('image/png');
            enlace.download = `Reporte semanal seguridad - corte ${reporte.corte}.png`;
            enlace.click();
        } finally {
            setDescargando(false);
        }
    };

    return (
        <div>
            <div ref={tarjeta} className="overflow-hidden rounded-xl border border-slate-200 bg-white" style={{ color: TINTA }}>
                <div style={{ height: 6, background: AMARILLO }} />
                <header className="flex items-center gap-3 px-4 py-3 text-white" style={{ background: AZUL }}>
                    <img src="/assets/escudo-limpio.png" alt="" className="h-11 w-auto" />
                    <div>
                        <p className="text-[10px] font-black uppercase tracking-widest" style={{ color: AMARILLO }}>Alcaldía de Jamundí</p>
                        <p className="text-[10px] font-bold text-white/80">Secretaría de Seguridad y Convivencia</p>
                        <p className="text-[17px] font-black leading-tight">{reporte.titulo}</p>
                    </div>
                </header>
                <p className="px-4 py-1.5 text-center text-[12px] font-black" style={{ background: AMARILLO }}>{reporte.periodo}</p>

                <div className="px-4 pb-3">
                    <Cuadro titulo={`En lo corrido del año, frente a ${reporte.anio_anterior}`}>
                        <thead>
                            <tr style={{ background: AZUL }}>
                                <th className={th}>Delito</th><th className={th}>{reporte.anio}</th>
                                <th className={th}>{reporte.anio_anterior}</th><th className={th}>Cambio</th>
                            </tr>
                        </thead>
                        <tbody>
                            {reporte.filas.map((f) => (
                                <tr key={f.nombre}>
                                    <td className={td}>{f.nombre}</td>
                                    <td className={`${td} text-[14px] font-black`} style={{ color: AZUL }}>{fmt(f.anio)}</td>
                                    <td className={`${td} text-slate-500`}>{fmt(f.anio_anterior)}</td>
                                    <td className={td}><Cambio diferencia={f.diferencia} porcentaje={f.porcentaje} /></td>
                                </tr>
                            ))}
                        </tbody>
                    </Cuadro>

                    <Cuadro titulo={`Última semana · ${reporte.semana.toLowerCase()}`}>
                        <thead>
                            <tr style={{ background: TINTA }}>
                                <th className={th}>Delito</th>
                                <th className={th}>Esta semana</th>
                                <th className={th}>Semana anterior</th>
                            </tr>
                        </thead>
                        <tbody>
                            {reporte.filas.map((f) => (
                                <tr key={f.nombre}>
                                    <td className={td}>{f.nombre}</td>
                                    <td className={`${td} text-[14px] font-black`}>{fmt(f.semana)}</td>
                                    <td className={`${td} text-slate-500`}>{fmt(f.semana_previa)}</td>
                                </tr>
                            ))}
                        </tbody>
                    </Cuadro>

                    {meses.length > 0 && (
                        <section className="mt-3">
                            <h4 className="mb-1 text-[11px] font-black uppercase tracking-wider" style={{ color: AZUL }}>Homicidios por mes</h4>
                            <div className="grid grid-cols-2 gap-2">
                                <TablaMeses meses={meses.slice(0, mitad)} anio={reporte.anio} anterior={reporte.anio_anterior} />
                                <TablaMeses meses={meses.slice(mitad)} anio={reporte.anio} anterior={reporte.anio_anterior} />
                            </div>
                            {hayParcial && <p className="mt-1 text-[10px] text-slate-500">* Mes en curso, hasta el día del corte (el año anterior, hasta el mismo día).</p>}
                        </section>
                    )}
                </div>

                <footer className="px-4 py-2 text-white" style={{ background: TINTA, borderTop: `4px solid ${AMARILLO}` }}>
                    <p className="text-[11px] font-black">Observatorio del Delito · SISC Jamundí</p>
                    <p className="text-[10px] text-white/70">Fuente: {reporte.fuente}.</p>
                    {(reporte.notas || []).map((n) => <p key={n} className="text-[10px] text-white/60">{n}</p>)}
                </footer>
            </div>
            <button type="button" onClick={descargar} disabled={descargando}
                className="mt-2 inline-flex items-center gap-1.5 rounded-full bg-[#281FD0] px-3 py-1.5 text-xs font-black text-white hover:bg-[#3026D9] disabled:opacity-60">
                {descargando ? <Loader2 size={13} className="animate-spin" /> : <Download size={13} />} Descargar imagen para WhatsApp
            </button>
        </div>
    );
}
