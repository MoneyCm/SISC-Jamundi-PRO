import React, { useEffect, useState } from 'react';
import { Loader, Scale, Info, ExternalLink } from 'lucide-react';
import { apiJson } from '../utils/apiClient';

// Respuesta judicial: en qué etapa van los procesos de la Fiscalía por hechos en Jamundí.
// Uso interno (SISC de la oficina). Los datos los guarda la revisión semanal de la Fiscalía.

const fmt = (n) => (n == null ? '—' : Number(n).toLocaleString('es-CO'));
const pct = (parte, total) => (total ? `${((100 * parte) / total).toLocaleString('es-CO', { maximumFractionDigits: 1 })} %` : '—');
const fechaLarga = (iso) => {
    if (!iso) return 'sin fecha';
    const d = new Date(`${String(iso).slice(0, 10)}T00:00:00`);
    return d.toLocaleDateString('es-CO', { day: 'numeric', month: 'long', year: 'numeric' });
};

const ETAPAS = [
    { id: 'indagacion_inactiva', label: 'Indagación inactiva', ayuda: 'Suele ser archivo o suspensión; el dato abierto no dice el motivo' },
    { id: 'indagacion_activa', label: 'Indagación activa', ayuda: 'Aún se busca establecer el hecho y el autor' },
    { id: 'investigacion', label: 'Investigación', ayuda: 'Ya hubo imputación de cargos' },
    { id: 'juicio', label: 'Juicio' },
    { id: 'condena', label: 'Ejecución de penas', ayuda: 'Hay condena' },
    { id: 'sin_informacion', label: 'Sin información' },
];

const Tarjeta = ({ titulo, dato, total, anio, nota }) => (
    <div className="bg-white rounded-2xl p-5 shadow-sm border border-slate-100 flex flex-col gap-1">
        <p className="text-[11px] font-black text-slate-400 uppercase tracking-widest">{titulo}</p>
        <p className="text-3xl font-black text-primary">{pct(dato, total)}</p>
        <p className="text-xs text-slate-600">
            {fmt(dato)} de {fmt(total)} procesos por hechos de {anio} llegaron a juicio o condena
        </p>
        {nota && <p className="text-[11px] text-slate-400">{nota}</p>}
    </div>
);

const encabezadoAnio = (anio, enCurso, corte) => (
    <th key={anio} className="px-3 py-2 text-right">
        {anio}
        {anio === enCurso && (
            <span className="block text-[10px] font-normal normal-case tracking-normal text-slate-400">
                hasta el corte, muy reciente
            </span>
        )}
    </th>
);

const TablaEtapas = ({ titulo, datos, anios, enCurso, corte }) => (
    <div className="bg-white rounded-2xl shadow-sm border border-slate-100 overflow-x-auto">
        <h3 className="px-4 pt-4 pb-2 text-sm font-black text-slate-800">{titulo}</h3>
        <table className="w-full text-sm">
            <thead>
                <tr className="text-[11px] uppercase tracking-wider text-slate-500 border-b border-slate-100">
                    <th className="px-4 py-2 text-left">Etapa del proceso</th>
                    {anios.map((a) => encabezadoAnio(a, enCurso, corte))}
                </tr>
            </thead>
            <tbody>
                {ETAPAS.filter((e) => anios.some((a) => datos[a]?.[e.id])).map((e) => (
                    <tr key={e.id} className="border-b border-slate-50">
                        <td className="px-4 py-2 text-slate-700">
                            {e.label}
                            {e.ayuda && <span className="block text-[11px] text-slate-400">{e.ayuda}</span>}
                        </td>
                        {anios.map((a) => (
                            <td key={a} className="px-3 py-2 text-right tabular-nums text-slate-700">
                                {fmt(datos[a]?.[e.id])}
                                <span className="block text-[11px] text-slate-400">{pct(datos[a]?.[e.id], datos[a]?.total)}</span>
                            </td>
                        ))}
                    </tr>
                ))}
                <tr className="font-black text-slate-900 bg-slate-50">
                    <td className="px-4 py-2">Llegaron a juicio o condena</td>
                    {anios.map((a) => (
                        <td key={a} className="px-3 py-2 text-right tabular-nums">
                            {fmt(datos[a]?.juicio_o_condena)}
                            <span className="block text-[11px] font-bold text-slate-500">{pct(datos[a]?.juicio_o_condena, datos[a]?.total)}</span>
                        </td>
                    ))}
                </tr>
                <tr className="text-slate-600">
                    <td className="px-4 py-2">Total de procesos</td>
                    {anios.map((a) => <td key={a} className="px-3 py-2 text-right tabular-nums">{fmt(datos[a]?.total)}</td>)}
                </tr>
            </tbody>
        </table>
    </div>
);

