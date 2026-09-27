import React, { useState } from 'react';
import {
    Phone,
    ShieldCheck,
    Home,
    Scale,
    Baby,
    AlertCircle,
    ChevronDown,
    ChevronUp,
    ExternalLink
} from 'lucide-react';

// Solo líneas nacionales oficiales: no se publican direcciones, horarios ni teléfonos locales que el
// SISC no pueda mantener verificados. Para eso se remite a la página oficial de la Alcaldía.
const LINES = [
    { label: 'Emergencias', number: '123', detail: 'Riesgo para la vida o la integridad. Todo el día, todos los días.', icon: Phone },
    { label: 'Línea 155', number: '155', detail: 'Orientación a mujeres víctimas de violencia. Gratuita y confidencial.', icon: ShieldCheck },
    { label: 'Línea 141 del ICBF', number: '141', detail: 'Niñas, niños y adolescentes en riesgo o víctimas de maltrato.', icon: Baby },
    { label: 'Fiscalía: denuncias', number: '122', detail: 'Para denunciar un delito ante la Fiscalía General de la Nación.', icon: Scale },
];

const ROUTES = [
    {
        id: 'vbg',
        title: 'Violencia intrafamiliar o basada en género',
        color: 'bg-purple-600',
        steps: [
            { title: 'Si hay peligro inmediato', description: 'Llame al 123. Busque un lugar seguro y, si puede, la compañía de alguien de confianza.', agency: 'Emergencia' },
            { title: 'Atención en salud', description: 'Acuda a urgencias del centro de salud más cercano. La atención a víctimas de violencia es prioritaria y no exige denuncia previa.', agency: 'Salud' },
            { title: 'Medidas de protección', description: 'Una Comisaría de Familia puede ordenar medidas para que el agresor se aleje o salga de la vivienda. La Línea 155 orienta sobre cómo solicitarlas.', agency: 'Protección' },
            { title: 'Denuncia', description: 'Puede denunciar ante la Fiscalía (línea 122) o en una estación de Policía. Denunciar no es requisito para recibir atención ni protección.', agency: 'Justicia' },
        ],
    },
    {
        id: 'infancia',
        title: 'Maltrato a niñas, niños o adolescentes',
        color: 'bg-blue-600',
        steps: [
            { title: 'Reporte', description: 'Llame a la Línea 141 del ICBF. Puede reportar aunque no esté seguro o no sea familiar del niño o la niña; el reporte puede ser anónimo.', agency: 'ICBF' },
            { title: 'Verificación de derechos', description: 'El ICBF o la Comisaría de Familia verifica la situación y, si es necesario, abre un proceso para proteger al niño, niña o adolescente.', agency: 'Protección' },
            { title: 'Si hay peligro inmediato', description: 'Llame al 123.', agency: 'Emergencia' },
        ],
    },
];

const RouteSection = ({ title, color, children }) => {
    const [isOpen, setIsOpen] = useState(true);
    return (
        <div className="bg-white rounded-2xl shadow-sm border border-slate-100 overflow-hidden mb-6">
            <button
                onClick={() => setIsOpen(!isOpen)}
                aria-expanded={isOpen}
                className={`w-full flex items-center justify-between p-6 text-left transition-colors ${isOpen ? 'bg-slate-50' : 'hover:bg-slate-50'}`}
            >
                <div className="flex items-center gap-4">
                    <div className={`p-3 rounded-xl ${color} text-white`}>
                        <AlertCircle size={24} />
                    </div>
                    <h3 className="text-xl font-bold text-slate-800">{title}</h3>
                </div>
                {isOpen ? <ChevronUp size={20} className="text-slate-400" /> : <ChevronDown size={20} className="text-slate-400" />}
            </button>
            {isOpen && <div className="p-6">{children}</div>}
        </div>
    );
};

