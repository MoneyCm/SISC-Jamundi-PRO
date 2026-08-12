import React, { useState, useRef, useEffect } from 'react';
import { MessageCircle, X, Send, Bot, Minimize2, Maximize2, Sparkles, ShieldCheck, GripVertical } from 'lucide-react';
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
        { id: 1, text: 'Hola. Soy el asistente ciudadano del SISC Jamundi. Puedo ayudarte a entender cifras publicas, fecha de corte, tendencias, territorios visibles y rutas de atencion. En emergencias llama al 123.', sender: 'ai' }
    ]);
    const [loading, setLoading] = useState(false);
    const scrollRef = useRef(null);
    const assistantRef = useRef(null);
    const dragState = useRef(null);
    const wasDragged = useRef(false);
    const [position, setPosition] = useState(null);

    const openAssistant = () => {
        setPosition((currentPosition) => {
            if (!currentPosition) return currentPosition;
            const panelWidth = Math.min(760, window.innerWidth - 32);
            const panelHeight = Math.min(760, window.innerHeight - 64);
            return {
                x: Math.max(8, Math.min(currentPosition.x, window.innerWidth - panelWidth - 8)),
                y: Math.max(8, Math.min(currentPosition.y, window.innerHeight - panelHeight - 8))
            };
        });
        setIsOpen(true);
        setIsMinimized(false);
    };

    const handleDragStart = (event, allowButton = false) => {
        if (event.button !== 0 || (!allowButton && event.target.closest('button'))) return;
        const element = assistantRef.current;
        if (!element) return;

        const rect = element.getBoundingClientRect();
        wasDragged.current = false;
        dragState.current = {
            offsetX: event.clientX - rect.left,
            offsetY: event.clientY - rect.top,
            width: rect.width,
            height: rect.height,
            startX: event.clientX,
            startY: event.clientY,
            moved: false
        };
        event.currentTarget.setPointerCapture?.(event.pointerId);
    };

    const handleDragMove = (event) => {
        const drag = dragState.current;
        if (!drag) return;

        if (Math.abs(event.clientX - drag.startX) > 4 || Math.abs(event.clientY - drag.startY) > 4) {
            drag.moved = true;
        }

        const maxX = Math.max(8, window.innerWidth - drag.width - 8);
        const maxY = Math.max(8, window.innerHeight - drag.height - 8);
        setPosition({
            x: Math.min(Math.max(8, event.clientX - drag.offsetX), maxX),
            y: Math.min(Math.max(8, event.clientY - drag.offsetY), maxY)
        });
    };

    const handleDragEnd = (event) => {
        const moved = dragState.current?.moved || false;
        dragState.current = null;
        event.currentTarget.releasePointerCapture?.(event.pointerId);
        return moved;
    };

    const positionedStyle = position
        ? { left: position.x, top: position.y, right: 'auto', bottom: 'auto' }
        : undefined;

    useEffect(() => {
        if (scrollRef.current) {
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
        }
    }, [messages, isOpen]);

    useEffect(() => {
        const openAssistant = () => {
            setIsOpen(true);
            setIsMinimized(false);
        };
        window.addEventListener('sisc:open-assistant', openAssistant);
        return () => window.removeEventListener('sisc:open-assistant', openAssistant);
    }, []);

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
            <div
                ref={assistantRef}
                style={positionedStyle}
                className="fixed bottom-3 right-3 z-[60] print:hidden md:bottom-4 md:right-6"
            >
                <div className="relative flex items-end gap-3">
                    <div className="hidden 2xl:block max-w-[420px] overflow-hidden rounded-md border border-[#281FD0]/15 bg-white shadow-2xl ring-1 ring-white/80">
                        <div className="h-2 bg-[#FFB600]" />
                        <div className="px-6 py-5">
                            <div className="flex items-center gap-2">
                                <span className="grid h-10 w-10 place-items-center rounded-full bg-[#281FD0]/10 text-[#281FD0]">
                                    <Sparkles size={20} />
                                </span>
                                <p className="text-xs font-black uppercase tracking-widest text-[#281FD0]">Asistente ciudadano</p>
                            </div>
                            <p className="mt-3 text-2xl font-black leading-tight text-slate-900">Consulte al SISC</p>
                            <p className="mt-2 text-sm font-semibold leading-snug text-slate-600">Corte, cifras, tendencias y orientacion ciudadana.</p>
                            <div className="mt-4 flex flex-wrap gap-2 text-[10px] font-black uppercase tracking-widest text-slate-500"><span className="rounded-full bg-slate-100 px-3 py-1">Datos publicos</span><span className="rounded-full bg-amber-100 px-3 py-1 text-amber-700">Linea 123</span></div>
                        </div>
                    </div>
                    <button
                        type="button"
                        aria-label="Mover asistente"
                        title="Arrastrar para mover el asistente"
                        onPointerDown={(event) => { event.preventDefault(); handleDragStart(event, true); }}
                        onPointerMove={handleDragMove}
                        onPointerUp={handleDragEnd}
                        onPointerCancel={handleDragEnd}
                        className="absolute -left-2 -top-2 z-10 hidden h-8 w-8 cursor-grab place-items-center rounded-full border-2 border-white bg-slate-800 text-white shadow-lg active:cursor-grabbing md:grid"
                    >
                        <GripVertical size={18} />
                    </button>
                    <button
                        type="button"
                        onClick={openAssistant}
                        aria-label="Abrir asistente SISC"
                        className="group relative grid h-14 w-14 place-items-center rounded-full bg-[#281FD0] text-white shadow-xl shadow-[#281FD0]/30 transition-all hover:-translate-y-1 hover:bg-[#1f18a8] active:translate-y-0 focus:outline-none focus:ring-4 focus:ring-[#FFB600]/40 md:h-20 md:w-20 md:shadow-2xl"
                    >
                        <span className="absolute inset-0 rounded-full border-4 border-[#FFB600]/80 opacity-80 animate-ping md:border-8"></span>
                        <span className="absolute -right-1 -top-1 grid h-7 w-7 place-items-center rounded-full border-2 border-white bg-[#FFB600] text-[#281FD0] shadow-lg md:-right-2 md:-top-2 md:h-9 md:w-9">
                            <Sparkles size={16} />
                        </span>
                        <MessageCircle size={22} className="relative transition-transform group-hover:scale-110 md:h-[30px] md:w-[30px]" />
                    </button>
                </div>
            </div>
        );
    }

    return (
        <div ref={assistantRef} style={positionedStyle} className={`fixed bottom-2 right-2 z-[60] flex flex-col overflow-hidden rounded-md border border-slate-200 bg-white shadow-2xl shadow-slate-900/20 ring-1 ring-white/80 transition-all duration-300 print:hidden md:bottom-24 md:right-6 ${isMinimized ? 'h-16 w-[calc(100vw-1rem)] md:h-20 md:w-[min(560px,calc(100vw-2rem))]' : 'h-[calc(100dvh-1rem)] w-[calc(100vw-1rem)] md:h-[min(760px,calc(100vh-4rem))] md:w-[min(760px,calc(100vw-2rem))]'}`}>
            <div
                className="bg-[#281FD0] text-white shrink-0 cursor-move"
                onPointerDown={handleDragStart}
                onPointerMove={handleDragMove}
                onPointerUp={handleDragEnd}
                onPointerCancel={handleDragEnd}
            >
                <div className="h-2 bg-[#FFB600]" />
                <div className="flex items-center justify-between px-4 py-3 md:px-6 md:py-5">
                <div className="flex items-center gap-3 min-w-0">
                    <div className="grid h-10 w-10 shrink-0 place-items-center rounded-md bg-white/15 ring-1 ring-white/20 md:h-14 md:w-14 md:rounded-2xl">
                        <Bot size={24} />
                    </div>
                    <div className="min-w-0">
                        <div className="flex items-center gap-2">
                            <h4 className="truncate text-base font-black md:text-lg">Asistente SISC Jamundi</h4>
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
                    <div className="border-b border-[#FFB600]/35 bg-[#FFF8DF] px-4 py-3 md:px-6 md:py-5">
                        <p className="text-sm font-bold text-slate-800">Canal informativo ciudadano. Para emergencias llama al <span className="text-[#281FD0] font-black">123</span>.</p>
                    </div>

                    <div ref={scrollRef} className="flex-1 space-y-4 overflow-y-auto bg-slate-50/70 p-4 md:space-y-5 md:p-6">
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

                    <form onSubmit={handleSend} className="border-t border-slate-100 bg-white p-4 md:p-6">
                        <div className="mb-3 flex flex-wrap gap-2">
                            {['Resume que informacion tienes', 'Homicidios en julio', 'Barrios con mas casos', 'Rutas de atencion'].map((quick) => (
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