const RespuestaJudicial = () => {
    const [estado, setEstado] = useState({ cargando: true, datos: null, error: null });

    useEffect(() => {
        let vivo = true;
        apiJson('/source-center/fiscalia/respuesta-judicial')
            .then((datos) => vivo && setEstado({ cargando: false, datos, error: null }))
            .catch((error) => vivo && setEstado({ cargando: false, datos: null, error: error.message }));
        return () => { vivo = false; };
    }, []);

    if (estado.cargando) {
        return <div className="flex justify-center py-16"><Loader className="animate-spin text-primary" /></div>;
    }
    if (estado.error) {
        return <div className="bg-red-50 text-red-700 p-4 rounded-xl text-sm border border-red-100">No se pudo cargar la respuesta judicial: {estado.error}</div>;
    }
    const { datos } = estado;
    if (!datos?.available) {
        return (
            <div className="bg-amber-50 text-amber-900 p-4 rounded-xl text-sm border border-amber-200">
                Todavía no hay datos de la Fiscalía. Se llenan solos en la próxima revisión semanal (Centro de fuentes → Fiscalía).
            </div>
        );
    }

    const s = datos.seguimiento;
    const anios = s.anios.map(String);
    const enCurso = String(s.anio_en_curso);
    const completos = anios.filter((a) => a !== enCurso);
    const ultimoCompleto = completos[completos.length - 1];

    return (
        <div className="flex flex-col gap-5">
            <div className="bg-white rounded-2xl p-5 shadow-sm border border-slate-100 flex gap-3">
                <Scale className="text-primary shrink-0" size={22} />
                <div className="text-sm text-slate-600">
                    <p className="font-black text-slate-800">¿Qué pasa después de la denuncia?</p>
                    <p>
                        Procesos de la Fiscalía por hechos ocurridos en Jamundí y la etapa en que van. Corte de la Fiscalía:{' '}
                        <strong>{fechaLarga(datos.corte)}</strong>. Fuente:{' '}
                        <a href={datos.enlace} target="_blank" rel="noreferrer" className="text-primary font-bold inline-flex items-center gap-1">
                            {datos.fuente} <ExternalLink size={12} />
                        </a>
                    </p>
                </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
                {completos.map((a) => (
                    <Tarjeta key={`t${a}`} titulo={`Todos los delitos · ${a}`} anio={a}
                        dato={s.todos[a]?.juicio_o_condena} total={s.todos[a]?.total} />
                ))}
                {completos.map((a) => (
                    <Tarjeta key={`h${a}`} titulo={`Homicidio doloso · ${a}`} anio={a}
                        dato={s.homicidio_doloso[a]?.juicio_o_condena} total={s.homicidio_doloso[a]?.total}
                        nota="Procesos, no homicidios: un hecho puede abrir varios procesos" />
                ))}
            </div>

            <TablaEtapas titulo="Todos los delitos" datos={s.todos} anios={anios} enCurso={enCurso} />
            <TablaEtapas titulo="Homicidio doloso" datos={s.homicidio_doloso} anios={anios} enCurso={enCurso} />

            {s.por_delito?.length > 0 && (
                <div className="bg-white rounded-2xl shadow-sm border border-slate-100 overflow-x-auto">
                    <h3 className="px-4 pt-4 pb-2 text-sm font-black text-slate-800">
                        Delitos con más procesos en {ultimoCompleto}
                    </h3>
                    <table className="w-full text-sm">
                        <thead>
                            <tr className="text-[11px] uppercase tracking-wider text-slate-500 border-b border-slate-100">
                                <th className="px-4 py-2 text-left">Delito (capítulo del Código Penal)</th>
                                {completos.map((a) => <th key={a} className="px-3 py-2 text-right">Procesos {a}</th>)}
                                {completos.map((a) => <th key={`j${a}`} className="px-3 py-2 text-right">Juicio o condena {a}</th>)}
                            </tr>
                        </thead>
                        <tbody>
                            {s.por_delito.map((f) => (
                                <tr key={f.delito} className="border-b border-slate-50">
                                    <td className="px-4 py-2 text-slate-700">{f.delito}</td>
                                    {completos.map((a) => <td key={a} className="px-3 py-2 text-right tabular-nums">{fmt(f[a]?.total)}</td>)}
                                    {completos.map((a) => (
                                        <td key={`j${a}`} className="px-3 py-2 text-right tabular-nums">
                                            {fmt(f[a]?.juicio_o_condena)}{' '}
                                            <span className="text-[11px] text-slate-400">({pct(f[a]?.juicio_o_condena, f[a]?.total)})</span>
                                        </td>
                                    ))}
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            )}

            <div className="bg-slate-50 rounded-2xl p-5 border border-slate-200 text-sm text-slate-600 flex gap-3">
                <Info className="text-slate-400 shrink-0" size={18} />
                <div className="flex flex-col gap-1.5">
                    <p className="font-black text-slate-800">Cómo leerlo y cómo citarlo</p>
                    <p>• Se cuentan <strong>procesos</strong>, no delitos ni víctimas. Por ejemplo, en {completos[0]} hubo {fmt(s.homicidio_doloso[completos[0]]?.total)} procesos por homicidio doloso, más que los homicidios que reporta la Policía. Decir "el X % de los procesos por homicidio llegó a juicio o condena", no "el X % de los homicidios se resuelve".</p>
                    <p>• El avance depende de la Fiscalía y los jueces, no de la Secretaría. Sirve para pedir resultados en el Consejo de Seguridad.</p>
                    <p>• El año {enCurso} es muy reciente: es normal que casi todo siga en indagación. Para medir resultados, use los años anteriores.</p>
                    <p>• El homicidio culposo (casi todo de tránsito) va aparte: {completos.map((a) => `${fmt(s.homicidio_culposo[a]?.total)} procesos en ${a}`).join(' y ')}.</p>
                    <p>• Uso interno. Antes de publicarlo, la Secretaría debe aprobar el texto.</p>
                </div>
            </div>
        </div>
    );
};

export default RespuestaJudicial;
