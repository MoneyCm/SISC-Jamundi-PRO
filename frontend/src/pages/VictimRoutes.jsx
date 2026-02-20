import React, { useState } from 'react';
import {
    Phone,
    MapPin,
    ShieldCheck,
    ArrowRight,
    Info,
    Home,
    Scale,
    HandHelping,
    AlertCircle,
    ChevronDown,
    ChevronUp
} from 'lucide-react';

const RouteSection = ({ title, icon: Icon, children, colorClass }) => {
    const [isOpen, setIsOpen] = useState(true);
    return (
        <div className="bg-white rounded-2xl shadow-sm border border-slate-100 overflow-hidden mb-6">
            <button
                onClick={() => setIsOpen(!isOpen)}
                className={`w-full flex items-center justify-between p-6 text-left transition-colors ${isOpen ? 'bg-slate-50' : 'hover:bg-slate-50'}`}
            >
                <div className="flex items-center gap-4">
                    <div className={`p-3 rounded-xl ${colorClass} text-white`}>
                        <Icon size={24} />
                    </div>
                    <h3 className="text-xl font-bold text-slate-800">{title}</h3>
                </div>
                {isOpen ? <ChevronUp size={20} className="text-slate-400" /> : <ChevronDown size={20} className="text-slate-400" />}
            </button>
            {isOpen && <div className="p-6">{children}</div>}
        </div>
    );
};

