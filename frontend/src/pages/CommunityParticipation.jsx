import React from 'react';
import {
    Users,
    MessageCircle,
    Handshake,
    Home,
    Lightbulb,
    ChevronRight,
    MapPin,
    CalendarDays
} from 'lucide-react';

const CommunityParticipation = ({ onBack }) => {
    const initiatives = [
        {
            title: 'Frentes de Seguridad Local',
            description: 'Organización de vecinos conectados para la prevención y alerta temprana en barrios.',
            icon: Handshake,
            members: '45 frentes activos'
        },
        {
            title: 'Propuestas de Convivencia',
            description: 'Envía tus ideas para mejorar la iluminación, parques o espacios comunes de tu sector.',
            icon: Lightbulb,
            members: '12 proyectos en curso'
        },
        {
            title: 'Reporte de Riesgos Sociales',
            description: 'Informa sobre situaciones de vulnerabilidad o falta de cohesión social en tu comunidad.',
            icon: Users,
            members: 'Atención integral'
        }
    ];

    return (
        <div className="min-h-screen bg-slate-50 pb-20">
            {/* Header */}
            <div className="bg-[#10b981] text-white py-12 px-6">
                <div className="max-w-5xl mx-auto">
                    <button
                        onClick={onBack}
                        className="flex items-center gap-2 text-white/70 hover:text-white mb-6 font-bold uppercase text-xs tracking-widest transition-colors"
                    >
                        <Home size={16} /> Volver al Hub
                    </button>
                    <div className="flex items-center gap-4 mb-4">
                        <div className="p-3 bg-white/20 rounded-2xl">
                            <Users size={32} />
                        </div>
                        <h1 className="text-3xl md:text-5xl font-black tracking-tighter">Participación Ciudadana</h1>
                    </div>
                    <p className="text-white/80 max-w-2xl font-medium">
                        La seguridad se construye desde el barrio. Conéctate con tu JAC y participa en la transformación de Jamundí.
                    </p>
                </div>
            </div>

            <div className="max-w-5xl mx-auto px-6 -mt-8">
                <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-12">
                    {initiatives.map((item, idx) => (
                        <div key={idx} className="bg-white p-6 rounded-3xl shadow-lg border border-slate-100 hover:shadow-xl transition-all group">
                            <div className="bg-emerald-50 text-emerald-600 p-4 rounded-2xl w-fit mb-6 group-hover:scale-110 transition-transform">
                                <item.icon size={24} />
                            </div>
                            <h3 className="text-lg font-bold text-slate-800 mb-2">{item.title}</h3>
                            <p className="text-sm text-slate-500 mb-6 leading-relaxed">{item.description}</p>
                            <div className="flex items-center justify-between pt-4 border-t border-slate-50">
                                <span className="text-[10px] font-black uppercase tracking-widest text-emerald-600">{item.members}</span>
                                <ChevronRight size={16} className="text-slate-300" />
                            </div>
                        </div>
                    ))}
                </div>

                <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
                    {/* JAC Form Section */}
                    <div className="bg-white p-8 md:p-10 rounded-3xl shadow-xl border border-slate-100">
                        <h3 className="text-2xl font-black text-slate-800 mb-6 tracking-tight">Vínculo con tu JAC</h3>
                        <p className="text-slate-500 mb-8 text-sm">
                            ¿Eres líder de una Junta de Acción Comunal? Regístrate para recibir información estratégica del SISC y participar en las mesas de seguridad territorial.
                        </p>
                        <form className="space-y-4">
                            <input
                                type="text"
                                placeholder="Nombre del Líder / Representante"
                                className="w-full bg-slate-50 border-none rounded-xl px-4 py-3 text-sm focus:ring-2 focus:ring-emerald-500 h-12"
                            />
                            <input
                                type="text"
                                placeholder="Barrio / Vereda"
                                className="w-full bg-slate-50 border-none rounded-xl px-4 py-3 text-sm focus:ring-2 focus:ring-emerald-500 h-12"
                            />
                            <textarea
                                placeholder="Describa brevemente su requerimiento o propuesta..."
                                rows={4}
                                className="w-full bg-slate-50 border-none rounded-xl px-4 py-3 text-sm focus:ring-2 focus:ring-emerald-500"
                            ></textarea>
                            <button className="w-full bg-emerald-600 text-white font-black py-4 rounded-xl hover:bg-emerald-700 transition-all shadow-lg active:scale-95">
                                ENVIAR SOLICITUD DE VÍNCULO
                            </button>
                        </form>
                    </div>

                    {/* Events / News */}
                    <div className="space-y-6">
                        <div className="bg-slate-900 text-white p-8 rounded-3xl shadow-xl">
                            <h3 className="text-xl font-bold mb-6 flex items-center gap-2">
                                <CalendarDays size={20} className="text-emerald-400" />
                                Agenda Comunitaria
                            </h3>
                            <div className="space-y-6">
                                <div className="border-l-2 border-emerald-500 pl-4 py-1">
                                    <p className="text-xs font-bold text-emerald-400">25 FEB | 6:00 PM</p>
                                    <p className="text-sm font-bold">Mesa de Seguridad - Comuna 1</p>
                                    <p className="text-[10px] text-white/40">Lugar: Casa de la Cultura</p>
                                </div>
                                <div className="border-l-2 border-slate-700 pl-4 py-1">
                                    <p className="text-xs font-bold text-slate-500">02 MAR | 5:30 PM</p>
                                    <p className="text-sm font-bold">Capacitación Prevención VBG</p>
                                    <p className="text-[10px] text-white/40">Lugar: Virtual (Meet)</p>
                                </div>
                            </div>
                        </div>

                        <div className="bg-white p-8 rounded-3xl border border-slate-100 shadow-sm">
                            <h4 className="font-bold text-slate-800 mb-4 flex items-center gap-2">
                                <MessageCircle size={18} className="text-emerald-600" />
                                ¿Por qué participar?
                            </h4>
                            <ul className="text-sm text-slate-500 space-y-3">
                                <li className="flex items-center gap-2">
                                    <div className="w-1 h-1 bg-emerald-500 rounded-full"></div>
                                    Incidencia real en las políticas de seguridad.
                                </li>
                                <li className="flex items-center gap-2">
                                    <div className="w-1 h-1 bg-emerald-500 rounded-full"></div>
                                    Acceso a reportes preventivos de tu sector.
                                </li>
                                <li className="flex items-center gap-2">
                                    <div className="w-1 h-1 bg-emerald-500 rounded-full"></div>
                                    Fortalecimiento del tejido social de Jamundí.
                                </li>
                            </ul>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default CommunityParticipation;
