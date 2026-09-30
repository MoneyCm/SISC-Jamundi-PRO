import React, { useEffect, useState } from 'react';
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { History } from 'lucide-react';
import { apiJson } from '../utils/apiClient';

const numero = (valor) => new Intl.NumberFormat('es-CO').format(Number(valor || 0));
const cambio = (valor) => (valor === null || valor === undefined ? '—' : `${valor > 0 ? '+' : ''}${String(valor).replace('.', ',')}%`);
const colorCambio = (valor) => (valor === null || valor === undefined ? 'text-slate-400' : valor > 0 ? 'text-red-700' : valor < 0 ? 'text-emerald-700' : 'text-slate-600');
const minuscula = (texto) => (texto ? texto.charAt(0).toLowerCase() + texto.slice(1) : '');
const tarjeta = 'bg-white p-5 md:p-8 rounded-3xl md:rounded-[2.5rem] shadow-xl shadow-slate-100 border border-slate-50';

// Lectura automática: solo describe las cifras; si dos comportamientos se mueven fuerte en sentidos
// opuestos, advierte que puede ser un cambio en cómo se clasifican los comparendos.
const lecturaTendencia = (datos) => {
    const partes = [];
    const actual = datos.anios.find((item) => item.en_curso);
    if (actual && datos.variacion_tramo !== null && datos.variacion_tramo !== undefined) {
        partes.push(`Del ${datos.tramo}, ${datos.anio_actual} lleva ${numero(actual.mismo_tramo)} comparendos: ${cambio(datos.variacion_tramo)} frente al mismo tramo de ${datos.anio_previo}.`);
    }
    // Se ordena por cuántos comparendos cambian, no por porcentaje: 58 a 19 pesa menos que 2.226 a 1.250.
    const diferencia = (item) => (item.por_anio[datos.anio_actual] || 0) - (item.por_anio[datos.anio_previo] || 0);
    const conCambio = datos.comportamientos.filter((item) => item.variacion !== null && (item.por_anio[datos.anio_previo] || 0) >= 30);
    const sube = [...conCambio].sort((a, b) => diferencia(b) - diferencia(a))[0];
    const baja = [...conCambio].sort((a, b) => diferencia(a) - diferencia(b))[0];
    if (sube && diferencia(sube) > 0) partes.push(`Lo que más sube es ${minuscula(sube.etiqueta)}: de ${numero(sube.por_anio[datos.anio_previo])} a ${numero(sube.por_anio[datos.anio_actual])} (${cambio(sube.variacion)}).`);
    if (baja && diferencia(baja) < 0) partes.push(`Lo que más baja es ${minuscula(baja.etiqueta)}: de ${numero(baja.por_anio[datos.anio_previo])} a ${numero(baja.por_anio[datos.anio_actual])} (${cambio(baja.variacion)}).`);
    if (sube && baja && sube.variacion >= 40 && baja.variacion <= -40 && diferencia(sube) >= 100 && diferencia(baja) <= -100) {
        partes.push('Un cambio tan fuerte y en sentidos opuestos puede deberse a que la Policía está clasificando distinto los mismos hechos; conviene confirmarlo con la Policía antes de presentarlo como un cambio en la convivencia.');
    }
    return partes.join(' ');
};

