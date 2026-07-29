import React, { useState, useRef, useEffect } from 'react';
import { MessageCircle, X, Send, Bot, Minimize2, Maximize2 } from 'lucide-react';
import { API_BASE_URL } from '../utils/apiConfig';

const normalizeAssistantText = (value) => {
    return String(value || '')
        .replace(/\r\n/g, '\n')
        .replace(/\r/g, '\n')
        .replace(/\s+-\s+/g, '\n- ')
        .trim();
};

const renderInlineMarkdown = (value, keyPrefix) => {
    return String(value || '').split(/(\*\*[^*]+\*\*)/g).map((part, index) => {
        if (part.startsWith('**') && part.endsWith('**') && part.length > 4) {
            return <strong key={`${keyPrefix}-strong-${index}`} className="font-black text-slate-900">{part.slice(2, -2)}</strong>;
        }
        return <React.Fragment key={`${keyPrefix}-text-${index}`}>{part}</React.Fragment>;
    });
};

const AssistantMessage = ({ text }) => {
    const lines = normalizeAssistantText(text).split('\n').map(line => line.trim()).filter(Boolean);
    const blocks = [];
    let bullets = [];

    const flushBullets = () => {
        if (!bullets.length) return;
        const bulletBlock = bullets;
        blocks.push(
            <ul key={`list-${blocks.length}`} className="list-disc space-y-1 pl-5">
                {bulletBlock.map((line, index) => (
                    <li key={`bullet-${blocks.length}-${index}`}>{renderInlineMarkdown(line.replace(/^-\s*/, ''), `bullet-${blocks.length}-${index}`)}</li>
                ))}
            </ul>
        );
        bullets = [];
    };

    lines.forEach((line) => {
        if (line.startsWith('- ')) {
            bullets.push(line);
            return;
        }
        flushBullets();
        blocks.push(
            <p key={`paragraph-${blocks.length}`}>
                {renderInlineMarkdown(line, `paragraph-${blocks.length}`)}
            </p>
        );
    });

    flushBullets();

    return <div className="space-y-2">{blocks}</div>;
};

