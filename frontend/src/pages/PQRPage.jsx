import React from 'react';
import { ArrowLeft, Globe, ExternalLink } from 'lucide-react';

const PQRPage = ({ onBack }) => {
    return (
        <div className="min-h-screen bg-slate-50 flex flex-col animate-fade-in">
            {/* Header / Nav */}
            <div className="bg-white border-b border-slate-200 px-6 py-4 flex justify-between items-center shadow-sm relative z-10">
                <div className="flex items-center gap-4">
                    <button
                        onClick={onBack}
                        className="p-2 hover:bg-slate-100 rounded-full transition-colors text-slate-600 hover:text-primary"
                        title="Volver"
                    >
                        <ArrowLeft size={24} />
                    </button>
                    <div>
                        <h1 className="text-xl font-bold text-slate-800 flex items-center gap-2">
                            <Globe size={20} className="text-primary" />
                            Ventanilla Única Digital
                        </h1>
                        <p className="text-xs text-slate-500 font-medium">Sistema de PQR y Trámites - Alcaldía de Jamundí</p>
                    </div>
                </div>
                <a
                    href="https://www.sisnet.com.co/jamundipqr/#no-back-button"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="hidden md:flex items-center gap-2 text-xs font-bold text-primary bg-primary/10 px-4 py-2 rounded-lg hover:bg-primary/20 transition-colors"
                >
                    Abrir en nueva pestaña <ExternalLink size={14} />
                </a>
            </div>

            {/* Iframe Content */}
            <div className="flex-1 w-full bg-white relative">
                <iframe
                    src="https://www.sisnet.com.co/jamundipqr/#no-back-button"
                    title="Ventanilla Única Digital PQR"
                    className="w-full h-full absolute inset-0 border-none"
                    allow="camera; microphone; geolocation"
                />
            </div>
        </div>
    );
};

export default PQRPage;
