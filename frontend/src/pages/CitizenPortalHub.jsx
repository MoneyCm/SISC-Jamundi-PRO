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
    MessageCircle
} from 'lucide-react';

const CitizenPortalHub = ({ onNavigate, onLoginClick }) => {
    const services = [
        {
            id: 'reporting',
            title: 'Reporte Seguro',
            description: 'Canal encriptado para reportar delitos y comportamientos contrarios a la convivencia de forma anónima.',
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
            description: 'Visualiza el comportamiento delictivo en Jamundí mediante mapas y estadísticas en tiempo real.',
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
                <div className="max-w-6xl mx-auto relative z-10 text-center">
                    <div className="inline-flex items-center gap-2 bg-white/10 backdrop-blur-md px-4 py-2 rounded-full border border-white/20 mb-8 animate-fade-in">
                        <Globe size={16} className="text-white/80" />
                        <span className="text-xs font-bold uppercase tracking-widest text-white/90">Ventanilla Única Digital de Jamundí</span>
                    </div>
                    <h1 className="text-4xl md:text-6xl font-black mb-6 tracking-tighter leading-none">
                        SISC <span className="text-white/80">Ciudadano</span>
                    </h1>
                    <p className="text-lg md:text-xl text-white/80 max-w-2xl mx-auto font-medium mb-10">
                        Plataforma integral para la seguridad, transparencia y atención a víctimas.
                        Herramientas tecnológicas al servicio de la convivencia ciudadana.
                    </p>

                    <div className="flex flex-wrap justify-center gap-4">
                        <button
                            onClick={onLoginClick}
                            className="flex items-center gap-2 bg-white text-primary px-8 py-4 rounded-2xl font-black text-sm uppercase tracking-wider shadow-xl hover:bg-slate-50 transition-all hover:scale-105"
                        >
                            <Lock size={18} />
                            Ingreso Institucional
                        </button>
                    </div>
                </div>

                {/* Decorative Elements */}
                <div className="absolute top-0 left-0 w-full h-full opacity-10 pointer-events-none">
                    <div className="absolute top-[10%] left-[5%] w-64 h-64 bg-white rounded-full blur-3xl" />
                    <div className="absolute bottom-[10%] right-[10%] w-96 h-96 bg-primary-400 rounded-full blur-3xl" />
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
                            <h3 className="text-2xl font-bold text-slate-800 mb-3">{service.title}</h3>
                            <p className="text-slate-500 leading-relaxed mb-8 flex-1">{service.description}</p>
                            <div className={`inline-flex items-center gap-2 font-bold text-sm uppercase tracking-wider ${service.textColor}`}>
                                Acceder al Servicio
                                <ChevronRight size={18} className="group-hover:translate-x-1 transition-transform" />
                            </div>
                        </button>
                    ))}
                </div>
            </div>

            {/* Chatbot Floating Banner Placeholder */}
            <div className="fixed bottom-8 right-8 z-50">
                <div className="relative">
                    <div className="absolute -top-12 right-0 bg-white px-4 py-2 rounded-xl shadow-lg border border-slate-100 text-xs font-bold text-slate-700 animate-bounce whitespace-nowrap">
                        ¿Cómo puedo ayudarte hoy? 🤖
                    </div>
                    <button className="bg-primary hover:bg-primary-600 text-white p-5 rounded-full shadow-2xl transition-all transform hover:scale-110 active:scale-95 group">
                        <MessageCircle size={28} className="group-hover:rotate-12 transition-transform" />
                    </button>
                </div>
            </div>

            {/* Footer */}
            <footer className="mt-auto bg-slate-900 text-white py-16 px-6">
                <div className="max-w-6xl mx-auto grid grid-cols-1 md:grid-cols-3 gap-12">
                    <div className="space-y-6">
                        <div className="flex items-center gap-3">
                            <div className="bg-white p-2 rounded-lg">
                                <img src="/assets/escudo.png" alt="Escudo Jamundí" className="h-8 w-auto" />
                            </div>
                            <div>
                                <h4 className="font-black tracking-tighter text-xl">SISC <span className="text-white/50">Jamundí</span></h4>
                                <p className="text-[10px] uppercase font-bold text-white/40 tracking-widest">Alcaldía de Jamundí</p>
                            </div>
                        </div>
                        <p className="text-sm text-white/50 leading-relaxed">
                            Plataforma oficial del Sistema de Información para la Seguridad y Convivencia.
                            Operado por la Oficina del Observatorio del Delito.
                        </p>
                    </div>
                    <div>
                        <h5 className="font-bold mb-6 flex items-center gap-2">
                            <Eye size={18} className="text-primary-400" />
                            Transparencia
                        </h5>
                        <ul className="space-y-4 text-sm text-white/40">
                            <li><button className="hover:text-white transition-colors text-left uppercase text-xs font-black tracking-widest">Datos Abiertos</button></li>
                            <li><button className="hover:text-white transition-colors text-left uppercase text-xs font-black tracking-widest">Boletines Técnicos</button></li>
                            <li><button className="hover:text-white transition-colors text-left uppercase text-xs font-black tracking-widest">Rendición de Cuentas</button></li>
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
