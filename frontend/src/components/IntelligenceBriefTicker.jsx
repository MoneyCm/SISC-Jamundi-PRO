import React, { useState, useEffect } from 'react';
import { Shield, Zap, Calendar, TrendingUp, TrendingDown, Minus } from 'lucide-react';
import { API_BASE_URL } from '../utils/apiConfig';

const IntelligenceBriefTicker = () => {
    const [briefs, setBriefs] = useState([]);
    const [currentIndex, setCurrentLoopIndex] = useState(0);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const fetchBriefs = async () => {
            try {
                const token = localStorage.getItem('token');
                const response = await fetch(`${API_BASE_URL}/intelligence/executive-brief`, {
                    headers: { 'Authorization': `Bearer ${token}` }
                });
                if (response.ok) {
                    const data = await response.json();
                    // Handle the debug wrapper if present
                    const items = data.briefs || data;
                    setBriefs(Array.isArray(items) ? items : []);
                }
            } catch (err) {
                console.error("Error fetching intelligence brief:", err);
            } finally {
                setLoading(false);
            }
        };
        fetchBriefs();
    }, []);

    useEffect(() => {
        if (briefs.length > 1) {
            const timer = setInterval(() => {
                setCurrentLoopIndex((prev) => (prev + 1) % briefs.length);
            }, 8000); // Cambio cada 8 segundos
            return () => clearInterval(timer);
        }
    }, [briefs]);

    if (loading || briefs.length === 0) return null;

    const current = briefs[currentIndex];

    const getTrendIcon = (trend) => {
        switch (trend) {
            case 'UP': return <TrendingUp size={14} className="text-rose-500" />;
            case 'DOWN': return <TrendingDown size={14} className="text-emerald-500" />;
            default: return <Minus size={14} className="text-slate-400" />;
        }
    };

    return (
        <div className="bg-white border-y border-slate-100 shadow-sm overflow-hidden h-12 flex items-center">
            <div className="flex items-center gap-2 px-6 border-r border-slate-100 bg-slate-50 h-full z-10">
                <Shield size={16} className="text-indigo-600 animate-pulse" />
                <span className="text-[10px] font-black text-slate-900 uppercase tracking-widest whitespace-nowrap">
                    SISC Intel-Brief
                </span>
            </div>
            
            <div className="flex-1 px-6 flex items-center justify-between animate-in slide-in-from-right duration-500 key={currentIndex}">
                <div className="flex items-center gap-4 truncate">
                    <div className="flex items-center gap-1.5">
                        <span className="text-[10px] font-black text-slate-400 uppercase tracking-tighter">
                            {current.delito.replace('_', ' ')}:
                        </span>
                        {getTrendIcon(current.tendencia)}
                        <span className={`text-[10px] font-black ${current.tendencia === 'UP' ? 'text-rose-600' : 'text-emerald-600'}`}>
                            {current.variacion_pct > 0 ? '+' : ''}{current.variacion_pct}%
                        </span>
                    </div>
                    
                    <p className="text-xs font-bold text-slate-700 italic truncate max-w-2xl">
                        "{current.analisis_ia}"
                    </p>
                </div>

                <div className="flex items-center gap-2 text-slate-400 bg-slate-50 px-3 py-1 rounded-lg border border-slate-100">
                    <Calendar size={12} />
                    <span className="text-[9px] font-black uppercase tracking-tight">
                        Corte: {current.fecha_corte}
                    </span>
                </div>
            </div>
            
            <div className="px-4 text-[9px] font-black text-slate-300">
                {currentIndex + 1} / {briefs.length}
            </div>
        </div>
    );
};

export default IntelligenceBriefTicker;