const SiscAIChatbot = () => {
    const [isOpen, setIsOpen] = useState(false);
    const [isMinimized, setIsMinimized] = useState(false);
    const [input, setInput] = useState('');
    const [messages, setMessages] = useState([
        { id: 1, text: 'Hola. Soy el asistente virtual del SISC Jamundi. Puedo orientarte sobre seguridad, convivencia, rutas de atencion y uso del portal ciudadano.', sender: 'ai' }
    ]);
    const [loading, setLoading] = useState(false);
    const scrollRef = useRef(null);

    useEffect(() => {
        if (scrollRef.current) {
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
        }
    }, [messages, isOpen]);

    const handleSend = async (e) => {
        e.preventDefault();
        if (!input.trim() || loading) return;

        const userMsg = { id: Date.now(), text: input, sender: 'user' };
        setMessages(prev => [...prev, userMsg]);
        setInput('');
        setLoading(true);

        try {
            const response = await fetch(`${API_BASE_URL}/ia/chat_ciudadano`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message: input })
            });

            if (!response.ok) throw new Error('Error de conexion');
            const data = await response.json();

            setMessages(prev => [...prev, {
                id: Date.now() + 1,
                text: data.response || 'Lo siento, estoy teniendo problemas para procesar tu consulta. Por favor intenta mas tarde.',
                sender: 'ai'
            }]);
        } catch (err) {
            setMessages(prev => [...prev, {
                id: Date.now() + 1,
                text: 'En este momento no puedo conectarme con el servicio de inteligencia. Para emergencias llama al 123.',
                sender: 'ai'
            }]);
        } finally {
            setLoading(false);
        }
    };

    if (!isOpen) {
        return (
            <div className="fixed right-4 bottom-28 md:right-6 z-[60] print:hidden">
                <div className="relative flex items-center gap-3">
                    <div className="hidden sm:block bg-white border border-slate-200 px-4 py-3 shadow-xl max-w-[230px]">
                        <p className="text-[10px] font-black uppercase tracking-widest text-[#281FD0]">Asistente SISC</p>
                        <p className="text-xs font-bold text-slate-700 mt-0.5">Orientacion rapida para ciudadanos</p>
                    </div>
                    <button
                        type="button"
                        onClick={() => setIsOpen(true)}
                        aria-label="Abrir asistente SISC"
                        className="relative bg-[#281FD0] hover:bg-[#1f18a8] text-white p-4 md:p-5 rounded-full shadow-2xl transition-all transform hover:scale-105 active:scale-95 flex items-center justify-center focus:outline-none focus:ring-4 focus:ring-[#281FD0]/25"
                    >
                        <MessageCircle size={28} />
                        <span className="absolute -top-1 -right-1 flex h-4 w-4">
                            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[#FFB600] opacity-75"></span>
                            <span className="relative inline-flex rounded-full h-4 w-4 bg-[#FFB600]"></span>
                        </span>
                    </button>
                </div>
            </div>
        );
    }

    return (
        <div className={`fixed right-4 bottom-24 md:right-6 z-[60] bg-white shadow-2xl overflow-hidden flex flex-col transition-all duration-300 border border-slate-200 print:hidden ${isMinimized ? 'h-16 w-[min(360px,calc(100vw-2rem))]' : 'h-[min(620px,calc(100vh-7rem))] w-[min(420px,calc(100vw-2rem))]'}`}>
            <div className="bg-[#281FD0] px-4 py-3 text-white flex items-center justify-between shrink-0">
                <div className="flex items-center gap-3 min-w-0">
                    <div className="bg-white/20 p-2 rounded-xl shrink-0">
                        <Bot size={20} />
                    </div>
                    <div className="min-w-0">
                        <h4 className="font-black text-sm truncate">Asistente SISC Jamundi</h4>
                        <div className="flex items-center gap-1">
                            <span className="w-1.5 h-1.5 bg-emerald-400 rounded-full animate-pulse"></span>
                            <span className="text-[10px] text-white/70 font-bold uppercase tracking-widest">En linea</span>
                        </div>
                    </div>
                </div>
                <div className="flex items-center gap-1 shrink-0">
                    <button type="button" onClick={() => setIsMinimized(!isMinimized)} className="p-2 hover:bg-white/10 rounded-lg transition-colors" aria-label={isMinimized ? 'Expandir asistente' : 'Minimizar asistente'}>
                        {isMinimized ? <Maximize2 size={16} /> : <Minimize2 size={16} />}
                    </button>
                    <button type="button" onClick={() => setIsOpen(false)} className="p-2 hover:bg-white/10 rounded-lg transition-colors" aria-label="Cerrar asistente">
                        <X size={18} />
                    </button>
                </div>
            </div>

            {!isMinimized && (
                <>
                    <div className="px-4 py-3 bg-slate-50 border-b border-slate-100">
                        <p className="text-xs font-semibold text-slate-600">Este canal es informativo. No reemplaza la linea de emergencias 123.</p>
                    </div>

                    <div ref={scrollRef} className="flex-1 overflow-y-auto p-4 space-y-4 bg-slate-50/70">
                        {messages.map(msg => (
                            <div key={msg.id} className={`flex ${msg.sender === 'user' ? 'justify-end' : 'justify-start'}`}>
                                <div className={`max-w-[85%] p-3 text-sm leading-relaxed shadow-sm ${msg.sender === 'user'
                                    ? 'bg-[#281FD0] text-white rounded-2xl rounded-br-none'
                                    : 'bg-white text-slate-700 border border-slate-100 rounded-2xl rounded-bl-none'}`}>
                                    {msg.sender === 'ai' ? <AssistantMessage text={msg.text} /> : msg.text}
                                </div>
                            </div>
                        ))}
                        {loading && (
                            <div className="flex justify-start text-xs text-slate-500 animate-pulse font-semibold">
                                SISC esta procesando la consulta...
                            </div>
                        )}
                    </div>

                    <form onSubmit={handleSend} className="p-4 border-t border-slate-100 bg-white">
                        <div className="relative">
                            <input
                                type="text"
                                value={input}
                                onChange={(e) => setInput(e.target.value)}
                                placeholder="Escribe tu consulta aqui..."
                                className="w-full bg-slate-50 border border-slate-200 rounded-2xl px-4 py-3 text-sm focus:ring-2 focus:ring-[#281FD0] focus:border-[#281FD0] outline-none transition-all pr-12"
                                disabled={loading}
                            />
                            <button
                                type="submit"
                                disabled={!input.trim() || loading}
                                aria-label="Enviar consulta"
                                className={`absolute right-2 top-1/2 -translate-y-1/2 p-2 rounded-xl transition-all ${!input.trim() || loading ? 'text-slate-300' : 'bg-[#281FD0] text-white hover:bg-[#1f18a8] shadow-md'}`}
                            >
                                <Send size={18} />
                            </button>
                        </div>
                        <p className="text-[10px] text-slate-400 mt-3 text-center uppercase font-bold tracking-widest">
                            Asistente ciudadano del SISC
                        </p>
                    </form>
                </>
            )}
        </div>
    );
};

export default SiscAIChatbot;