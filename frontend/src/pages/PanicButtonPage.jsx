import React, { useState, useEffect, useRef } from 'react';
import { 
    ShieldAlert, 
    Camera, 
    Video as VideoIcon, 
    MapPin, 
    Send, 
    History, 
    CheckCircle2, 
    AlertTriangle,
    Navigation,
    Loader2,
    ChevronLeft,
    Trash2,
    Image as ImageIcon
} from 'lucide-react';
import { API_BASE_URL } from '../utils/apiConfig';

// Configuración de IndexedDB para persistencia de archivos en cola
const DB_NAME = 'SISC_Panic_DB';
const STORE_NAME = 'offline_alerts';

const initDB = () => {
    return new Promise((resolve, reject) => {
        const request = indexedDB.open(DB_NAME, 1);
        request.onupgradeneeded = (e) => {
            const db = e.target.result;
            if (!db.objectStoreNames.contains(STORE_NAME)) {
                db.createObjectStore(STORE_NAME, { keyPath: 'id', autoIncrement: true });
            }
        };
        request.onsuccess = (e) => resolve(e.target.result);
        request.onerror = (e) => reject(e.target.error);
    });
};

const saveToQueue = async (payload, media) => {
    const db = await initDB();
    const tx = db.transaction(STORE_NAME, 'readwrite');
    const store = tx.objectStore(STORE_NAME);
    
    // Convertir Files a Blobs para almacenamiento
    const mediaBlobs = await Promise.all(media.map(async file => ({
        blob: file,
        name: file.name,
        type: file.type
    })));

    return new Promise((resolve, reject) => {
        const request = store.add({
            payload,
            media: mediaBlobs,
            timestamp: new Date().toISOString()
        });
        request.onsuccess = () => resolve();
        request.onerror = () => reject(request.error);
    });
};

const getQueue = async () => {
    const db = await initDB();
    const tx = db.transaction(STORE_NAME, 'readonly');
    const store = tx.objectStore(STORE_NAME);
    return new Promise((resolve) => {
        const request = store.getAll();
        request.onsuccess = () => resolve(request.result);
    });
};

const clearFromQueue = async (id) => {
    const db = await initDB();
    const tx = db.transaction(STORE_NAME, 'readwrite');
    const store = tx.objectStore(STORE_NAME);
    store.delete(id);
};

