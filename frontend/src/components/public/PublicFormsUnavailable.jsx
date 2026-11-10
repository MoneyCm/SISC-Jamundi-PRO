import React from 'react';
import { ArrowLeft, Phone, ShieldAlert, FileText, HeartHandshake } from 'lucide-react';

// Build ciudadano sin formularios (VITE_PUBLIC_FORMS distinto de 'true'): en vez de un formulario
// que no se puede enviar, se muestran los canales oficiales que sí funcionan.
const TEXTS = {
    reporting: {
        title: 'Reporte seguro',
        intro: 'El formulario en línea de este portal todavía no está habilitado. Para informar un delito o un riesgo use estos canales oficiales:',
    },
    participation: {
        title: 'Participación ciudadana',
        intro: 'El registro de frentes de seguridad y de propuestas en línea todavía no está habilitado. Mientras tanto, puede participar por estos canales:',
    },
};

const PublicFormsUnavailable = ({ kind = 'reporting', onBack, onNavigate }) => {
    const text = TEXTS[kind] || TEXTS.reporting;
    return (
        <main className="mx-auto max-w-3xl px-4 py-12 md:px-6">
            <button onClick={onBack} className="mb-6 inline-flex min-h-11 items-center gap-2 font-black text-[#281FD0]">
                <ArrowLeft size={18} /> Volver al portal
            </button>
            <h1 className="text-3xl font-black text-slate-900">{text.title}</h1>
            <p className="mt-3 text-base font-semibold leading-7 text-slate-600">{text.intro}</p>
            <ul className="mt-6 grid gap-3">
                <li className="flex gap-3 border-l-4 border-red-600 bg-red-50 p-4">
                    <Phone className="mt-0.5 shrink-0 text-red-700" size={20} />
                    <p className="text-sm font-semibold text-red-900"><strong>Emergencias: 123.</strong> Si hay una persona en peligro o un delito en curso, llame de inmediato.</p>
                </li>
                <li className="flex gap-3 border-l-4 border-[#281FD0] bg-white p-4">
                    <ShieldAlert className="mt-0.5 shrink-0 text-[#281FD0]" size={20} />
                    <p className="text-sm font-semibold text-slate-700"><strong>Denuncia en línea:</strong> plataforma ¡A Denunciar! de la Policía Nacional y la Fiscalía, en <a className="font-black text-[#281FD0] underline" href="https://adenunciar.policia.gov.co" target="_blank" rel="noreferrer">adenunciar.policia.gov.co</a>.</p>
                </li>
                <li className="flex gap-3 border-l-4 border-[#281FD0] bg-white p-4">
                    <HeartHandshake className="mt-0.5 shrink-0 text-[#281FD0]" size={20} />
                    <p className="text-sm font-semibold text-slate-700"><strong>Violencia intrafamiliar, de género o contra niñas y niños:</strong> consulte las <button onClick={() => onNavigate?.('victim-support')} className="font-black text-[#281FD0] underline">rutas de atención</button>.</p>
                </li>
                <li className="flex gap-3 border-l-4 border-[#281FD0] bg-white p-4">
                    <FileText className="mt-0.5 shrink-0 text-[#281FD0]" size={20} />
                    <p className="text-sm font-semibold text-slate-700"><strong>Solicitudes, propuestas y quejas a la Alcaldía:</strong> <button onClick={() => onNavigate?.('pqr')} className="font-black text-[#281FD0] underline">Ventanilla única PQR</button>.</p>
                </li>
            </ul>
        </main>
    );
};

export default PublicFormsUnavailable;
