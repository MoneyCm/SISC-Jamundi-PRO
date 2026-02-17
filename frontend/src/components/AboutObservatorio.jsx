import React from 'react';
import { Target, ListChecks, Info } from 'lucide-react';

const AboutObservatorio = () => {
    const funciones = [
        "Coordinar la información de los entes que integran el sistema institucional de Seguridad Publica.",
        "Generar informes periódicos de comportamientos, contravenciones y delitos registrados, y disponerlos para su consulta.",
        "Elaborar diagnósticos sobre las principales problemáticas del municipio.",
        "Caracterizar los fenómenos de seguridad y convivencia que afectan el municipio.",
        "Identificar y analizar los factores de riesgo de actos violentos y comportamiento delincuencial.",
        "Identificar las zonas más afectadas por un delito en el municipio (georreferenciación de delitos).",
        "Priorizar las problemáticas que se deben atender.",
        "Ejecutar políticas, planes o programas que atiendan las necesidades identificadas.",
        "Elaborar informes de seguimiento a las medidas tomadas y los cambios generados por las intervenciones propuestas."
    ];

    return (
        <section className="bg-white rounded-2xl shadow-lg border border-slate-100 overflow-hidden">
            <div className="bg-slate-50 p-6 border-b border-slate-100 flex items-center gap-3">
                <Info size={24} className="text-primary" />
                <h3 className="text-xl font-bold text-slate-800">Sobre el Observatorio del Delito</h3>
            </div>

            <div className="p-6 md:p-10 grid grid-cols-1 lg:grid-cols-2 gap-10">
                <div className="space-y-6">
                    <div className="flex items-center gap-3 text-primary">
                        <Target size={22} className="shrink-0" />
                        <h4 className="text-lg font-bold uppercase tracking-wider">Misión</h4>
                    </div>
                    <p className="text-slate-600 leading-relaxed text-lg">
                        Gestionar y consolidar información estratégica y periódica sobre los comportamientos contra la vida y la integridad personal. Con base en la información elabora análisis e investigaciones sobre los fenómenos de violencia, inseguridad o baja convivencia que afectan el territorio. Así mismo, asesora y orienta en intervenciones que promuevan la convivencia y seguridad ciudadana.
                    </p>
                </div>

                <div className="space-y-6">
                    <div className="flex items-center gap-3 text-primary">
                        <ListChecks size={22} className="shrink-0" />
                        <h4 className="text-lg font-bold uppercase tracking-wider">Funciones Principales</h4>
                    </div>
                    <ul className="grid grid-cols-1 gap-4">
                        {funciones.map((func, index) => (
                            <li key={index} className="flex items-start gap-4 group">
                                <span className="flex-none flex items-center justify-center w-6 h-6 bg-primary/10 text-primary text-xs font-bold rounded-full mt-1 group-hover:bg-primary group-hover:text-white transition-colors">
                                    {index + 1}
                                </span>
                                <span className="text-slate-600 text-sm md:text-base leading-snug">
                                    {func}
                                </span>
                            </li>
                        ))}
                    </ul>
                </div>
            </div>
            <div className="bg-slate-900 text-white/70 p-4 text-center text-[10px] items-center gap-2">
                <p className="font-bold tracking-[0.2em] uppercase">Oficina del Observatorio | Jamundí</p>
            </div>
        </section>
    );
};

export default AboutObservatorio;
