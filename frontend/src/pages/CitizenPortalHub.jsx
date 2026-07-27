import React from 'react';
import {
    ShieldAlert,
    BarChart3,
    Users,
    MessageSquare,
    ChevronRight,
    Globe,
    Lock,
    HeartPulse,
    Eye,
    MessageCircle,
    BellRing,
    PhoneCall
} from 'lucide-react';

const CitizenPortalHub = ({ onNavigate, onLoginClick }) => {
    const services = [
        {
            id: 'reporting',
            title: 'Reporte Seguro',
            description: 'Canal institucional para reportar delitos y riesgos de forma anónima o con datos de contacto.',
            icon: ShieldAlert,
            color: 'bg-red-500',
            bg: 'bg-red-50',
            textColor: 'text-red-700',
            tag: 'Prioritario'
        },
        {
            id: 'victim-support',
            title: 'Rutas de Atención',
            description: 'Guía interactiva sobre qué hacer y a qué entidades acudir en casos de violencia o maltrato.',
            icon: HeartPulse,
            color: 'bg-purple-500',
            bg: 'bg-purple-50',
            textColor: 'text-purple-700',
            tag: 'Apoyo Integral'
        },
        {
            id: 'transparency',
            title: 'Transparencia de Datos',
            description: 'Consulta el comportamiento delictivo con fuentes, periodos y fechas de corte visibles.',
            icon: BarChart3,
            color: 'bg-primary-600',
            bg: 'bg-primary-50',
            textColor: 'text-primary-700',
            tag: 'Datos Abiertos'
        },
        {
            id: 'participation',
            title: 'Participación Ciudadana',
            description: 'Espacio para JAC y ciudadanos para reportar riesgos y colaborar en la seguridad comunitaria.',
            icon: Users,
            color: 'bg-emerald-500',
            bg: 'bg-emerald-50',
            textColor: 'text-emerald-700',
            tag: 'Comunidad'
        },
    ];

    return (
        <div className="min-h-screen bg-slate-50 flex flex-col">
            {/* Hero Section */}
            <div className="bg-gradient-to-br from-[#281FD0] via-[#384CF5] to-indigo-800 text-white py-16 md:py-24 px-6 relative overflow-hidden">
                {/* Orla Institucional Superior */}
                <div className="absolute top-0 left-0 orla-hidirica"></div>

                <div className="max-w-6xl mx-auto relative z-10 text-center">
                    <button
                        onClick={() => onNavigate('pqr')}
                        className="inline-flex items-center gap-2 bg-white/10 backdrop-blur-md px-4 py-2 rounded-full border border-white/20 mb-8 animate-fade-in hover:bg-white/20 transition-colors cursor-pointer"
                    >
                        <Globe size={16} className="text-white/80" />
                        <span className="text-[10px] font-black uppercase tracking-widest text-white/90">Abrir Ventanilla Única (PQR)</span>
                    </button>
                    <h1 className="text-5xl md:text-7xl font-black mb-6 tracking-tighter leading-none font-titles">
                        SISC <span className="text-white uppercase">JAMUNDÍ</span>
                    </h1>
                    <p className="text-xl md:text-2xl text-white/80 max-w-3xl mx-auto font-medium mb-10 leading-relaxed">
                        Sistema de Información para la Seguridad y Convivencia de la <span className="text-white font-bold uppercase">ALCALDÍA DE JAMUNDÍ</span>.
                    </p>

                    <div className="flex flex-wrap justify-center gap-4">
                        <a
                            href="tel:123"
                            className="flex items-center gap-2 bg-red-600 text-white px-8 py-4 rounded-2xl font-black text-sm uppercase tracking-wider shadow-xl hover:bg-red-700 transition-colors"
                        >
                            <PhoneCall size={18} />
                            Emergencias 123
                        </a>
                        <button
                            onClick={onLoginClick}
                            className="flex items-center gap-2 bg-white text-primary px-8 py-4 rounded-2xl font-black text-sm uppercase tracking-wider shadow-xl shadow-primary/20 hover:opacity-90 transition-all hover:scale-105 cursor-pointer"
                        >
                            <Lock size={18} />
                            Ingreso Institucional
                        </button>
                    </div>
                </div>

                {/* Decorative Elements */}
                <div className="absolute top-0 right-0 w-1/4 h-full opacity-[0.03] pointer-events-none">
                    <img src="/assets/escudo.png" alt="" className="w-full h-full object-contain translate-x-10 translate-y-10" />
                </div>
            </div>

            {/* Services Grid */}
            <div className="max-w-6xl mx-auto px-6 -mt-12 mb-20 relative z-20">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    {services.map((service) => (
                        <button
                            key={service.id}
                            onClick={() => onNavigate(service.id)}
                            className="bg-white p-8 rounded-3xl shadow-xl border border-slate-100 hover:shadow-2xl hover:border-primary-100 transition-all group text-left flex flex-col h-full"
                        >
                            <div className="flex justify-between items-start mb-6">
                                <div className={`p-4 rounded-2xl ${service.bg} ${service.textColor} group-hover:scale-110 transition-transform`}>
                                    <service.icon size={32} />
                                </div>
                                <span className={`text-[10px] font-black uppercase tracking-[0.2em] px-3 py-1.5 rounded-full ${service.bg} ${service.textColor}`}>
                                    {service.tag}
                                </span>
                            </div>
                            <h3 className="text-2xl font-black text-slate-800 mb-3 font-titles">{service.title}</h3>
                            <p className="text-slate-500 leading-relaxed mb-8 flex-1 font-medium">{service.description}</p>
                            <div className={`inline-flex items-center gap-2 font-black text-xs uppercase tracking-wider ${service.textColor}`}>
                                Acceder al Servicio
                                <ChevronRight size={18} className="group-hover:translate-x-1 transition-transform" />
                            </div>
                        </button>
                    ))}
                </div>
            </div>

            {/* El chatbot real se renderiza globalmente en App.jsx */}

            {/* Footer */}
            <footer className="mt-auto bg-slate-900 text-white py-16 px-6">
                <div className="max-w-6xl mx-auto grid grid-cols-1 md:grid-cols-3 gap-12">
                    <div className="space-y-6">
                        <div className="flex items-center gap-3">
                            <div className="bg-white p-2 rounded-lg">
                                <img src="/assets/escudo.png" alt="Escudo Jamundí" className="h-10 w-auto" />
                            </div>
                            <div>
                                <h4 className="font-black tracking-tighter text-2xl font-titles">SISC</h4>
                                <p className="text-[10px] uppercase font-bold text-white/40 tracking-widest leading-none">ALCALDÍA DE JAMUNDÍ</p>
                            </div>
                        </div>
                        <p className="text-sm text-white/50 leading-relaxed font-medium">
                            Plataforma oficial del Sistema de Información para la Seguridad y Convivencia.
                            Operado por la Oficina del Observatorio del Delito de la <span className="text-white font-bold uppercase">ALCALDÍA DE JAMUNDÍ</span>.
                        </p>
                    </div>
                    <div>
                        <button onClick={() => onNavigate('transparency-info')} className="font-bold mb-6 flex items-center gap-2 hover:text-primary-300">
                            <Eye size={18} className="text-primary-400" />
                            Transparencia
                        </button>
                        <ul className="space-y-4 text-sm text-white/40">
                            <li><button onClick={() => onNavigate('open-data')} className="hover:text-white transition-colors text-left uppercase text-xs font-black tracking-widest">Datos Abiertos</button></li>
                            <li><button onClick={() => onNavigate('technical-bulletins')} className="hover:text-white transition-colors text-left uppercase text-xs font-black tracking-widest">Boletines Técnicos</button></li>
                            <li><button onClick={() => onNavigate('accountability')} className="hover:text-white transition-colors text-left uppercase text-xs font-black tracking-widest">Rendición de Cuentas</button></li>
                        </ul>
                    </div>
                    <div>
                        <h5 className="font-bold mb-6 flex items-center gap-2">
                            <MessageSquare size={18} className="text-primary-400" />
                            Contacto de Emergencia
                        </h5>
                        <div className="bg-white/5 p-4 rounded-xl border border-white/10">
                            <p className="text-[10px] uppercase font-bold text-primary-400 mb-1">Línea Unificada</p>
                            <p className="text-2xl font-black">123</p>
                            <div className="mt-4 pt-4 border-t border-white/10">
                                <p className="text-[10px] uppercase font-bold text-white/40 mb-1">Centro de Mando Jamundí</p>
                                <p className="text-sm font-bold">(602) 519 22 22</p>
                            </div>
                        </div>
                    </div>
                </div>
                <div className="max-w-6xl mx-auto pt-16 mt-16 border-t border-white/5 text-center text-[10px] font-bold uppercase tracking-[0.3em] text-white/20">
                    © 2026 Alcaldía de Jamundí | Oficina del Observatorio
                </div>
            </footer>
        </div>
    );
};

export default CitizenPortalHub;
