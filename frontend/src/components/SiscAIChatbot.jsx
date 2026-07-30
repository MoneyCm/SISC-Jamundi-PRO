import React, { useState, useRef, useEffect } from 'react';
import { MessageCircle, X, Send, Bot, Minimize2, Maximize2, Sparkles, ShieldCheck } from 'lucide-react';
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
        { id: 1, text: 'Hola. Soy el asistente ciudadano del SISC Jamundi. Puedo ayudarte a entender cifras publicas, rutas de atencion, convivencia y uso del portal. En emergencias llama al 123.', sender: 'ai' }
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
        const historyForRequest = [...messages, userMsg]
            .slice(-8)
            .map(({ text, sender }) => ({ text, sender }));
        setMessages(prev => [...prev, userMsg]);
        setInput('');
        setLoading(true);

        try {
            const response = await fetch(`${API_BASE_URL}/ia/chat_ciudadano`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message: input, history: historyForRequest })
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
            <div className="fixed right-4 bottom-20 md:bottom-12 md:right-8 z-[60] print:hidden">
                <div className="relative flex items-end gap-3">
                    <div className="hidden sm:block max-w-[420px] overflow-hidden border border-[#281FD0]/15 bg-white shadow-2xl ring-1 ring-white/80">
                        <div className="h-2 bg-[#FFB600]" />
                        <div className="px-6 py-5">
                            <div className="flex items-center gap-2">
                                <span className="grid h-10 w-10 place-items-center rounded-full bg-[#281FD0]/10 text-[#281FD0]">
                                    <Sparkles size={20} />
                                </span>
                                <p className="text-xs font-black uppercase tracking-widest text-[#281FD0]">Asistente ciudadano</p>
                            </div>
                            <p className="mt-3 text-2xl font-black leading-tight text-slate-900">Preguntale al SISC</p>
                            <p className="mt-2 text-sm font-semibold leading-snug text-slate-600">Cifras publicas, rutas de atencion y orientacion rapida.</p>
                        </div>
                    </div>
                    <button
                        type="button"
                        onClick={() => setIsOpen(true)}
                        aria-label="Abrir asistente SISC"
                        className="group relative grid h-24 w-24 place-items-center rounded-full bg-[#281FD0] text-white shadow-2xl shadow-[#281FD0]/35 transition-all hover:-translate-y-1 hover:bg-[#1f18a8] active:translate-y-0 focus:outline-none focus:ring-4 focus:ring-[#FFB600]/40 md:h-36 md:w-36"
                    >
                        <span className="absolute inset-0 rounded-full border-8 border-[#FFB600]/80 opacity-80 animate-ping"></span>
                        <span className="absolute -top-2 -right-2 grid h-10 w-10 place-items-center md:h-12 md:w-12 rounded-full border-2 border-white bg-[#FFB600] text-[#281FD0] shadow-lg">
                            <Sparkles size={20} />
                        </span>
                        <MessageCircle size={46} className="relative transition-transform group-hover:scale-110" />
                    </button>
                </div>
            </div>
        );
    }

    return (
        <div className={`fixed right-4 bottom-24 md:right-6 z-[60] bg-white shadow-2xl shadow-slate-900/20 overflow-hidden flex flex-col transition-all duration-300 border border-slate-200 ring-1 ring-white/80 print:hidden ${isMinimized ? 'h-20 w-[min(560px,calc(100vw-2rem))]' : 'h-[min(760px,calc(100vh-4rem))] w-[min(760px,calc(100vw-2rem))]'}`}>
            <div className="bg-[#281FD0] text-white shrink-0">
                <div className="h-2 bg-[#FFB600]" />
                <div className="px-6 py-5 flex items-center justify-between">
                <div className="flex items-center gap-3 min-w-0">
                    <div className="grid h-14 w-14 place-items-center rounded-2xl bg-white/15 ring-1 ring-white/20 shrink-0">
                        <Bot size={30} />
                    </div>
                    <div className="min-w-0">
                        <div className="flex items-center gap-2">
                            <h4 className="font-black text-lg truncate">Asistente SISC Jamundi</h4>
                            <ShieldCheck size={20} className="shrink-0 text-[#FFB600]" />
                        </div>
                        <div className="flex items-center gap-1.5">
                            <span className="w-1.5 h-1.5 bg-emerald-400 rounded-full animate-pulse"></span>
                            <span className="text-xs text-white/75 font-bold uppercase tracking-widest">Ciudadano / en linea</span>
                        </div>
                    </div>
                </div>
                <div className="flex items-center gap-1 shrink-0">
                    <button type="button" onClick={() => setIsMinimized(!isMinimized)} className="p-3 hover:bg-white/10 rounded-lg transition-colors" aria-label={isMinimized ? 'Expandir asistente' : 'Minimizar asistente'}>
                        {isMinimized ? <Maximize2 size={20} /> : <Minimize2 size={20} />}
                    </button>
                    <button type="button" onClick={() => setIsOpen(false)} className="p-3 hover:bg-white/10 rounded-lg transition-colors" aria-label="Cerrar asistente">
                        <X size={22} />
                    </button>
                </div>
                </div>
            </div>

            {!isMinimized && (
                <>
                    <div className="px-6 py-5 bg-[#FFF8DF] border-b border-[#FFB600]/35">
                        <p className="text-sm font-bold text-slate-800">Canal informativo ciudadano. Para emergencias llama al <span className="text-[#281FD0] font-black">123</span>.</p>
                    </div>

                    <div ref={scrollRef} className="flex-1 overflow-y-auto p-6 space-y-5 bg-slate-50/70">
                        {messages.map(msg => (
                            <div key={msg.id} className={`flex ${msg.sender === 'user' ? 'justify-end' : 'justify-start'}`}>
                                <div className={`max-w-[88%] p-4 text-base leading-relaxed shadow-sm ${msg.sender === 'user'
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

                    <form onSubmit={handleSend} className="p-6 border-t border-slate-100 bg-white">
                        <div className="mb-3 flex flex-wrap gap-2">
                            {['Corte de datos', 'Homicidios 2026', 'Rutas de atencion'].map((quick) => (
                                <button
                                    key={quick}
                                    type="button"
                                    onClick={() => setInput(quick)}
                                    className="rounded-full border border-slate-200 bg-slate-50 px-4 py-2 text-xs font-black text-slate-600 transition-colors hover:border-[#281FD0]/40 hover:bg-[#281FD0]/5 hover:text-[#281FD0]"
                                >
                                    {quick}
                                </button>
                            ))}
                        </div>
                        <div className="relative">
                            <input
                                type="text"
                                value={input}
                                onChange={(e) => setInput(e.target.value)}
                                placeholder="Escribe tu consulta aqui..."
                                className="w-full bg-slate-50 border border-slate-200 rounded-2xl px-6 py-5 text-base focus:ring-2 focus:ring-[#281FD0] focus:border-[#281FD0] outline-none transition-all pr-12"
                                disabled={loading}
                            />
                            <button
                                type="submit"
                                disabled={!input.trim() || loading}
                                aria-label="Enviar consulta"
                                className={`absolute right-2 top-1/2 -translate-y-1/2 p-3 rounded-xl transition-all ${!input.trim() || loading ? 'text-slate-300' : 'bg-[#281FD0] text-white hover:bg-[#1f18a8] shadow-md'}`}
                            >
                                <Send size={22} />
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