const VictimRoutes = ({ onBack }) => {
    const emergencyNumbers = [
        { label: 'Emergencias Nacional', number: '123', icon: Phone },
        { label: 'Línea Púrpura (Mujeres)', number: '155', icon: ShieldCheck },
        { label: 'Fiscalía General', number: '122', icon: Scale },
        { label: 'Policía Jamundí', number: '317 430 4577', icon: Phone },
    ];

    const routes = [
        {
            id: 'vbg',
            title: 'Violencia Basada en Género',
            steps: [
                { title: 'Atención Médica Inmediata', description: 'Acudir al Hospital Piloto o centro de salud más cercano. Tienes derecho a atención prioritaria y recolección de pruebas.', agency: 'Salud' },
                { title: 'Denuncia / Reporte', description: 'Dirigirse a la Fiscalía o Comisaría de Familia para solicitar medidas de protección.', agency: 'Justicia' },
                { title: 'Protección Física', description: 'Si tu vida corre peligro, solicita el traslado a una Casa de Refugio o medida de alejamiento inmediata.', agency: 'Seguridad' }
            ]
        },
        {
            id: 'infancia',
            title: 'Maltrato Infantil / Adolescencia',
            steps: [
                { title: 'Reporte ICBF', description: 'Llamar a la línea 141 o acudir al Centro Zonal del ICBF Jamundí.', agency: 'ICBF' },
                { title: 'Verificación de Derechos', description: 'La Defensoría de Familia iniciará el proceso de restablecimiento de derechos.', agency: 'Defensoría' }
            ]
        }
    ];

    return (
        <div className="min-h-screen bg-slate-50 pb-20">
            {/* Header */}
            <div className="bg-[#281FD0] text-white py-12 px-6">
                <div className="max-w-5xl mx-auto">
                    <button
                        onClick={onBack}
                        className="flex items-center gap-2 text-white/70 hover:text-white mb-6 font-bold uppercase text-xs tracking-widest transition-colors"
                    >
                        <Home size={16} /> Volver al Hub
                    </button>
                    <h1 className="text-3xl md:text-5xl font-black tracking-tighter mb-4">Rutas de Atención Integral</h1>
                    <p className="text-white/80 max-w-2xl font-medium">
                        Guía paso a paso sobre qué hacer y a dónde acudir. No estás sola, Jamundí te acompaña en cada paso de tu protección.
                    </p>
                </div>
            </div>

            {/* Content */}
            <div className="max-w-5xl mx-auto px-6 -mt-8">
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
                    {/* Main Routes */}
                    <div className="lg:col-span-2 space-y-6">
                        {routes.map(route => (
                            <RouteSection
                                key={route.id}
                                title={route.title}
                                icon={AlertCircle}
                                colorClass={route.id === 'vbg' ? 'bg-purple-600' : 'bg-blue-600'}
                            >
                                <div className="relative space-y-8 before:absolute before:inset-0 before:ml-5 before:-translate-x-px md:before:mx-auto md:before:translate-x-0 before:h-full before:w-0.5 before:bg-gradient-to-b before:from-transparent before:via-slate-200 before:to-transparent">
                                    {route.steps.map((step, idx) => (
                                        <div key={idx} className="relative flex items-center justify-between md:justify-normal md:odd:flex-row-reverse group is-active">
                                            <div className="flex items-center justify-center w-10 h-10 rounded-full border border-white bg-slate-100 group-[.is-active]:bg-primary group-[.is-active]:text-white text-slate-500 shadow shrink-0 md:order-1 md:group-odd:-translate-x-1/2 md:group-even:translate-x-1/2">
                                                {idx + 1}
                                            </div>
                                            <div className="w-[calc(100%-4rem)] md:w-[calc(50%-2.5rem)] p-4 rounded border border-slate-200 bg-white shadow">
                                                <div className="flex items-center justify-between space-x-2 mb-1">
                                                    <div className="font-bold text-slate-800">{step.title}</div>
                                                    <time className="font-caveat font-medium text-primary text-xs uppercase bg-primary/10 px-2 py-0.5 rounded">{step.agency}</time>
                                                </div>
                                                <div className="text-slate-500 text-sm">{step.description}</div>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            </RouteSection>
                        ))}

                        {/* Map or Locations static placeholder */}
                        <div className="bg-white p-8 rounded-2xl shadow-sm border border-slate-100">
                            <h3 className="text-xl font-bold text-slate-800 mb-6 flex items-center gap-2">
                                <MapPin size={24} className="text-primary" />
                                Puntos de Atención en Jamundí
                            </h3>
                            <div className="space-y-4">
                                <div className="flex items-start gap-4 p-4 border border-slate-50 rounded-xl hover:bg-slate-50 transition-colors">
                                    <div className="p-2 bg-primary/10 text-primary rounded-lg font-bold text-xs">A</div>
                                    <div>
                                        <p className="font-bold text-slate-800">Hospital Piloto Jamundí</p>
                                        <p className="text-sm text-slate-500">Calle 10 con Carrera 10. Atención 24/7 Urgencias.</p>
                                    </div>
                                </div>
                                <div className="flex items-start gap-4 p-4 border border-slate-50 rounded-xl hover:bg-slate-50 transition-colors">
                                    <div className="p-2 bg-primary/10 text-primary rounded-lg font-bold text-xs">B</div>
                                    <div>
                                        <p className="font-bold text-slate-800">Comisaría de Familia</p>
                                        <p className="text-sm text-slate-500">C.C. Caña Dulce, Local 92 (Cra 10 # 13-14). Lun - Vie: 8:00 AM - 12:00 M y 2:00 PM - 5:00 PM.</p>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>

                    {/* Sidebar: Emergency Contacts */}
                    <div className="space-y-6">
                        <div className="bg-slate-900 text-white p-8 rounded-3xl shadow-xl border border-slate-800">
                            <h3 className="text-xl font-black mb-6 uppercase tracking-tighter text-primary-400">Líneas de Vida</h3>
                            <div className="space-y-6">
                                {emergencyNumbers.map((item, idx) => (
                                    <div key={idx} className="flex items-center gap-4 group">
                                        <div className="p-3 bg-white/10 rounded-2xl group-hover:bg-primary transition-colors">
                                            <item.icon size={20} className="text-white" />
                                        </div>
                                        <div>
                                            <p className="text-[10px] uppercase font-bold text-white/40 tracking-widest">{item.label}</p>
                                            <p className="text-xl font-black tracking-tight">{item.number}</p>
                                        </div>
                                    </div>
                                ))}
                            </div>
                            <div className="mt-8 pt-8 border-t border-white/10">
                                <p className="text-sm text-white/60 italic mb-4">
                                    "Si estás en una situación de riesgo inminente, llama al 123 de inmediato."
                                </p>
                                <button className="w-full bg-red-600 hover:bg-red-700 text-white font-black py-4 rounded-2xl shadow-lg transition-all transform active:scale-95 flex items-center justify-center gap-2">
                                    <Phone size={20} /> BOTÓN DE PÁNICO
                                </button>
                            </div>
                        </div>

                        <div className="bg-primary/5 p-8 rounded-3xl border border-primary/10">
                            <div className="flex items-center gap-3 mb-4">
                                <div className="p-2 bg-primary/20 text-primary rounded-lg">
                                    <HandHelping size={20} />
                                </div>
                                <h4 className="font-bold text-slate-800">Soporte Psicosocial</h4>
                            </div>
                            <p className="text-sm text-slate-600 leading-relaxed">
                                Contamos con un equipo interdisciplinario que puede brindarte orientación emocional y jurídica de manera confidencial y gratuita.
                            </p>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default VictimRoutes;