/** Comparendos del RNMC año por año (desde 2018): año completo y el mismo tramo del año en curso. */
const TendenciaConvivencia = () => {
    const [datos, setDatos] = useState(null);

    useEffect(() => {
        let vigente = true;
        apiJson('/inspecciones/stats/tendencia').then((resultado) => { if (vigente) setDatos(resultado); }).catch(() => {});
        return () => { vigente = false; };
    }, []);

    if (!datos?.anios?.length) return null;
    const grafica = datos.anios.map((item) => ({
        anio: String(item.anio),
        completo: item.en_curso ? null : item.total,
        tramo: item.mismo_tramo,
    }));
    const anios = datos.anios.map((item) => item.anio).slice(-4);

    return (
        <div className={tarjeta}>
            <h3 className="text-xl font-black text-slate-900 flex items-center gap-3">
                <History className="text-indigo-600" /> Tendencia {datos.anios[0].anio}-{datos.anio_actual}
            </h3>
            <p className="mt-2 text-sm font-bold leading-relaxed text-slate-700">{lecturaTendencia(datos)}</p>

            <div className="mt-6">
                <ResponsiveContainer width="100%" height={280}>
                    <BarChart data={grafica}>
                        <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                        <XAxis dataKey="anio" axisLine={false} tickLine={false} tick={{ fill: '#64748b', fontSize: 11, fontWeight: 700 }} />
                        <YAxis axisLine={false} tickLine={false} tick={{ fill: '#94a3b8', fontSize: 11 }} />
                        <Tooltip formatter={(valor, nombre) => [numero(valor), nombre]} cursor={{ fill: '#f8fafc' }} />
                        <Legend wrapperStyle={{ fontSize: 12, fontWeight: 700 }} />
                        <Bar dataKey="completo" name="Año completo" fill="#CBD5E1" radius={[6, 6, 0, 0]} />
                        <Bar dataKey="tramo" name={`Del ${datos.tramo}`} fill="#281FD0" radius={[6, 6, 0, 0]} />
                    </BarChart>
                </ResponsiveContainer>
                <p className="mt-1 text-xs font-semibold text-slate-500">Las barras azules comparan tramos iguales de cada año. El RNMC empezó en 2017, por eso los primeros años son más bajos.</p>
            </div>

            <div className="mt-8 grid gap-8 lg:grid-cols-2">
                <div>
                    <p className="text-[11px] font-black uppercase tracking-wide text-slate-500">Comportamientos · del {datos.tramo}</p>
                    <div className="mt-2 overflow-x-auto">
                        <table className="w-full text-left text-sm">
                            <thead>
                                <tr className="text-[10px] font-black uppercase tracking-widest text-slate-400">
                                    <th className="py-2 pr-3">Comportamiento</th>
                                    {anios.map((anio) => <th key={anio} className="py-2 px-2 text-right">{anio}</th>)}
                                    <th className="py-2 pl-2 text-right">Cambio</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-slate-100">
                                {datos.comportamientos.map((item) => (
                                    <tr key={item.articulo}>
                                        <td className="py-2 pr-3 font-semibold text-slate-800">{item.etiqueta}</td>
                                        {anios.map((anio) => <td key={anio} className="py-2 px-2 text-right tabular-nums">{numero(item.por_anio[anio])}</td>)}
                                        <td className={`py-2 pl-2 text-right font-black tabular-nums ${colorCambio(item.variacion)}`}>{cambio(item.variacion)}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </div>
                <div>
                    <p className="text-[11px] font-black uppercase tracking-wide text-slate-500">Barrios · del {datos.tramo}</p>
                    <div className="mt-2 overflow-x-auto">
                        <table className="w-full text-left text-sm">
                            <thead>
                                <tr className="text-[10px] font-black uppercase tracking-widest text-slate-400">
                                    <th className="py-2 pr-3">Barrio</th>
                                    <th className="py-2 px-2 text-right">{datos.anio_previo}</th>
                                    <th className="py-2 px-2 text-right">{datos.anio_actual}</th>
                                    <th className="py-2 pl-2 text-right">Cambio</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-slate-100">
                                {datos.barrios.map((item) => (
                                    <tr key={item.barrio}>
                                        <td className="py-2 pr-3 font-black text-slate-900">{item.barrio}</td>
                                        <td className="py-2 px-2 text-right tabular-nums">{numero(item.por_anio[datos.anio_previo])}</td>
                                        <td className="py-2 px-2 text-right tabular-nums">{numero(item.por_anio[datos.anio_actual])}</td>
                                        <td className={`py-2 pl-2 text-right font-black tabular-nums ${colorCambio(item.variacion)}`}>{cambio(item.variacion)}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                    <p className="mt-2 text-xs font-semibold text-slate-500">Cambio frente al mismo tramo del año anterior. Rojo: más comparendos; verde: menos.</p>
                </div>
            </div>
        </div>
    );
};

export default TendenciaConvivencia;
