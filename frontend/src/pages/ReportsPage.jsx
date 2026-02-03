import React from 'react';
import {
    LineChart, Line, BarChart, Bar, PieChart, Pie, Cell,
    XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer
} from 'recharts';
import { Download, Calendar, Filter } from 'lucide-react';
import { API_BASE_URL } from '../utils/apiConfig';

const ReportsPage = () => {
    // Datos simulados
    const trendData = [
        { name: 'Ene', homicidios: 4, hurtos: 24 },
        { name: 'Feb', homicidios: 3, hurtos: 18 },
        { name: 'Mar', homicidios: 2, hurtos: 28 },
        { name: 'Abr', homicidios: 5, hurtos: 22 },
        { name: 'May', homicidios: 3, hurtos: 30 },
        { name: 'Jun', homicidios: 4, hurtos: 25 },
    ];

    const typeData = [
        { name: 'Hurto a Personas', value: 45 },
        { name: 'Hurto a Comercio', value: 25 },
        { name: 'Lesiones Personales', value: 15 },
        { name: 'Violencia Intrafamiliar', value: 10 },
        { name: 'Homicidio', value: 5 },
    ];

    const neighborhoodData = [
        { name: 'Centro', delitos: 35 },
        { name: 'Terranova', delitos: 28 },
        { name: 'Bonanza', delitos: 22 },
        { name: 'Libertadores', delitos: 18 },
        { name: 'Alfaguara', delitos: 15 },
    ];

    const COLORS = ['#0088FE', '#00C49F', '#FFBB28', '#FF8042', '#FF4444'];

    const handleExportPDF = async () => {
        try {
            window.open(`${API_BASE_URL}/reportes/generar-boletin`, '_blank');
        } catch (err) {
            alert('Error al generar el PDF. Asegúrate de que el backend esté activo.');
        }
    };

    return (
        <div className="space-y-6">
            {/* Encabezado y Filtros */}
            <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 bg-white p-4 rounded-lg shadow-sm border border-slate-200">
                <div>
                    <h2 className="text-2xl font-bold text-slate-800">Boletines y Reportes</h2>
                    <p className="text-slate-500">Estadísticas de seguridad y convivencia</p>
                </div>
                <div className="flex gap-2">
                    <button className="flex items-center space-x-2 px-4 py-2 bg-white border border-slate-300 rounded-md text-slate-700 hover:bg-slate-50">
                        <Calendar size={18} />
                        <span>Últimos 6 meses</span>
                    </button>
                    <button
                        onClick={handleExportPDF}
                        className="flex items-center space-x-2 px-4 py-2 bg-primary text-white rounded-md hover:bg-primary/90 transition-colors"
                    >
                        <Download size={18} />
                        <span>Exportar PDF</span>
                    </button>
                </div>
            </div>

            {/* Gráficas Superiores */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* Tendencia Temporal */}
                <div className="bg-white p-6 rounded-lg shadow-sm border border-slate-200">
                    <h3 className="text-lg font-semibold mb-4 text-slate-800">Tendencia de Delitos</h3>
                    <div className="h-80">
                        <ResponsiveContainer width="100%" height="100%">
                            <LineChart data={trendData}>
                                <CartesianGrid strokeDasharray="3 3" />
                                <XAxis dataKey="name" />
                                <YAxis />
                                <Tooltip />
                                <Legend />
                                <Line type="monotone" dataKey="hurtos" stroke="#8884d8" name="Hurtos" strokeWidth={2} />
                                <Line type="monotone" dataKey="homicidios" stroke="#ff4444" name="Homicidios" strokeWidth={2} />
                            </LineChart>
                        </ResponsiveContainer>
                    </div>
                </div>

                {/* Distribución por Tipo */}
                <div className="bg-white p-6 rounded-lg shadow-sm border border-slate-200">
                    <h3 className="text-lg font-semibold mb-4 text-slate-800">Distribución por Tipo de Delito</h3>
                    <div className="h-80">
                        <ResponsiveContainer width="100%" height="100%">
                            <PieChart>
                                <Pie
                                    data={typeData}
                                    cx="50%"
                                    cy="50%"
                                    labelLine={false}
                                    label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                                    outerRadius={80}
                                    fill="#8884d8"
                                    dataKey="value"
                                >
                                    {typeData.map((entry, index) => (
                                        <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                                    ))}
                                </Pie>
                                <Tooltip />
                            </PieChart>
                        </ResponsiveContainer>
                    </div>
                </div>
            </div>

            {/* Gráfica Inferior y Tabla */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                {/* Top Barrios */}
                <div className="lg:col-span-2 bg-white p-6 rounded-lg shadow-sm border border-slate-200">
                    <h3 className="text-lg font-semibold mb-4 text-slate-800">Barrios con Mayor Incidencia</h3>
                    <div className="h-80">
                        <ResponsiveContainer width="100%" height="100%">
                            <BarChart data={neighborhoodData} layout="vertical">
                                <CartesianGrid strokeDasharray="3 3" />
                                <XAxis type="number" />
                                <YAxis dataKey="name" type="category" width={100} />
                                <Tooltip />
                                <Legend />
                                <Bar dataKey="delitos" fill="#82ca9d" name="Cantidad de Delitos" radius={[0, 4, 4, 0]} />
                            </BarChart>
                        </ResponsiveContainer>
                    </div>
                </div>

                {/* Resumen Numérico */}
                <div className="bg-white p-6 rounded-lg shadow-sm border border-slate-200">
                    <h3 className="text-lg font-semibold mb-4 text-slate-800">Resumen del Periodo</h3>
                    <div className="space-y-4">
                        <div className="p-4 bg-primary/10 rounded-lg border border-primary/20">
                            <p className="text-sm text-primary font-medium">Total Incidentes</p>
                            <p className="text-3xl font-bold text-primary">142</p>
                            <p className="text-xs text-primary/80 mt-1">↑ 12% vs mes anterior</p>
                        </div>
                        <div className="p-4 bg-green-50 rounded-lg border border-green-100">
                            <p className="text-sm text-green-600 font-medium">Casos Resueltos</p>
                            <p className="text-3xl font-bold text-green-800">85</p>
                            <p className="text-xs text-green-500 mt-1">60% de efectividad</p>
                        </div>
                        <div className="p-4 bg-orange-50 rounded-lg border border-orange-100">
                            <p className="text-sm text-orange-600 font-medium">Zonas Críticas</p>
                            <p className="text-3xl font-bold text-orange-800">3</p>
                            <p className="text-xs text-orange-500 mt-1">Requieren intervención</p>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default ReportsPage;
