import React, { useEffect, useMemo, useState } from 'react';
import {
    ArrowLeft,
    BarChart3,
    CalendarDays,
    CheckCircle2,
    Database,
    Download,
    FileText,
    Info,
    Printer,
    RefreshCcw,
    ShieldCheck
} from 'lucide-react';
import { API_BASE_URL } from '../utils/apiConfig';

const SECTIONS = [
    { id: 'transparency-info', label: 'Transparencia', icon: ShieldCheck },
    { id: 'open-data', label: 'Datos abiertos', icon: Database },
    { id: 'technical-bulletins', label: 'Boletines técnicos', icon: FileText },
    { id: 'accountability', label: 'Rendición de cuentas', icon: CheckCircle2, href: 'https://www.jamundi.gov.co/Paginas/Rendici%C3%B3n-de-cuentas.aspx' },
];

const csvCell = (value) => `"${String(value ?? '').replaceAll('"', '""')}"`;

const downloadCsv = (filename, headers, rows) => {
    const body = [headers, ...rows].map((row) => row.map(csvCell).join(';')).join('\n');
    const blob = new Blob([`\uFEFF${body}`], { type: 'text/csv;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    link.click();
    URL.revokeObjectURL(url);
};

const PublicInformation = ({ initialSection = 'transparency-info', onBack, onNavigate }) => {
    const [activeSection, setActiveSection] = useState(initialSection);
    const [data, setData] = useState({ kpis: null, distribution: [], metadata: null });
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');

    const loadData = async () => {
        setLoading(true);
        setError('');
        try {
            const [kpiResponse, distributionResponse, metadataResponse] = await Promise.all([
                fetch(`${API_BASE_URL}/analitica/estadisticas/kpis`),
                fetch(`${API_BASE_URL}/analitica/estadisticas/distribucion`),
                fetch(`${API_BASE_URL}/analitica/estadisticas/ultima-actualizacion`),
            ]);
            if (![kpiResponse, distributionResponse, metadataResponse].every((response) => response.ok)) {
                throw new Error('No fue posible consultar todas las fuentes públicas.');
            }
            const [kpis, distribution, metadata] = await Promise.all([
                kpiResponse.json(),
                distributionResponse.json(),
                metadataResponse.json(),
            ]);
            setData({ kpis, distribution, metadata });
        } catch (requestError) {
            setError(requestError.message || 'No fue posible cargar la información pública.');
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => { loadData(); }, []);
    useEffect(() => { setActiveSection(initialSection); }, [initialSection]);

    const indicatorRows = useMemo(() => {
        if (!data.kpis) return [];
        return [
            ['Total de hechos', data.kpis.total_incidentes],
            ['Homicidios', data.kpis.homicidios],
            ['Hurto a personas', data.kpis.hurto_personas],
            ['Hurto de vehículos', data.kpis.hurto_vehiculos],
            ['Hurto a comercio', data.kpis.hurto_comercio],
            ['Hurto a residencias', data.kpis.hurto_residencias],
            ['Lesiones personales', data.kpis.lesiones],
            ['Violencia intrafamiliar', data.kpis.vif],
        ];
    }, [data.kpis]);

    const source = data.kpis?.fuente === 'POLICIA_SEMANAL'
        ? 'Policía Nacional - SABANA SIEDCO/PONAL'
        : data.kpis?.fuente || 'Fuente oficial en validación';
    const cutoff = data.metadata?.ultima_fecha || 'Corte no disponible';

    const downloadIndicators = () => downloadCsv(
        `sisc_indicadores_${new Date().toISOString().slice(0, 10)}.csv`,
        ['indicador', 'valor', 'fecha_corte', 'fuente'],
        indicatorRows.map(([indicator, value]) => [indicator, value, cutoff, source])
    );

    const downloadDistribution = () => downloadCsv(
        `sisc_distribucion_${new Date().toISOString().slice(0, 10)}.csv`,
        ['delito', 'casos', 'fecha_corte', 'fuente'],
        data.distribution.map((item) => [item.name, item.value, cutoff, source])
    );

    return (
        <div className="min-h-screen bg-slate-50 text-slate-900">
            <header className="bg-[#171f3a] text-white border-b-4 border-amber-400 print:bg-white print:text-slate-900">
                <div className="max-w-6xl mx-auto px-5 py-6 flex flex-col gap-5 md:flex-row md:items-center md:justify-between">
                    <div>
                        <button onClick={onBack} className="inline-flex items-center gap-2 text-xs font-bold text-white/70 hover:text-white mb-3 print:hidden">
                            <ArrowLeft size={16} /> Volver al portal ciudadano
                        </button>
                        <h1 className="text-2xl md:text-3xl font-black">Centro público de información</h1>
                        <p className="mt-2 text-sm text-white/70 max-w-2xl print:text-slate-600">
                            Datos agregados sobre seguridad y convivencia, con fuente y fecha de corte visibles.
                        </p>
                    </div>
                    <button onClick={loadData} disabled={loading} className="self-start p-3 border border-white/20 hover:bg-white/10 disabled:opacity-50 print:hidden" title="Actualizar información">
                        <RefreshCcw size={18} className={loading ? 'animate-spin' : ''} />
                    </button>
                </div>
            </header>

            <nav className="bg-white border-b border-slate-200 print:hidden" aria-label="Información pública">
                <div className="max-w-6xl mx-auto px-4 py-2 flex gap-1 overflow-x-auto">
                    {SECTIONS.map((section) => section.href ? (
                        <a
                            key={section.id}
                            href={section.href}
                            className="flex items-center gap-2 px-4 py-3 text-sm font-bold whitespace-nowrap border-b-2 border-transparent text-slate-500 hover:text-slate-900"
                        >
                            <section.icon size={17} /> {section.label}
                        </a>
                    ) : (
                        <button
                            key={section.id}
                            onClick={() => setActiveSection(section.id)}
                            className={`flex items-center gap-2 px-4 py-3 text-sm font-bold whitespace-nowrap border-b-2 ${activeSection === section.id ? 'border-[#281FD0] text-[#281FD0]' : 'border-transparent text-slate-500 hover:text-slate-900'}`}
                        >
                            <section.icon size={17} /> {section.label}
                        </button>
                    ))}
                </div>
            </nav>

            <main className="max-w-6xl mx-auto px-5 py-8 md:py-12">
                {error && <div className="mb-8 border-l-4 border-red-500 bg-red-50 p-4 text-sm text-red-700">{error}</div>}

                {activeSection === 'transparency-info' && (
                    <section>
                        <h2 className="text-2xl font-black mb-2">Cómo se construye la información</h2>
                        <p className="text-slate-600 mb-8 max-w-3xl">La publicación ciudadana usa cifras agregadas. No muestra nombres, direcciones exactas, teléfonos ni información operativa reservada.</p>
                        <dl className="grid md:grid-cols-2 border-y border-slate-200">
                            <div className="py-5 md:pr-8 border-b md:border-r border-slate-200"><dt className="text-xs font-black uppercase text-slate-500">Fuente principal</dt><dd className="mt-2 font-bold">{source}</dd></div>
                            <div className="py-5 md:pl-8 border-b border-slate-200"><dt className="text-xs font-black uppercase text-slate-500">Último registro disponible</dt><dd className="mt-2 font-bold">{cutoff}</dd></div>
                            <div className="py-5 md:pr-8 md:border-r border-slate-200"><dt className="text-xs font-black uppercase text-slate-500">Cobertura</dt><dd className="mt-2">Hechos registrados para el municipio de Jamundí.</dd></div>
                            <div className="py-5 md:pl-8"><dt className="text-xs font-black uppercase text-slate-500">Tratamiento público</dt><dd className="mt-2">Agregación estadística y ubicación aproximada para proteger a las personas.</dd></div>
                        </dl>
                        <button onClick={() => onNavigate?.('transparency')} className="mt-8 inline-flex items-center gap-2 bg-[#281FD0] text-white px-5 py-3 font-bold hover:bg-indigo-800">
                            <BarChart3 size={18} /> Consultar tablero ciudadano
                        </button>
                    </section>
                )}

                {activeSection === 'open-data' && (
                    <section>
                        <h2 className="text-2xl font-black mb-2">Descargar datos abiertos</h2>
                        <p className="text-slate-600 mb-8">Archivos CSV anonimizados, listos para análisis y con trazabilidad de fuente y corte.</p>
                        <div className="divide-y divide-slate-200 border-y border-slate-200">
                            <div className="py-6 flex flex-col md:flex-row md:items-center md:justify-between gap-4">
                                <div><h3 className="font-black">Indicadores consolidados</h3><p className="text-sm text-slate-500 mt-1">{indicatorRows.length} indicadores públicos · corte {cutoff}</p></div>
                                <button onClick={downloadIndicators} disabled={!indicatorRows.length} className="inline-flex items-center justify-center gap-2 bg-[#281FD0] text-white px-5 py-3 font-bold disabled:opacity-40"><Download size={18} /> Descargar CSV</button>
                            </div>
                            <div className="py-6 flex flex-col md:flex-row md:items-center md:justify-between gap-4">
                                <div><h3 className="font-black">Distribución por delito</h3><p className="text-sm text-slate-500 mt-1">{data.distribution.length} categorías agregadas · corte {cutoff}</p></div>
                                <button onClick={downloadDistribution} disabled={!data.distribution.length} className="inline-flex items-center justify-center gap-2 border border-[#281FD0] text-[#281FD0] px-5 py-3 font-bold disabled:opacity-40"><Download size={18} /> Descargar CSV</button>
                            </div>
                        </div>
                        <p className="mt-6 flex gap-2 text-xs text-slate-500"><Info size={16} className="shrink-0" /> Cite la fuente como “SISC Jamundí / Policía Nacional - SABANA SIEDCO/PONAL” e indique la fecha de descarga.</p>
                    </section>
                )}

                {activeSection === 'technical-bulletins' && (
                    <section>
                        <h2 className="text-2xl font-black mb-2">Boletines técnicos</h2>
                        <p className="text-slate-600 mb-8">Solo se publican documentos revisados y aprobados para circulación ciudadana.</p>
                        <div className="border-y border-slate-200 py-7 flex flex-col md:flex-row md:items-center md:justify-between gap-5">
                            <div className="flex gap-4"><CalendarDays className="text-[#281FD0] shrink-0" /><div><h3 className="font-black">Ficha automática de indicadores</h3><p className="text-sm text-slate-500 mt-1">Vista informativa en tiempo real. No reemplaza un boletín oficial aprobado.</p></div></div>
                            <button onClick={() => window.print()} className="inline-flex items-center justify-center gap-2 border border-slate-300 px-5 py-3 font-bold print:hidden"><Printer size={18} /> Imprimir ficha</button>
                        </div>
                        <div className="mt-8 grid grid-cols-2 md:grid-cols-4 gap-px bg-slate-200 border border-slate-200">
                            {indicatorRows.slice(0, 4).map(([label, value]) => <div key={label} className="bg-white p-5"><p className="text-xs text-slate-500">{label}</p><p className="text-2xl font-black mt-2">{value ?? '—'}</p></div>)}
                        </div>
                        <p className="mt-8 text-sm text-amber-800 bg-amber-50 border-l-4 border-amber-400 p-4">Aún no hay boletines oficiales aprobados cargados en este repositorio público.</p>
                    </section>
                )}

                {activeSection === 'accountability' && (
                    <section>
                        <h2 className="text-2xl font-black mb-2">Rendición de cuentas</h2>
                        <p className="text-slate-600 mb-8">Este espacio publicará compromisos verificables sin revelar tácticas, personas o actuaciones reservadas.</p>
                        <div className="grid md:grid-cols-4 gap-px bg-slate-200 border border-slate-200">
                            {['Problema detectado', 'Acción acordada', 'Entidad responsable', 'Resultado medido'].map((label, index) => <div key={label} className="bg-white p-5"><span className="text-xs font-black text-[#281FD0]">0{index + 1}</span><p className="font-bold mt-3">{label}</p></div>)}
                        </div>
                        <div className="mt-8 border-l-4 border-slate-300 bg-white p-5">
                            <h3 className="font-black">Estado de publicación</h3>
                            <p className="text-sm text-slate-600 mt-2">No hay compromisos institucionales públicos registrados todavía. Las cifras del tablero muestran resultados observados, pero no deben atribuirse a una acción específica sin acta, responsable y periodo de evaluación.</p>
                        </div>
                    </section>
                )}
            </main>
        </div>
    );
};

export default PublicInformation;