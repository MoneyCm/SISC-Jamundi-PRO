import React, { useState, useEffect } from 'react';
import {
    Users,
    MessageCircle,
    Handshake,
    Home,
    Lightbulb,
    ChevronRight,
    MapPin,
    CalendarDays,
    Plus,
    X,
    CheckCircle2
} from 'lucide-react';
import { API_BASE_URL } from '../utils/apiConfig';

const CommunityParticipation = ({ onBack }) => {
    const [proposals, setProposals] = useState([]);
    const [loading, setLoading] = useState(true);
    const [showModal, setShowModal] = useState(false);
    const [formData, setFormData] = useState({
        title: '',
        description: '',
        category: 'ILUMINACIÓN',
        barrio: '',
        author_name: ''
    });
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [successMessage, setSuccessMessage] = useState(false);

    useEffect(() => {
        fetchProposals();
    }, []);

    const fetchProposals = async () => {
        try {
            const response = await fetch(`${API_BASE_URL}/participacion/propuestas`);
            if (response.ok) {
                const data = await response.json();
                setProposals(data);
            }
        } catch (err) {
            console.error("Error fetching proposals:", err);
        } finally {
            setLoading(false);
        }
    };

    const handleInviteClick = (title) => {
        if (title === 'Propuestas de Convivencia') {
            setShowModal(true);
        }
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        setIsSubmitting(true);
        try {
            const response = await fetch(`${API_BASE_URL}/participacion/propuestas`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(formData)
            });
            if (response.ok) {
                setSuccessMessage(true);
                setFormData({ title: '', description: '', category: 'ILUMINACIÓN', barrio: '', author_name: '' });
                fetchProposals();
                setTimeout(() => {
                    setSuccessMessage(false);
                    setShowModal(false);
                }, 3000);
            }
        } catch (err) {
            alert("Error al enviar la propuesta.");
        } finally {
            setIsSubmitting(false);
        }
    };

    const initiatives = [
        {
            title: 'Frentes de Seguridad Local',
            description: 'Organización de vecinos conectados para la prevención y alerta temprana en barrios.',
            icon: Handshake,
            members: '45 frentes activos',
            color: 'emerald'
        },
        {
            title: 'Propuestas de Convivencia',
            description: 'Envía tus ideas para mejorar la iluminación, parques o espacios comunes de tu sector.',
            icon: Lightbulb,
            members: `${proposals.length > 0 ? proposals.length : 12} proyectos en curso`,
            color: 'amber'
        },
        {
            title: 'Reporte de Riesgos Sociales',
            description: 'Informa sobre situaciones de vulnerabilidad o falta de cohesión social en tu comunidad.',
            icon: Users,
            members: 'Atención integral',
            color: 'blue'
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
                    <p className="text-white/80 max-max-w-2xl font-medium">
                        La seguridad se construye desde el barrio. Conéctate con tu JAC y participa en la transformación de Jamundí.
                    </p>
                </div>
            </div>

            <div className="max-w-5xl mx-auto px-6 -mt-8">
                <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-12">
                    {initiatives.map((item, idx) => (
                        <div
                            key={idx}
                            onClick={() => handleInviteClick(item.title)}
                            className={`bg-white p-6 rounded-3xl shadow-lg border border-slate-100 hover:shadow-xl transition-all group ${item.title === 'Propuestas de Convivencia' ? 'cursor-pointer hover:border-emerald-200' : ''}`}
                        >
                            <div className={`p-4 rounded-2xl w-fit mb-6 group-hover:scale-110 transition-transform ${item.color === 'emerald' ? 'bg-emerald-50 text-emerald-600' :
                                item.color === 'amber' ? 'bg-amber-50 text-amber-600' :
                                    'bg-blue-50 text-blue-600'
                                }`}>
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
                    {/* Proposal List Section */}
                    <div className="bg-white p-8 md:p-10 rounded-3xl shadow-xl border border-slate-100 h-fit">
                        <div className="flex justify-between items-center mb-6">
                            <h3 className="text-2xl font-black text-slate-800 tracking-tight">Proyectos en Curso</h3>
                            <button
                                onClick={() => setShowModal(true)}
                                className="bg-emerald-100 text-emerald-700 p-2 rounded-xl hover:bg-emerald-200 transition-colors"
                            >
                                <Plus size={20} />
                            </button>
                        </div>

                        <div className="space-y-4 max-h-[400px] overflow-y-auto pr-2 custom-scrollbar">
                            {proposals.length === 0 ? (
                                <div className="text-center py-10 text-slate-400">
                                    <p className="text-sm italic">No hay propuestas registradas aún.</p>
                                    <p className="text-xs">¡Sé el primero en proponer una mejora!</p>
                                </div>
                            ) : (
                                proposals.map((p) => (
                                    <div key={p.id} className="p-4 bg-slate-50 rounded-2xl border border-slate-100 hover:border-emerald-200 transition-colors">
                                        <div className="flex justify-between items-start mb-2">
                                            <span className="text-[10px] font-bold bg-emerald-100 text-emerald-700 px-2 py-0.5 rounded-full uppercase">{p.category}</span>
                                            <span className="text-[10px] text-slate-400">{new Date(p.created_at).toLocaleDateString()}</span>
                                        </div>
                                        <h4 className="font-bold text-slate-800 text-sm mb-1">{p.title}</h4>
                                        <p className="text-xs text-slate-500 mb-2 line-clamp-2">{p.description}</p>
                                        <div className="flex items-center gap-1 text-[10px] text-slate-400 font-medium">
                                            <MapPin size={10} /> {p.barrio}
                                        </div>
                                    </div>
                                ))
                            )}
                        </div>
                    </div>

                    {/* JAC Form Section - Restored */}
                    <div className="bg-white p-8 md:p-10 rounded-3xl shadow-xl border border-slate-100">
                        <h3 className="text-2xl font-black text-slate-800 mb-6 tracking-tight">Vínculo con tu JAC</h3>
                        <p className="text-slate-500 mb-8 text-sm">
                            ¿Eres líder de una Junta de Acción Comunal? Regístrate para recibir información estratégica del SISC y participar en las mesas de seguridad territorial.
                        </p>
                        <form className="space-y-4" onSubmit={(e) => { e.preventDefault(); alert("Solicitud de vínculo enviada. El equipo del SISC se pondrá en contacto pronto."); }}>
                            <input
                                required
                                type="text"
                                placeholder="Nombre del Líder / Representante"
                                className="w-full bg-slate-50 border-none rounded-xl px-4 py-3 text-sm focus:ring-2 focus:ring-emerald-500 h-12"
                            />
                            <input
                                required
                                type="text"
                                placeholder="Barrio / Vereda"
                                className="w-full bg-slate-50 border-none rounded-xl px-4 py-3 text-sm focus:ring-2 focus:ring-emerald-500 h-12"
                            />
                            <textarea
                                required
                                placeholder="Describa brevemente su requerimiento o propuesta..."
                                rows={4}
                                className="w-full bg-slate-50 border-none rounded-xl px-4 py-3 text-sm focus:ring-2 focus:ring-emerald-500"
                            ></textarea>
                            <button type="submit" className="w-full bg-emerald-600 text-white font-black py-4 rounded-xl hover:bg-emerald-700 transition-all shadow-lg active:scale-95">
                                ENVIAR SOLICITUD DE VÍNCULO
                            </button>
                        </form>
                    </div>

                    {/* Events Section moved lower */}
                    <div className="bg-slate-900 text-white p-8 rounded-3xl shadow-xl lg:col-span-1">
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

                    <div className="bg-white p-8 rounded-3xl border border-slate-100 shadow-sm lg:col-span-1">
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

            {/* Modal for new proposal */}
            {showModal && (
                <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm z-50 flex items-center justify-center p-6">
                    <div className="bg-white w-full max-w-lg rounded-3xl shadow-2xl overflow-hidden animate-in fade-in zoom-in duration-200">
                        <div className="p-6 bg-emerald-600 text-white flex justify-between items-center">
                            <h3 className="text-xl font-bold">Nueva Propuesta de Convivencia</h3>
                            <button onClick={() => setShowModal(false)} className="p-2 hover:bg-white/10 rounded-full transition-colors">
                                <X size={20} />
                            </button>
                        </div>

                        {successMessage ? (
                            <div className="p-12 text-center space-y-4">
                                <div className="bg-emerald-100 text-emerald-600 p-4 rounded-full w-fit mx-auto">
                                    <CheckCircle2 size={48} />
                                </div>
                                <h4 className="text-2xl font-bold text-slate-800">¡Propuesta Enviada!</h4>
                                <p className="text-slate-500">Gracias por ayudar a transformar Jamundí. Tu idea será revisada por el equipo del SISC.</p>
                            </div>
                        ) : (
                            <form onSubmit={handleSubmit} className="p-8 space-y-4">
                                <div className="space-y-1">
                                    <label className="text-[10px] font-black uppercase text-slate-400 tracking-widest pl-1">Título de la Idea</label>
                                    <input
                                        required
                                        type="text"
                                        placeholder="Ej: Mejora de iluminación en el Parque Principal"
                                        className="w-full bg-slate-50 border-none rounded-xl px-4 py-3 text-sm focus:ring-2 focus:ring-emerald-500 h-12"
                                        value={formData.title}
                                        onChange={(e) => setFormData({ ...formData, title: e.target.value })}
                                    />
                                </div>

                                <div className="grid grid-cols-2 gap-4">
                                    <div className="space-y-1">
                                        <label className="text-[10px] font-black uppercase text-slate-400 tracking-widest pl-1">Categoría</label>
                                        <select
                                            className="w-full bg-slate-50 border-none rounded-xl px-4 py-3 text-sm focus:ring-2 focus:ring-emerald-500 h-12"
                                            value={formData.category}
                                            onChange={(e) => setFormData({ ...formData, category: e.target.value })}
                                        >
                                            <option value="ILUMINACIÓN">Iluminación</option>
                                            <option value="PARQUES">Parques</option>
                                            <option value="ESPACIOS_COMUNES">Espacios Comunes</option>
                                            <option value="OTROS">Otros</option>
                                        </select>
                                    </div>
                                    <div className="space-y-1">
                                        <label className="text-[10px] font-black uppercase text-slate-400 tracking-widest pl-1">Barrio</label>
                                        <input
                                            required
                                            type="text"
                                            placeholder="Tu barrio"
                                            className="w-full bg-slate-50 border-none rounded-xl px-4 py-3 text-sm focus:ring-2 focus:ring-emerald-500 h-12"
                                            value={formData.barrio}
                                            onChange={(e) => setFormData({ ...formData, barrio: e.target.value })}
                                        />
                                    </div>
                                </div>

                                <div className="space-y-1">
                                    <label className="text-[10px] font-black uppercase text-slate-400 tracking-widest pl-1">Descripción</label>
                                    <textarea
                                        required
                                        placeholder="Describe tu propuesta detalladamente..."
                                        rows={4}
                                        className="w-full bg-slate-50 border-none rounded-xl px-4 py-3 text-sm focus:ring-2 focus:ring-emerald-500"
                                        value={formData.description}
                                        onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                                    ></textarea>
                                </div>

                                <button
                                    disabled={isSubmitting}
                                    type="submit"
                                    className="w-full bg-emerald-600 text-white font-black py-4 rounded-xl hover:bg-emerald-700 transition-all shadow-lg active:scale-95 disabled:opacity-50 mt-4"
                                >
                                    {isSubmitting ? 'ENVIANDO...' : 'PUBLICAR PROPUESTA'}
                                </button>
                            </form>
                        )}
                    </div>
                </div>
            )}
        </div>
    );
};

export default CommunityParticipation;
