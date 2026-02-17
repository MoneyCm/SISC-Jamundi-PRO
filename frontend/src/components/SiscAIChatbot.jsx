import React, { useState, useRef, useEffect } from 'react';
import { MessageCircle, X, Send, Bot, User, Minimize2, Maximize2 } from 'lucide-react';
import { API_BASE_URL } from '../utils/apiConfig';

const SiscAIChatbot = () => {
    const [isOpen, setIsOpen] = useState(false);
    const [isMinimized, setIsMinimized] = useState(false);
    const [input, setInput] = useState('');
    const [messages, setMessages] = useState([
        { id: 1, text: '¡Hola! Soy el asistente virtual del SISC Jamundí. ¿En qué puedo orientarte hoy sobre seguridad, convivencia o rutas de atención?', sender: 'ai' }
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
            // Usamos el endpoint existente de IA pero con un contexto ciudadano
            const response = await fetch(`${API_BASE_URL}/ia/chat_ciudadano`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message: input })
            });

            if (!response.ok) throw new Error('Error de conexión');
            const data = await response.json();

            setMessages(prev => [...prev, {
                id: Date.now() + 1,
                text: data.response || 'Lo siento, estoy teniendo problemas para procesar tu consulta. Por favor intenta más tarde.',
                sender: 'ai'
            }]);
        } catch (err) {
            setMessages(prev => [...prev, {
                id: Date.now() + 1,
                text: 'En este momento no puedo conectarme con mi centro de inteligencia. Pero recuerda que puedes llamar al 123 para emergencias.',
                sender: 'ai'
            }]);
        } finally {
            setLoading(false);
        }
    };

    if (!isOpen) {
        return (
            <div className="fixed bottom-8 right-8 z-50">
                <div className="relative group">
                    <div className="absolute -top-12 right-0 bg-white px-4 py-2 rounded-xl shadow-lg border border-slate-100 text-xs font-bold text-slate-700 opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap animate-bounce pointer-events-none">
                        ¿Cómo puedo ayudarte hoy? 🤖
                    </div>
                    <button
                        onClick={() => setIsOpen(true)}
                        className="bg-primary hover:bg-primary-600 text-white p-5 rounded-full shadow-2xl transition-all transform hover:scale-110 active:scale-95 flex items-center justify-center"
                    >
                        <MessageCircle size={28} />
                    </button>
                    {/* Alerta de notificación visual */}
                    <span className="absolute top-0 right-0 flex h-4 w-4">
                        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-accent opacity-75"></span>
                        <span className="relative inline-flex rounded-full h-4 w-4 bg-accent"></span>
                    </span>
                </div>
            </div>
        );
    }

    return (
        <div className={`fixed bottom-8 right-8 z-50 bg-white shadow-2xl rounded-3xl overflow-hidden flex flex-col transition-all duration-300 border border-slate-100 ${isMinimized ? 'h-16 w-72' : 'h-[550px] w-[350px] md:w-[400px]'}`}>
            {/* Header */}
            <div className="bg-[#281FD0] p-4 text-white flex items-center justify-between shrink-0">
                <div className="flex items-center gap-3">
                    <div className="bg-white/20 p-2 rounded-xl">
                        <Bot size={20} />
                    </div>
                    <div>
                        <h4 className="font-bold text-sm">Asistente SISC Jamundí</h4>
                        <div className="flex items-center gap-1">
                            <span className="w-1.5 h-1.5 bg-emerald-400 rounded-full animate-pulse"></span>
                            <span className="text-[10px] text-white/60 font-medium uppercase tracking-widest">En línea</span>
                        </div>
                    </div>
                </div>
                <div className="flex items-center gap-1">
                    <button onClick={() => setIsMinimized(!isMinimized)} className="p-2 hover:bg-white/10 rounded-lg transition-colors">
                        {isMinimized ? <Maximize2 size={16} /> : <Minimize2 size={16} />}
                    </button>
                    <button onClick={() => setIsOpen(false)} className="p-2 hover:bg-white/10 rounded-lg transition-colors">
                        <X size={18} />
                    </button>
                </div>
            </div>

            {!isMinimized && (
                <>
                    {/* Messages Area */}
                    <div ref={scrollRef} className="flex-1 overflow-y-auto p-4 space-y-4 bg-slate-50/50">
                        {messages.map(msg => (
                            <div key={msg.id} className={`flex ${msg.sender === 'user' ? 'justify-end' : 'justify-start'}`}>
                                <div className={`max-w-[85%] p-3 rounded-2xl text-sm leading-relaxed shadow-sm ${msg.sender === 'user'
                                    ? 'bg-primary text-white rounded-br-none'
                                    : 'bg-white text-slate-700 border border-slate-100 rounded-bl-none'}`}>
                                    {msg.text}
                                </div>
                            </div>
                        ))}
                        {loading && (
                            <div className="flex justify-start italic text-xs text-slate-400 animate-pulse">
                                SISC está pensando...
                            </div>
                        )}
                    </div>

                    {/* Input Area */}
                    <form onSubmit={handleSend} className="p-4 border-t border-slate-100 bg-white">
                        <div className="relative">
                            <input
                                type="text"
                                value={input}
                                onChange={(e) => setInput(e.target.value)}
                                placeholder="Escribe tu consulta aquí..."
                                className="w-full bg-slate-50 border-none rounded-2xl px-4 py-3 text-sm focus:ring-2 focus:ring-primary outline-none transition-all pr-12"
                                disabled={loading}
                            />
                            <button
                                type="submit"
                                disabled={!input.trim() || loading}
                                className={`absolute right-2 top-1/2 -translate-y-1/2 p-2 rounded-xl transition-all ${!input.trim() || loading ? 'text-slate-300' : 'bg-primary text-white hover:bg-primary-600 shadow-md'}`}
                            >
                                <Send size={18} />
                            </button>
                        </div>
                        <p className="text-[10px] text-slate-400 mt-3 text-center uppercase font-bold tracking-widest">
                            Inteligencia Artificial aplicada a la seguridad
                        </p>
                    </form>
                </>
            )}
        </div>
    );
};

export default SiscAIChatbot;