const VictimRoutes = ({ onBack }) => (
    <div className="min-h-screen bg-slate-50 pb-20">
        <div className="bg-[#281FD0] text-white py-12 px-6">
            <div className="max-w-5xl mx-auto">
                <button
                    onClick={onBack}
                    className="flex items-center gap-2 text-white/70 hover:text-white mb-6 font-bold uppercase text-xs tracking-widest transition-colors"
                >
                    <Home size={16} /> Volver al inicio
                </button>
                <h1 className="text-3xl md:text-5xl font-black tracking-tighter mb-4">Rutas de atención a víctimas</h1>
                <p className="text-white/80 max-w-2xl font-medium">
                    Qué hacer y a quién llamar si usted o alguien cercano vive una situación de violencia. No tiene que enfrentarlo en soledad.
                </p>
            </div>
        </div>

        <div className="max-w-5xl mx-auto px-6 -mt-8">
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
                <div className="lg:col-span-2">
                    {ROUTES.map((route) => (
                        <RouteSection key={route.id} title={route.title} color={route.color}>
                            <ol className="space-y-4">
                                {route.steps.map((step, index) => (
                                    <li key={step.title} className="flex gap-4">
                                        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-[#281FD0] text-sm font-black text-white">{index + 1}</span>
                                        <div className="flex-1 rounded border border-slate-200 bg-white p-4">
                                            <div className="mb-1 flex flex-wrap items-center justify-between gap-2">
                                                <p className="font-bold text-slate-800">{step.title}</p>
                                                <span className="rounded bg-[#281FD0]/10 px-2 py-0.5 text-xs font-bold uppercase text-[#281FD0]">{step.agency}</span>
                                            </div>
                                            <p className="text-sm text-slate-600">{step.description}</p>
                                        </div>
                                    </li>
                                ))}
                            </ol>
                        </RouteSection>
                    ))}

                    <div className="bg-white p-6 rounded-2xl shadow-sm border border-slate-100">
                        <h3 className="text-lg font-bold text-slate-800 mb-2">Direcciones y horarios en Jamundí</h3>
                        <p className="text-sm text-slate-600 mb-4">
                            Para ubicar las Comisarías de Familia, la Personería y otras entidades del municipio, consulte los canales oficiales de la Alcaldía.
                        </p>
                        <a href="https://www.jamundi.gov.co" target="_blank" rel="noopener noreferrer"
                            className="inline-flex min-h-11 items-center gap-2 rounded-lg border border-slate-300 px-4 text-sm font-bold text-slate-700 hover:bg-slate-50">
                            Página oficial de la Alcaldía de Jamundí <ExternalLink size={16} />
                        </a>
                    </div>
                </div>

                <aside className="space-y-6">
                    <div className="bg-slate-900 text-white p-6 rounded-3xl shadow-xl">
                        <h3 className="text-lg font-black mb-5 uppercase tracking-tight">Líneas nacionales</h3>
                        <ul className="space-y-5">
                            {LINES.map((line) => (
                                <li key={line.number}>
                                    <a href={`tel:${line.number}`} className="flex items-start gap-4 rounded-xl p-1 hover:bg-white/5" aria-label={`Llamar a ${line.label}, ${line.number}`}>
                                        <span className="rounded-2xl bg-white/10 p-3"><line.icon size={20} className="text-white" /></span>
                                        <span>
                                            <span className="block text-[11px] font-bold uppercase tracking-widest text-white/60">{line.label}</span>
                                            <span className="block text-2xl font-black">{line.number}</span>
                                            <span className="block text-xs text-white/70">{line.detail}</span>
                                        </span>
                                    </a>
                                </li>
                            ))}
                        </ul>
                        <a
                            href="tel:123"
                            className="mt-6 flex w-full items-center justify-center gap-2 rounded-2xl bg-red-600 py-4 font-black text-white shadow-lg hover:bg-red-700"
                        >
                            <Phone size={20} /> Llamar al 123
                        </a>
                    </div>
                </aside>
            </div>
        </div>
    </div>
);

export default VictimRoutes;
