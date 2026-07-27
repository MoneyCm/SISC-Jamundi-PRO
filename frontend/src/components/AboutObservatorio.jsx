import React from 'react';
import { Target, Info, ShieldCheck, Users, Activity } from 'lucide-react';

const AboutObservatorio = () => {
    return (
        <section className="bg-white rounded-3xl shadow-xl border border-slate-100 overflow-hidden animate-fade-in relative group">
            {/* Header Moderno con Gradiente Institucional */}
            <div className="bg-gradient-to-r from-primary to-primary-800 p-8 flex flex-col md:flex-row items-start md:items-center justify-between gap-4 relative overflow-hidden">
                <div className="relative z-10">
                    <div className="flex items-center gap-3 mb-2">
                        <div className="bg-white/20 p-2 rounded-lg backdrop-blur-sm">
                            <ShieldCheck size={24} className="text-white" />
                        </div>
                        <span className="text-xs font-bold uppercase tracking-widest text-white/80">Información Institucional</span>
                    </div>
                    <h3 className="text-2xl md:text-3xl font-black text-white leading-tight">
                        Sistema de Información para la Seguridad y Convivencia
                    </h3>
                </div>
                {/* Decorative Pattern */}
                <div className="absolute top-0 right-0 w-64 h-64 bg-white/5 rounded-full blur-3xl -mr-16 -mt-16 pointer-events-none"></div>
            </div>

            <div className="p-8 md:p-12 grid grid-cols-1 lg:grid-cols-2 gap-12">
                <div className="space-y-8">
                    <div>
                        <div className="flex items-center gap-3 text-primary mb-4">
                            <Target size={24} />
                            <h4 className="text-lg font-bold uppercase tracking-wider">Propósito del SISC</h4>
                        </div>
                        <p className="text-slate-600 leading-relaxed text-justify">
                            El <strong>Sistema de Información para la Seguridad y Convivencia de Jamundí (SISC)</strong> es la plataforma institucional que consolida, estandariza y analiza datos para apoyar decisiones sobre prevención, control del delito, convivencia y atención territorial.
                        </p>
                        <p className="text-slate-600 leading-relaxed text-justify mt-4">
                            Integra información aportada por la Alcaldía de Jamundí, sus secretarías, la Gobernación del Valle del Cauca, la Policía Metropolitana de Santiago de Cali, el Ejército Nacional, la Fiscalía General de la Nación y los demás actores que participan en la seguridad y convivencia del municipio.
                        </p>
                    </div>

                    <div className="bg-slate-50 p-6 rounded-2xl border border-slate-100">
                        <h5 className="font-bold text-slate-800 mb-3 flex items-center gap-2">
                            <Users size={18} className="text-primary" />
                            Gestión de información
                        </h5>
                        <p className="text-sm text-slate-500">
                            El SISC conserva la trazabilidad de cada fuente, compara periodos equivalentes y transforma los registros disponibles en indicadores, alertas y productos técnicos para cada nivel de decisión.
                        </p>
                    </div>
                </div>

                <div className="space-y-8 relative">
                    <div className="absolute top-0 left-0 w-full h-full border-l border-slate-100 hidden lg:block -ml-6"></div>

                    <div className="relative pl-0 lg:pl-6">
                        <div className="flex items-center gap-3 text-primary mb-4">
                            <Activity size={24} />
                            <h4 className="text-lg font-bold uppercase tracking-wider">Ciclo de decisión</h4>
                        </div>
                        <p className="text-slate-600 leading-relaxed text-justify">
                            La información sigue un ciclo verificable: las fuentes detectan un foco, el SISC recomienda una acción, la entidad responsable ejecuta y el siguiente corte mide si el riesgo disminuyó, se mantuvo o se desplazó.
                        </p>

                        <div className="mt-8 bg-gradient-to-br from-indigo-50 to-white p-6 rounded-2xl border border-indigo-100 shadow-sm">
                            <p className="text-indigo-900 font-medium italic text-lg leading-relaxed text-center">
                                Detectar, decidir, ejecutar y medir: cada dato debe conducir a una acción verificable.
                            </p>
                            <div className="mt-4 text-center">
                                <span className="text-xs font-bold text-indigo-400 uppercase tracking-widest">Ciclo de gestión SISC Jamundí</span>
                            </div>
                        </div>

                        <p className="text-slate-600 leading-relaxed text-justify mt-6">
                            El sistema no reemplaza la competencia de las entidades ni los canales de emergencia. Les entrega evidencia común, oportuna y trazable para coordinar recursos y evaluar resultados.
                        </p>
                    </div>
                </div>
            </div>

            <div className="bg-slate-50 border-t border-slate-100 p-4 text-center">
                <p className="text-[10px] text-slate-400 font-bold tracking-[0.2em] uppercase">Secretaría de Seguridad y Convivencia</p>
            </div>
        </section>
    );
};

export default AboutObservatorio;
