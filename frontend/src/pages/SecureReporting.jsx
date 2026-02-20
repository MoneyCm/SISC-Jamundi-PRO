import React, { useState } from 'react';
import {
    ShieldAlert,
    Send,
    User,
    MapPin,
    Calendar,
    Clock,
    FileText,
    CheckCircle,
    Home,
    EyeOff,
    AlertTriangle,
    ArrowRight,
    ArrowLeft
} from 'lucide-react';
import { API_BASE_URL } from '../utils/apiConfig';

const StepIndicator = ({ currentStep }) => (
    <div className="flex items-center justify-center space-x-4 mb-10">
        {[1, 2, 3].map((step) => (
            <div key={step} className="flex items-center">
                <div className={`w-10 h-10 rounded-full flex items-center justify-center font-bold transition-all ${currentStep >= step ? 'bg-primary text-white shadow-lg' : 'bg-slate-200 text-slate-500'
                    }`}>
                    {step}
                </div>
                {step < 3 && (
                    <div className={`w-12 h-1 bg-slate-200 ml-4 ${currentStep > step ? 'bg-primary' : ''}`} />
                )}
            </div>
        ))}
    </div>
);

const SecureReporting = ({ onBack }) => {
    const [step, setStep] = useState(1);
    const [loading, setLoading] = useState(false);
    const [submitted, setSubmitted] = useState(false);
    const [formData, setFormData] = useState({
        tipo: 'HURTO A PERSONAS',
        subtipo: '',
        fecha: new Date().toISOString().split('T')[0],
        hora: '12:00',
        barrio: '',
        descripcion: '',
        es_anonimo: true,
        nombre: '',
        contacto: '',
        autoriza_datos: false
    });

    const handleChange = (e) => {
        const { name, value, type, checked } = e.target;
        setFormData(prev => ({
            ...prev,
            [name]: type === 'checkbox' ? checked : value
        }));
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        setLoading(true);
        try {
            const token = localStorage.getItem('token');
            const headers = {
                'Content-Type': 'application/json',
                ...(token ? { 'Authorization': `Bearer ${token}` } : {})
            };

            const response = await fetch(`${API_BASE_URL}/participacion/reportes-seguros`, {
                method: 'POST',
                headers,
                body: JSON.stringify(formData)
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || "Error al enviar el reporte");
            }

            setSubmitted(true);
        } catch (err) {
            console.error("Error submitting report:", err);
            alert(`Error: ${err.message}`);
        } finally {
            setLoading(false);
        }
    };

    if (submitted) {
        return (
            <div className="min-h-screen bg-slate-50 flex flex-col items-center justify-center p-6 text-center">
                <div className="bg-white p-10 rounded-3xl shadow-xl max-w-md w-full border border-slate-100">
                    <div className="bg-emerald-100 text-emerald-600 w-20 h-20 rounded-full flex items-center justify-center mx-auto mb-6">
                        <CheckCircle size={48} />
                    </div>
                    <h2 className="text-3xl font-black text-slate-800 mb-4 tracking-tighter">¡Reporte Enviado!</h2>
                    <p className="text-slate-500 mb-8 leading-relaxed">
                        Tu información ha sido recibida con éxito por el SISC Jamundí. Nuestro equipo técnico analizará estos datos para fortalecer la seguridad de tu sector.
                    </p>
                    <div className="bg-slate-50 p-4 rounded-xl mb-8 text-xs font-mono text-slate-600 border border-slate-100">
                        ID DE RADICADO: {Math.random().toString(36).substring(2, 10).toUpperCase()}
                    </div>
                    <button
                        onClick={onBack}
                        className="w-full bg-primary text-white font-black py-4 rounded-2xl hover:bg-primary-600 transition-all flex items-center justify-center gap-2"
                    >
                        <Home size={18} /> Volver al Inicio
                    </button>
                </div>
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-slate-50 pb-20">
            {/* Header */}
            <div className="bg-[#281FD0] text-white py-12 px-6">
                <div className="max-w-4xl mx-auto">
                    <button
                        onClick={onBack}
                        className="flex items-center gap-2 text-white/70 hover:text-white mb-6 font-bold uppercase text-xs tracking-widest transition-colors"
                    >
                        <Home size={16} /> Volver al Hub
                    </button>
                    <div className="flex items-center gap-4 mb-4">
                        <div className="p-3 bg-red-500 rounded-2xl shadow-lg">
                            <ShieldAlert size={32} />
                        </div>
                        <h1 className="text-3xl md:text-5xl font-black tracking-tighter">Reporte Seguro</h1>
                    </div>
                    <p className="text-white/80 max-w-2xl font-medium">
                        Tu aporte es fundamental para mapear el delito y salvar vidas. Este canal garantiza el anonimato si así lo prefieres.
                    </p>
                </div>
            </div>

            <div className="max-w-4xl mx-auto px-6 -mt-10">
                <div className="bg-white rounded-3xl shadow-xl border border-slate-100 overflow-hidden">
                    <div className="p-8 md:p-12">
                        <StepIndicator currentStep={step} />

                        <form onSubmit={handleSubmit}>
                            {step === 1 && (
                                <div className="space-y-6 animate-fade-in">
                                    <h3 className="text-xl font-bold text-slate-800 mb-6 flex items-center gap-2">
                                        <AlertTriangle size={24} className="text-amber-500" />
                                        Información del Suceso
                                    </h3>
                                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                                        <div className="space-y-2">
                                            <label className="text-xs font-black uppercase tracking-widest text-slate-400">Tipo de Incidente</label>
                                            <select
                                                name="tipo"
                                                value={formData.tipo}
                                                onChange={handleChange}
                                                className="w-full bg-slate-50 border-none rounded-xl px-4 py-3 text-sm focus:ring-2 focus:ring-primary h-12"
                                            >
                                                <option>HURTO A PERSONAS</option>
                                                <option>VIOLENCIA INTRAFAMILIAR</option>
                                                <option>LESIONES PERSONALES</option>
                                                <option>ACTIVIDAD SOSPECHOSA</option>
                                                <option>OTROS</option>
                                            </select>
                                        </div>
                                        <div className="space-y-2">
                                            <label className="text-xs font-black uppercase tracking-widest text-slate-400">Barrio / Sector</label>
                                            <input
                                                type="text"
                                                name="barrio"
                                                value={formData.barrio}
                                                onChange={handleChange}
                                                placeholder="Ej: Barrio Central"
                                                className="w-full bg-slate-50 border-none rounded-xl px-4 py-3 text-sm focus:ring-2 focus:ring-primary h-12"
                                                required
                                            />
                                        </div>
                                        <div className="space-y-2">
                                            <label className="text-xs font-black uppercase tracking-widest text-slate-400">Fecha</label>
                                            <div className="relative">
                                                <Calendar size={18} className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400" />
                                                <input
                                                    type="date"
                                                    name="fecha"
                                                    value={formData.fecha}
                                                    onChange={handleChange}
                                                    className="w-full bg-slate-50 border-none rounded-xl pl-12 pr-4 py-3 text-sm focus:ring-2 focus:ring-primary h-12"
                                                />
                                            </div>
                                        </div>
                                        <div className="space-y-2">
                                            <label className="text-xs font-black uppercase tracking-widest text-slate-400">Hora Aproximada</label>
                                            <div className="relative">
                                                <Clock size={18} className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400" />
                                                <input
                                                    type="time"
                                                    name="hora"
                                                    value={formData.hora}
                                                    onChange={handleChange}
                                                    className="w-full bg-slate-50 border-none rounded-xl pl-12 pr-4 py-3 text-sm focus:ring-2 focus:ring-primary h-12"
                                                />
                                            </div>
                                        </div>
                                    </div>
                                    <div className="flex justify-end">
                                        <button
                                            type="button"
                                            onClick={() => setStep(2)}
                                            className="bg-primary text-white font-black px-8 py-4 rounded-2xl flex items-center gap-2 hover:bg-primary-600 transition-all shadow-lg"
                                        >
                                            Siguiente Paso <ArrowRight size={18} />
                                        </button>
                                    </div>
                                </div>
                            )}

                            {step === 2 && (
                                <div className="space-y-6 animate-fade-in">
                                    <h3 className="text-xl font-bold text-slate-800 mb-6 flex items-center gap-2">
                                        <FileText size={24} className="text-primary" />
                                        Relato de los Hechos
                                    </h3>
                                    <div className="space-y-2">
                                        <label className="text-xs font-black uppercase tracking-widest text-slate-400">Descripción Detallada</label>
                                        <textarea
                                            name="descripcion"
                                            value={formData.descripcion}
                                            onChange={handleChange}
                                            rows={6}
                                            placeholder="Por favor, describe lo sucedido con la mayor precisión posible. No compartas nombres de víctimas aquí si prefieres el anonimato total."
                                            className="w-full bg-slate-50 border-none rounded-2xl px-6 py-4 text-sm focus:ring-2 focus:ring-primary ring-inset shadow-inner"
                                            required
                                        ></textarea>
                                    </div>
                                    <div className="p-4 bg-primary/5 rounded-2xl border border-primary/10 flex gap-4">
                                        <EyeOff size={24} className="text-primary shrink-0" />
                                        <p className="text-xs text-primary-900 leading-relaxed font-medium">
                                            <strong>Nota de Privacidad:</strong> Tu descripción será utilizada solo para fines de inteligencia de seguridad y no será publicada en el portal de transparencia de forma literal.
                                        </p>
                                    </div>
                                    <div className="flex justify-between">
                                        <button
                                            type="button"
                                            onClick={() => setStep(1)}
                                            className="bg-slate-100 text-slate-500 font-black px-8 py-4 rounded-2xl flex items-center gap-2 hover:bg-slate-200 transition-all"
                                        >
                                            <ArrowLeft size={18} /> Anterior
                                        </button>
                                        <button
                                            type="button"
                                            onClick={() => setStep(3)}
                                            className="bg-primary text-white font-black px-8 py-4 rounded-2xl flex items-center gap-2 hover:bg-primary-600 transition-all shadow-lg"
                                        >
                                            Siguiente Paso <ArrowRight size={18} />
                                        </button>
                                    </div>
                                </div>
                            )}

                            {step === 3 && (
                                <div className="space-y-6 animate-fade-in">
                                    <h3 className="text-xl font-bold text-slate-800 mb-6 flex items-center gap-2">
                                        <User size={24} className="text-emerald-500" />
                                        Información de Contacto
                                    </h3>
                                    <div className="bg-slate-50 p-6 rounded-3xl border border-slate-100 mb-6">
                                        <div className="flex items-center justify-between mb-6">
                                            <span className="font-bold text-slate-700">Deseo reportar de forma ANÓNIMA</span>
                                            <label className="relative inline-flex items-center cursor-pointer">
                                                <input
                                                    type="checkbox"
                                                    name="es_anonimo"
                                                    checked={formData.es_anonimo}
                                                    onChange={handleChange}
                                                    className="sr-only peer"
                                                />
                                                <div className="w-11 h-6 bg-slate-200 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-primary"></div>
                                            </label>
                                        </div>

                                        {!formData.es_anonimo && (
                                            <div className="grid grid-cols-1 md:grid-cols-2 gap-6 animate-fade-in">
                                                <div className="space-y-2">
                                                    <label className="text-[10px] font-black uppercase tracking-widest text-slate-400">Nombre Completo</label>
                                                    <input
                                                        type="text"
                                                        name="nombre"
                                                        value={formData.nombre}
                                                        onChange={handleChange}
                                                        className="w-full bg-white border border-slate-200 rounded-xl px-4 py-3 text-sm focus:ring-2 focus:ring-primary h-12"
                                                    />
                                                </div>
                                                <div className="space-y-2">
                                                    <label className="text-[10px] font-black uppercase tracking-widest text-slate-400">Teléfono / Email</label>
                                                    <input
                                                        type="text"
                                                        name="contacto"
                                                        value={formData.contacto}
                                                        onChange={handleChange}
                                                        className="w-full bg-white border border-slate-200 rounded-xl px-4 py-3 text-sm focus:ring-2 focus:ring-primary h-12"
                                                    />
                                                </div>
                                            </div>
                                        )}
                                    </div>

                                    <div className="flex items-center gap-3">
                                        <input
                                            type="checkbox"
                                            id="terms"
                                            name="autoriza_datos"
                                            checked={formData.autoriza_datos}
                                            onChange={handleChange}
                                            className="w-5 h-5 rounded border-slate-300 text-primary focus:ring-primary"
                                            required
                                        />
                                        <label htmlFor="terms" className="text-sm text-slate-500 leading-tight">
                                            Declaro que la información proporcionada es veraz y autorizo su tratamiento estadístico bajo la ley de protección de datos personales.
                                        </label>
                                    </div>

                                    <div className="flex justify-between pt-6 border-t border-slate-100">
                                        <button
                                            type="button"
                                            onClick={() => setStep(2)}
                                            className="bg-slate-100 text-slate-500 font-black px-8 py-4 rounded-2xl flex items-center gap-2 hover:bg-slate-200 transition-all"
                                        >
                                            <ArrowLeft size={18} /> Anterior
                                        </button>
                                        <button
                                            type="submit"
                                            disabled={loading || !formData.autoriza_datos}
                                            className="bg-emerald-600 text-white font-black px-12 py-4 rounded-2xl flex items-center gap-2 hover:bg-emerald-700 transition-all shadow-xl disabled:opacity-50 disabled:cursor-not-allowed group"
                                        >
                                            {loading ? 'Procesando...' : (
                                                <>
                                                    Enviar Reporte Seguro <Send size={18} className="group-hover:translate-x-1 group-hover:-translate-y-1 transition-transform" />
                                                </>
                                            )}
                                        </button>
                                    </div>
                                </div>
                            )}
                        </form>
                    </div>
                    {/* Bottom safety notice */}
                    <div className="bg-slate-900 py-3 px-8 text-center">
                        <p className="text-[10px] font-bold text-white/40 uppercase tracking-[0.4em]">
                            Conexión Encriptada • Servidores Seguros Jamundí
                        </p>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default SecureReporting;