const PanicButtonPage = ({ onBack }) => {
    const [isPressing, setIsPressing] = useState(false);
    const [progress, setProgress] = useState(0);
    const [status, setStatus] = useState('ready'); // ready, obtaining_pos, sending, success, error, queue
    const [location, setLocation] = useState(null);
    const [evidence, setEvidence] = useState([]);
    const [offlineQueueCount, setOfflineQueueCount] = useState(0);
    
    const pressTimer = useRef(null);
    const progressInterval = useRef(null);
    const fileInputRef = useRef(null);

    useEffect(() => {
        updateQueueCount();
    }, []);

    const updateQueueCount = async () => {
        const queue = await getQueue();
        setOfflineQueueCount(queue.length);
    };

    const handleStartPress = () => {
        if (status === 'sending' || status === 'success') return;
        setIsPressing(true);
        setStatus('ready');
        setProgress(0);
        
        if (navigator.vibrate) navigator.vibrate(50);

        progressInterval.current = setInterval(() => {
            setProgress(prev => {
                if (prev >= 100) {
                    clearInterval(progressInterval.current);
                    handleTriggered();
                    return 100;
                }
                return prev + 2;
            });
        }, 30);
    };

    const handleEndPress = () => {
        setIsPressing(false);
        clearInterval(progressInterval.current);
        if (progress < 100) setProgress(0);
    };

    const handleTriggered = () => {
        setIsPressing(false);
        if (navigator.vibrate) navigator.vibrate([100, 50, 100]);
        sendAlert();
    };

    const getPosition = () => {
        return new Promise((resolve) => {
            if (!navigator.geolocation) {
                resolve(null);
                return;
            }
            navigator.geolocation.getCurrentPosition(
                pos => resolve({ lat: pos.coords.latitude, lon: pos.coords.longitude, accuracy: pos.coords.accuracy }),
                () => resolve(null),
                { enableHighAccuracy: true, timeout: 5000 }
            );
        });
    };

    const sendAlert = async () => {
        setStatus('obtaining_pos');
        const pos = await getPosition();
        setLocation(pos);
        
        setStatus('sending');
        
        const payload = {
            timestamp: new Date().toISOString(),
            lat: pos?.lat || null,
            lon: pos?.lon || null,
            accuracy: pos?.accuracy || null,
            note: "Alerta de Pánico (Ciudadano)",
            device_info: { userAgent: navigator.userAgent, platform: navigator.platform }
        };

        const formData = new FormData();
        formData.append('payload', JSON.stringify(payload));
        evidence.forEach(file => formData.append('media', file));

        try {
            const response = await fetch(`${API_BASE_URL}/panic/alert`, {
                method: 'POST',
                body: formData
            });

            if (response.ok) {
                setStatus('success');
                setEvidence([]);
                if (navigator.vibrate) navigator.vibrate(200);
                setTimeout(() => setStatus('ready'), 4000);
            } else {
                throw new Error('Server Error');
            }
        } catch (err) {
            console.error("Fallo envío, encolando con IndexedDB...", err);
            await saveToQueue(payload, evidence);
            await updateQueueCount();
            setStatus('queue');
            setEvidence([]);
            setTimeout(() => setStatus('ready'), 3000);
        }
    };

    const retryQueue = async () => {
        const queue = await getQueue();
        if (queue.length === 0) return;
        
        setStatus('sending');
        let successCount = 0;

        for (const item of queue) {
            try {
                const formData = new FormData();
                formData.append('payload', JSON.stringify(item.payload));
                
                // Re-adjuntar archivos desde la base de datos local
                if (item.media && item.media.length > 0) {
                    item.media.forEach(m => {
                        const file = new File([m.blob], m.name, { type: m.type });
                        formData.append('media', file);
                    });
                }

                const response = await fetch(`${API_BASE_URL}/panic/alert`, {
                    method: 'POST',
                    body: formData
                });

                if (response.ok) {
                    successCount++;
                    await clearFromQueue(item.id);
                }
            } catch (e) {
                console.error("Fallo reintento:", e);
            }
        }

        await updateQueueCount();
        setStatus('ready');
        alert(`Resultados del envío: ${successCount} exitosos. Quedan ${offlineQueueCount - successCount} pendientes.`);
    };

    const handleFileChange = (e) => {
        const files = Array.from(e.target.files);
        console.log("Archivos seleccionados:", files);
        setEvidence(prev => [...prev, ...files]);
    };

    const removeEvidence = (index) => {
        setEvidence(prev => prev.filter((_, i) => i !== index));
    };

    return (
        <div className="min-h-screen bg-slate-950 text-white font-sans flex flex-col">
            <header className="p-6 flex items-center justify-between border-b border-white/10 bg-slate-900/50 sticky top-0 z-50">
                <button onClick={onBack} className="p-2 hover:bg-white/10 rounded-full transition-colors">
                    <ChevronLeft size={24} />
                </button>
                <div className="text-center">
                    <h1 className="text-lg font-black tracking-tighter uppercase">SISC Pánico</h1>
                    <p className="text-[10px] text-red-500 font-bold tracking-widest uppercase">Emergencia Jamundí</p>
                </div>
                <div className="w-10"></div>
            </header>

            <main className="flex-1 p-6 flex flex-col items-center justify-center gap-10 max-w-lg mx-auto w-full">
                <div className="relative w-64 h-64 flex items-center justify-center">
                    <svg className="absolute inset-0 w-full h-full -rotate-90 scale-110">
                        <circle cx="128" cy="128" r="120" stroke="currentColor" strokeWidth="6" fill="transparent" className="text-white/5" />
                        <circle cx="128" cy="128" r="120" stroke="currentColor" strokeWidth="6" fill="transparent" strokeDasharray="754" strokeDashoffset={754 - (progress * 7.54)} strokeLinecap="round" className="text-red-500 transition-all duration-75" />
                    </svg>

                    <button
                        onMouseDown={handleStartPress} onMouseUp={handleEndPress} onTouchStart={handleStartPress} onTouchEnd={handleEndPress}
                        className={`relative w-56 h-56 rounded-full flex flex-col items-center justify-center gap-3 transition-all duration-300 shadow-[0_0_50px_rgba(239,68,68,0.2)] ${isPressing ? 'scale-95 bg-red-700' : 'scale-100 bg-red-600'} ${status === 'sending' ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'} group`}
                    >
                        {status === 'ready' && (
                            <>
                                <ShieldAlert size={64} className="text-white group-hover:scale-110 transition-transform" />
                                <span className="text-lg font-black uppercase tracking-tight">Presiona</span>
                            </>
                        )}
                        {isPressing && <span className="text-4xl font-black">{Math.floor(progress)}%</span>}
                        {status === 'obtaining_pos' && <Loader2 className="animate-spin" size={48} />}
                        {status === 'sending' && <Loader2 className="animate-spin" size={48} />}
                        {status === 'success' && <CheckCircle2 size={64} className="text-green-400 animate-bounce" />}
                        {status === 'queue' && <AlertTriangle size={64} className="text-yellow-400" />}
                    </button>
                </div>

                <div className="w-full space-y-4">
                    <div className="flex items-center justify-between px-2">
                        <span className="text-[10px] font-black text-white/40 uppercase tracking-[0.2em]">Adjuntar Evidencia</span>
                        {evidence.length > 0 && <span className="bg-red-500 text-white text-[9px] font-black px-2 py-0.5 rounded-full">{evidence.length}</span>}
                    </div>
                    <div className="flex gap-3 h-28">
                        <button onClick={() => fileInputRef.current?.click()} className="w-24 bg-slate-900 border-2 border-dashed border-white/10 rounded-2xl flex flex-col items-center justify-center gap-2 hover:bg-slate-800 transition-all active:scale-95">
                            <Camera size={24} className="text-red-400" />
                            <span className="text-[8px] font-bold uppercase tracking-wider">Cámara</span>
                        </button>
                        <div className="flex-1 flex gap-2 overflow-x-auto pb-2 scrollbar-none">
                            {evidence.length === 0 ? (
                                <div className="flex-1 border border-white/5 rounded-2xl bg-white/5 flex items-center justify-center text-[10px] font-bold uppercase italic text-white/20">Sin archivos</div>
                            ) : (
                                evidence.map((file, idx) => (
                                    <div key={idx} className="min-w-[80px] h-full bg-slate-900 border border-white/10 rounded-xl p-2 relative flex flex-col items-center justify-center gap-1 group animate-fade-in">
                                        {file.type.startsWith('image/') ? <ImageIcon size={20} className="text-emerald-400" /> : <VideoIcon size={20} className="text-blue-400" />}
                                        <span className="text-[8px] font-bold truncate w-full text-center">{file.name}</span>
                                        <button onClick={() => removeEvidence(idx)} className="absolute -top-1 -right-1 bg-red-500 rounded-full p-1 shadow-lg hover:bg-red-600 transition-colors"><Trash2 size={10} /></button>
                                    </div>
                                ))
                            )}
                        </div>
                    </div>
                    <input type="file" ref={fileInputRef} onChange={handleFileChange} multiple accept="image/*,video/*" className="hidden" />
                </div>

                <div className="w-full bg-slate-900/50 rounded-3xl p-5 border border-white/5 space-y-4">
                    <div className="flex items-center gap-4">
                        <div className="p-3 bg-red-500/10 rounded-2xl text-red-400"><MapPin size={20} /></div>
                        <div>
                            <p className="text-[10px] uppercase font-bold text-white/40">Ubicación Actual</p>
                            <p className="text-xs font-bold font-mono tracking-tighter">
                                {location ? `${location.lat.toFixed(6)}, ${location.lon.toFixed(6)}` : 'Activando sensores GPS...'}
                            </p>
                        </div>
                    </div>
                    {offlineQueueCount > 0 && (
                        <div className="pt-4 border-t border-white/5 flex items-center justify-between">
                            <div className="flex items-center gap-2 text-yellow-500 animate-pulse"><History size={16} /><span className="text-xs font-black uppercase">{offlineQueueCount} En Cola</span></div>
                            <button onClick={retryQueue} className="bg-yellow-500 text-black px-4 py-1.5 rounded-full text-[10px] font-black uppercase tracking-wider hover:bg-yellow-400 transition-all active:scale-95">Reenviar Ahora</button>
                        </div>
                    )}
                </div>
            </main>
        </div>
    );
};

export default PanicButtonPage;
