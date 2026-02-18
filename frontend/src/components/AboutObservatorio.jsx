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
                        Sistema Local de Seguridad y Convivencia
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
                            <h4 className="text-lg font-bold uppercase tracking-wider">Arquitectura Institucional</h4>
                        </div>
                        <p className="text-slate-600 leading-relaxed text-justify">
                            El <strong>Sistema Local de Seguridad y Convivencia de Jamundí</strong> constituye la arquitectura institucional que articula las capacidades del Estado y de la sociedad para enfrentar de manera integral y estratégica los desafíos de la criminalidad, la violencia y la conflictividad social en el territorio.
                        </p>
                        <p className="text-slate-600 leading-relaxed text-justify mt-4">
                            Este sistema está conformado por una alianza estratégica de alto nivel, integrada por la Alcaldía de Jamundí, a través de su Secretaría de Seguridad y Convivencia, las demás secretarías comprometidas con la implementación del PISCC, la Gobernación del Valle del Cauca, la Policía Metropolitana de Santiago de Cali, la Tercera Brigada del Ejército Nacional y la Fiscalía General de la Nación con su seccional territorial.
                        </p>
                    </div>

                    <div className="bg-slate-50 p-6 rounded-2xl border border-slate-100">
                        <h5 className="font-bold text-slate-800 mb-3 flex items-center gap-2">
                            <Users size={18} className="text-primary" />
                            Gobernanza Colaborativa
                        </h5>
                        <p className="text-sm text-slate-500">
                            Más allá de las labores de prevención y control, este sistema gestiona conocimiento, produce inteligencia estratégica y promueve una gobernanza colaborativa, donde confluyen la institucionalidad pública, la fuerza pública, la justicia y la participación ciudadana.
                        </p>
                    </div>
                </div>

                <div className="space-y-8 relative">
                    <div className="absolute top-0 left-0 w-full h-full border-l border-slate-100 hidden lg:block -ml-6"></div>

                    <div className="relative pl-0 lg:pl-6">
                        <div className="flex items-center gap-3 text-primary mb-4">
                            <Activity size={24} />
                            <h4 className="text-lg font-bold uppercase tracking-wider">Enfoque Operativo</h4>
                        </div>
                        <p className="text-slate-600 leading-relaxed text-justify">
                            Estructurado como un sistema integrado, con alto nivel de cohesión y sinergia entre actores, este equipo lidera la ejecución del PISCC, enfocándose en la implementación de las acciones de prevención, control del delito y fortalecimiento de la convivencia de la mano de la ciudadanía.
                        </p>

                        <div className="mt-8 bg-gradient-to-br from-indigo-50 to-white p-6 rounded-2xl border border-indigo-100 shadow-sm">
                            <p className="text-indigo-900 font-medium italic text-lg leading-relaxed text-center">
                                "Se trata de una plataforma viva y adaptativa, capaz de leer el territorio, anticiparse al riesgo y materializar una visión de seguridad ciudadana centrada en la protección de la vida, la dignidad humana y la convivencia pacífica."
                            </p>
                            <div className="mt-4 text-center">
                                <span className="text-xs font-bold text-indigo-400 uppercase tracking-widest">Fuente: PISCC Jamundí 2024-2027</span>
                            </div>
                        </div>

                        <p className="text-slate-600 leading-relaxed text-justify mt-6">
                            En un contexto tan desafiante como el de Jamundí, este sistema no es solo una estructura operativa, sino una expresión concreta de la voluntad política y técnica por garantizar la presencia del Estado en todos los rincones del territorio.
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
