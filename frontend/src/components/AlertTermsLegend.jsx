import React from 'react';
import { ALERT_TERMS } from '../utils/alertTerms';

/** Leyenda: señal estadística, situación para análisis, alerta SISC y Alerta Temprana de la Defensoría. */
const AlertTermsLegend = ({ highlight, compact = false }) => (
    <details className="bg-slate-50 p-3" open={!compact}>
        <summary className="cursor-pointer text-xs font-black uppercase tracking-wide text-slate-600">Cómo se llama cada aviso</summary>
        <dl className={`mt-2 grid gap-2 ${compact ? '' : 'md:grid-cols-2'}`}>
            {ALERT_TERMS.map((term) => (
                <div key={term.key} className={`border-l-4 pl-2 ${term.key === highlight ? 'border-[#281FD0]' : 'border-slate-200'}`}>
                    <dt className="text-sm font-black text-slate-900">{term.label}</dt>
                    <dd className="text-xs font-semibold leading-5 text-slate-600">{term.text}</dd>
                </div>
            ))}
        </dl>
    </details>
);

export default AlertTermsLegend;
