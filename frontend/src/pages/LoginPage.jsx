import React, { useState } from 'react';
import { Lock, User, Eye, EyeOff, Loader, ArrowLeft } from 'lucide-react';
import { API_BASE_URL } from '../utils/apiConfig';
import { clearStoredSession } from '../utils/apiClient';

const LoginPage = ({ onLoginSuccess, onBackClick, notice = '' }) => {
    const [formData, setFormData] = useState({ username: '', password: '' });
    const [showPassword, setShowPassword] = useState(false);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');

    const handleSubmit = async (e) => {
        e.preventDefault();
        setLoading(true);
        setError('');

        try {
            const formDataBody = new URLSearchParams();
            formDataBody.append('username', formData.username);
            formDataBody.append('password', formData.password);

            // Asegurar que no haya doble slash si API_BASE_URL termina en /
            const baseUrl = API_BASE_URL.endsWith('/') ? API_BASE_URL.slice(0, -1) : API_BASE_URL;

            const response = await fetch(`${baseUrl}/auth/login`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                body: formDataBody
            });

            if (!response.ok) {
                let errorMessage = "Error en el inicio de sesión";
                try {
                    const data = await response.json();
                    errorMessage = data.detail || errorMessage;
                } catch (e) {
                    errorMessage = `Error ${response.status}: El servidor no respondió con JSON válido`;
                }
                throw new Error(errorMessage);
            }

            const data = await response.json();
            const token = data.access_token;
            localStorage.setItem('token', token);

            // Fetch profile
            const profileRes = await fetch(`${baseUrl}/auth/me`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });

            if (!profileRes.ok) {
                throw new Error("No se pudo cargar el perfil del usuario");
            }

            const profile = await profileRes.json();
            onLoginSuccess(token, profile.roles, profile.data_level_max, profile);

        } catch (err) {
            clearStoredSession();
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="min-h-screen bg-slate-50 flex items-center justify-center p-4">
            <div className="max-w-md w-full animate-fade-in">
                <button
                    onClick={onBackClick}
                    className="flex items-center gap-2 text-slate-500 hover:text-primary transition-colors mb-6 font-medium text-sm group"
                >
                    <ArrowLeft size={16} className="group-hover:-translate-x-1 transition-transform" />
                    Volver al Portal Público
                </button>

                <div className="bg-white rounded-3xl shadow-2xl overflow-hidden border border-slate-100">
                    <div className="p-8 md:p-10">
                        <div className="flex flex-col items-center mb-10">
                            <div className="bg-primary/5 p-5 rounded-2xl mb-6 flex items-center justify-center">
                                <img src="/assets/escudo-limpio.png" alt="Escudo Jamundí" className="w-16 h-16 object-contain" />
                            </div>
                            <h2 className="text-4xl font-black text-slate-800 font-titles uppercase tracking-tighter">SISC</h2>
                            <p className="text-slate-400 text-[10px] font-black uppercase tracking-[0.2em] mt-2">ALCALDÍA DE JAMUNDÍ</p>
                            <p className="text-slate-500 text-sm font-medium mt-4">Acceso exclusivo personal institucional</p>
                        </div>

                        {(error || notice) && (
                            <div className="bg-red-50 text-red-600 p-4 rounded-xl text-sm font-bold mb-6 border border-red-100 flex items-center gap-3">
                                <div className="w-1.5 h-1.5 bg-red-600 rounded-full"></div>
                                {error || notice}
                            </div>
                        )}

                        <form onSubmit={handleSubmit} className="space-y-5">
                            <div>
                                <label className="block text-[10px] font-black text-slate-400 uppercase tracking-widest mb-2 ml-1">Usuario Institucional</label>
                                <div className="relative group">
                                    <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none text-slate-400 group-focus-within:text-primary transition-colors">
                                        <User size={18} />
                                    </div>
                                    <input
                                        type="text"
                                        required
                                        className="block w-full pl-11 pr-4 py-3.5 bg-slate-50 border border-slate-200 text-slate-800 rounded-xl focus:ring-2 focus:ring-primary/20 focus:border-primary transition-all outline-none text-sm font-medium"
                                        placeholder="usuario@jamundi.gov.co"
                                        value={formData.username}
                                        onChange={(e) => setFormData({ ...formData, username: e.target.value })}
                                    />
                                </div>
                            </div>

                            <div>
                                <label className="block text-[10px] font-black text-slate-400 uppercase tracking-widest mb-2 ml-1">Contraseña</label>
                                <div className="relative group">
                                    <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none text-slate-400 group-focus-within:text-primary transition-colors">
                                        <Lock size={18} />
                                    </div>
                                    <input
                                        type={showPassword ? "text" : "password"}
                                        required
                                        className="block w-full pl-11 pr-12 py-3.5 bg-slate-50 border border-slate-200 text-slate-800 rounded-xl focus:ring-2 focus:ring-primary/20 focus:border-primary transition-all outline-none text-sm font-medium"
                                        placeholder="············"
                                        value={formData.password}
                                        onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                                    />
                                    <button
                                        type="button"
                                        onClick={() => setShowPassword(!showPassword)}
                                        className="absolute inset-y-0 right-0 pr-4 flex items-center text-slate-400 hover:text-slate-600 transition-colors"
                                    >
                                        {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                                    </button>
                                </div>
                            </div>

                            <button
                                type="submit"
                                disabled={loading}
                                className={`w-full bg-primary text-white py-4 rounded-xl font-black uppercase tracking-widest text-xs flex items-center justify-center gap-3 shadow-lg shadow-primary/20 transition-all active:scale-95 ${loading ? 'opacity-70' : 'hover:opacity-90'}`}
                            >
                                {loading ? (
                                    <>
                                        <Loader className="animate-spin" size={20} />
                                        AUTENTICANDO...
                                    </>
                                ) : (
                                    'INGRESAR AL SISTEMA'
                                )}
                            </button>
                        </form>
                    </div>

                    <div className="bg-slate-50 p-6 border-t border-slate-100">
                        <p className="text-center text-[9px] text-slate-400 uppercase font-black tracking-widest leading-relaxed">
                            SISC | SISTEMA DE INFORMACIÓN PARA LA SEGURIDAD Y CONVIVENCIA<br />
                            ALCALDÍA DE JAMUNDÍ - VALLE DEL CAUCA
                        </p>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default LoginPage;
