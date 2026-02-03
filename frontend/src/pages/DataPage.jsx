import React, { useState, useEffect } from 'react';
import { Search, Plus, Edit2, Trash2, Save, X, ChevronLeft, ChevronRight, Upload } from 'lucide-react';
import * as XLSX from 'xlsx';
import AIAnalysisModal from '../components/AIAnalysisModal';

import { geocodeNeighborhood } from '../utils/geocoding';
import { API_BASE_URL } from '../utils/apiConfig';

const API_URL = `${API_BASE_URL}/analitica/estadisticas/resumen`;
const INGESTA_URL = `${API_BASE_URL}/ingesta/upload`;

const DataPage = () => {
    const [searchTerm, setSearchTerm] = useState('');
    const [isModalOpen, setIsModalOpen] = useState(false);
    const [isAIModalOpen, setIsAIModalOpen] = useState(false);
    const [pendingImportData, setPendingImportData] = useState([]);
    const [editingId, setEditingId] = useState(null);
    const [formData, setFormData] = useState({
        fecha: '',
        tipo: '',
        barrio: '',
        descripcion: '',
        estado: 'Abierto'
    });

    // Datos iniciales vacíos, se llenarán desde el backend
    const [data, setData] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    // Fetch data on mount
    useEffect(() => {
        fetchIncidents();
    }, []);

    const fetchIncidents = async () => {
        try {
            const response = await fetch(API_URL);
            if (!response.ok) throw new Error('Error al cargar datos');
            const result = await response.json();
            setData(result);
            setError(null);
        } catch (err) {
            console.error(err);
            setError('No se pudo conectar con el servidor. Asegúrate de que el backend esté corriendo.');
        } finally {
            setLoading(false);
        }
    };

    const filteredData = data.filter(item =>
        item.tipo.toLowerCase().includes(searchTerm.toLowerCase()) ||
        item.barrio.toLowerCase().includes(searchTerm.toLowerCase()) ||
        item.descripcion.toLowerCase().includes(searchTerm.toLowerCase())
    );

    const handleInputChange = (e) => {
        const { name, value } = e.target;
        setFormData(prev => ({ ...prev, [name]: value }));
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        // Nota: Los endpoints de creación/edición individual deben implementarse en FastAPI si se requieren
        alert('Funcionalidad de guardado individual en desarrollo. Use Importar Excel para carga masiva.');
    };

    const handleEdit = (item) => {
        setFormData({
            fecha: item.fecha,
            tipo: item.tipo,
            barrio: item.barrio,
            descripcion: item.descripcion,
            estado: item.estado
        });
        setEditingId(item.id);
        setIsModalOpen(true);
    };

    const handleDelete = async (id) => {
        // Implementación pendiente en backend FastAPI
        alert('Funcionalidad de eliminación en desarrollo.');
    };

    const handleClearDatabase = async () => {
        if (!confirm('¿Estás seguro de que deseas eliminar TODOS los incidentes? Esta acción no se puede deshacer.')) return;

        try {
            const res = await fetch(`${API_BASE_URL}/ingesta/clear`, { method: 'DELETE' });
            if (res.ok) {
                alert('Base de datos limpiada correctamente.');
                fetchIncidents();
            } else {
                throw new Error('No se pudo limpiar la base de datos.');
            }
        } catch (err) {
            alert(err.message);
        }
    };

    const handleCloseModal = () => {
        setIsModalOpen(false);
        setEditingId(null);
        setFormData({ fecha: '', tipo: '', barrio: '', descripcion: '', estado: 'Abierto' });
    };

    const [uploadReport, setUploadReport] = useState(null);

    const handleFileUpload = async (e) => {
        const file = e.target.files[0];
        if (!file) return;

        const reader = new FileReader();
        reader.onload = (evt) => {
            try {
                const bstr = evt.target.result;
                const wb = XLSX.read(bstr, { type: 'binary' });
                const wsname = wb.SheetNames[0];
                const ws = wb.Sheets[wsname];

                // 1. Detección Dinámica de Encabezados
                // Leemos las primeras 20 filas como matriz para encontrar los títulos
                const rows = XLSX.utils.sheet_to_json(ws, { header: 1, range: 0, defval: '' });
                let headerIndex = rows.findIndex(row =>
                    row.some(cell => {
                        const c = String(cell || '').toLowerCase().trim();
                        return c.includes('fecha') || c.includes('delito') || c.includes('conducta') || c.includes('hecho');
                    })
                );

                if (headerIndex === -1) headerIndex = 0;

                const rawData = XLSX.utils.sheet_to_json(ws, { range: headerIndex });
                const headers = Object.keys(rawData[0] || {});
                console.log("Encabezados detectados en fila", headerIndex + 1, ":", headers);

                // 2. Normalizar columnas y mapeo inteligente
                const findValue = (row, keywords) => {
                    const keys = Object.keys(row);
                    const clean = (s) => (s || '').toString().toLowerCase().replace(/[^a-z0-9]/g, '');

                    let foundKey = keys.find(key => {
                        const lowKey = clean(key);
                        return keywords.some(kw => lowKey === clean(kw));
                    });

                    if (!foundKey) {
                        foundKey = keys.find(key => {
                            const lowKey = clean(key);
                            return keywords.some(kw => kw.length > 3 && (lowKey.includes(clean(kw)) || clean(kw).includes(lowKey)));
                        });
                    }

                    return foundKey ? row[foundKey] : undefined;
                };

                const excelDateToJSDate = (serial) => {
                    if (!serial || typeof serial !== 'number') return serial;
                    const date = new Date(Math.round((serial - 25569) * 86400 * 1000));
                    return date.toISOString().split('T')[0];
                };

                const normalizedData = rawData.map(row => {
                    const cleanRow = {};
                    Object.keys(row).forEach(key => {
                        cleanRow[key.toLowerCase().trim()] = row[key];
                    });

                    const rawFecha = findValue(cleanRow, ['fecha_hecho', 'fecha', 'dia', 'date']);
                    const barrio = findValue(cleanRow, ['barrios_hecho', 'barrio', 'sector', 'comuna']);

                    // Escaneo inteligente de coordenadas
                    let lat = findValue(cleanRow, ['latitud_hecho', 'latitud', 'lat', 'y_hecho', 'coordenada_y', 'coord_y', 'coordy', 'y', 'norte']);
                    let lng = findValue(cleanRow, ['longitud_hecho', 'longitud', 'long', 'lon', 'x_hecho', 'coordenada_x', 'coord_x', 'coordx', 'x', 'este']);

                    if (!lat || !lng) {
                        Object.values(row).forEach(val => {
                            const num = parseFloat(String(val).replace(',', '.'));
                            if (!isNaN(num)) {
                                if (num > 3.2 && num < 3.4 && !lat) lat = num;
                                if (num < -76.4 && num > -76.6 && !lng) lng = num;
                            }
                        });
                    }

                    // FALLBACK: Geocodificación por Barrio (User Request)
                    // Si siguen faltando o son el punto central genérico (-76.53, 3.26)
                    if (!lat || !lng || (Math.abs(lat - 3.2606) < 0.001 && Math.abs(lng - (-76.5364)) < 0.001)) {
                        const geo = geocodeNeighborhood(barrio || "");
                        lat = geo.lat;
                        lng = geo.lng;
                    }

                    return {
                        fecha: typeof rawFecha === 'number' ? excelDateToJSDate(rawFecha) : rawFecha,
                        tipo: findValue(cleanRow, ['descripcion_conducta', 'delito', 'clase_de_sitio', 'conducta', 'tipo']),
                        barrio: barrio,
                        descripcion: findValue(cleanRow, ['modalidad', 'detalle_de_la_conducta', 'observacion', 'descripcion', 'detalle']),
                        latitud: lat,
                        longitud: lng,
                        hora: findValue(cleanRow, ['hora24', 'hora_hecho', 'hora', 'time']) || '00:00'
                    };
                });

                setPendingImportData(normalizedData);
                setIsAIModalOpen(true);
            } catch (err) {
                alert('Error leyendo el archivo: ' + err.message);
            }
        };
        reader.readAsBinaryString(file);
        e.target.value = ''; // Reset input
    };

    const handleConfirmImport = async (analyzedData) => {
        try {
            setLoading(true);
            setIsAIModalOpen(false);

            const response = await fetch(`${API_BASE_URL}/ingesta/bulk`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(analyzedData)
            });

            const result = await response.json();
            if (!response.ok) throw new Error(result.detail || 'Error en la integración');

            setUploadReport(result.report);
            fetchIncidents();
        } catch (err) {
            alert('Error en la integración final: ' + err.message);
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="space-y-6">
            <div className="flex flex-col md:flex-row justify-between items-center gap-4">
                <div>
                    <h2 className="text-2xl font-bold text-slate-800">Gestión de Datos</h2>
                    <p className="text-slate-500">Administración de registros delictivos</p>
                </div>
                <div className="flex gap-2">
                    <button
                        onClick={handleClearDatabase}
                        className="flex items-center space-x-2 bg-red-50 text-red-600 px-4 py-2 rounded-lg hover:bg-red-100 transition-colors border border-red-100"
                    >
                        <Trash2 size={20} />
                        <span>Limpiar Base de Datos</span>
                    </button>
                    <label className="flex items-center space-x-2 bg-emerald-600 text-white px-4 py-2 rounded-lg hover:bg-emerald-700 transition-colors cursor-pointer shadow-sm">
                        <Upload size={20} />
                        <span>Cargar Excel / SIEDCO</span>
                        <input type="file" className="hidden" accept=".xlsx, .xls, .csv" onChange={handleFileUpload} />
                    </label>
                    <button className="flex items-center space-x-2 bg-primary text-white px-4 py-2 rounded-lg hover:bg-emphasis transition-colors shadow-sm">
                        <Plus size={20} />
                        <span>Nuevo Registro</span>
                    </button>
                </div>
            </div>

            {/* Barra de Búsqueda */}
            <div className="relative">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-slate-400" size={20} />
                <input
                    type="text"
                    placeholder="Buscar por tipo, barrio o descripción..."
                    className="w-full pl-10 pr-4 py-3 border border-slate-200 rounded-lg focus:ring-2 focus:ring-primary focus:border-transparent outline-none"
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                />
            </div>

            {/* Reporte de Carga */}
            {uploadReport && (
                <div className={`p-4 rounded-md border ${uploadReport.error_count > 0 ? 'bg-orange-50 border-orange-200' : 'bg-green-50 border-green-200'}`}>
                    <div className="flex justify-between items-center mb-2">
                        <h3 className="font-bold text-slate-800 flex items-center">
                            <Upload size={18} className="mr-2" />
                            Reporte de Ingesta
                        </h3>
                        <button onClick={() => setUploadReport(null)} className="text-slate-400 hover:text-slate-600">
                            <X size={16} />
                        </button>
                    </div>
                    <p className="text-sm text-slate-700">
                        Procesados <strong>{uploadReport.total}</strong> registros:
                        <span className="text-green-600 mx-1">{uploadReport.success_count} exitosos</span> y
                        <span className="text-red-600 mx-1">{uploadReport.error_count} errores</span>.
                    </p>

                    {uploadReport.errors.length > 0 && (
                        <div className="mt-3 overflow-hidden border border-red-100 rounded">
                            <div className="bg-red-50 px-3 py-1 text-[10px] uppercase font-bold text-red-400 border-b border-red-100">
                                Errores Detallados
                            </div>
                            <div className="max-h-32 overflow-y-auto bg-white p-2 space-y-1">
                                {uploadReport.errors.map((err, i) => (
                                    <div key={i} className="text-xs text-red-600 flex gap-2">
                                        <span className="font-mono font-bold bg-red-50 px-1 rounded">Fila {err.fila}:</span>
                                        <span>{err.error}</span>
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}
                </div>
            )}

            {/* Mensaje de Error */}
            {error && (
                <div className="p-4 bg-red-50 text-red-700 rounded-md border border-red-200">
                    {error}
                </div>
            )}

            {/* Tabla */}
            <div className="bg-white rounded-lg shadow-sm border border-slate-200 overflow-hidden">
                <div className="overflow-x-auto">
                    <table className="w-full text-left border-collapse">
                        <thead>
                            <tr className="bg-slate-50 border-b border-slate-200">
                                <th className="p-4 font-semibold text-slate-600">Fecha</th>
                                <th className="p-4 font-semibold text-slate-600">Tipo de Delito</th>
                                <th className="p-4 font-semibold text-slate-600">Barrio</th>
                                <th className="p-4 font-semibold text-slate-600">Descripción</th>
                                <th className="p-4 font-semibold text-slate-600">Estado</th>
                                <th className="p-4 font-semibold text-slate-600 text-right">Acciones</th>
                            </tr>
                        </thead>
                        <tbody>
                            {loading ? (
                                <tr>
                                    <td colSpan="6" className="p-8 text-center text-slate-500">
                                        Cargando datos...
                                    </td>
                                </tr>
                            ) : filteredData.length > 0 ? (
                                filteredData.map((item) => (
                                    <tr key={item.id} className="border-b border-slate-100 hover:bg-slate-50 transition-colors">
                                        <td className="p-4 text-slate-700">{item.fecha}</td>
                                        <td className="p-4">
                                            <span className="px-2 py-1 bg-primary/10 text-primary rounded-full text-xs font-medium">
                                                {item.tipo}
                                            </span>
                                        </td>
                                        <td className="p-4 text-slate-700">{item.barrio}</td>
                                        <td className="p-4 text-slate-600 text-sm max-w-xs truncate">{item.descripcion}</td>
                                        <td className="p-4">
                                            <span className={`px-2 py-1 rounded-full text-xs font-medium ${item.estado === 'Cerrado' ? 'bg-green-100 text-green-700' :
                                                item.estado === 'En Investigación' ? 'bg-orange-100 text-orange-700' :
                                                    'bg-red-100 text-red-700'
                                                }`}>
                                                {item.estado}
                                            </span>
                                        </td>
                                        <td className="p-4 text-right space-x-2">
                                            <button onClick={() => handleEdit(item)} className="text-slate-400 hover:text-primary transition-colors">
                                                <Edit2 size={18} />
                                            </button>
                                            <button onClick={() => handleDelete(item.id)} className="text-slate-400 hover:text-red-600 transition-colors">
                                                <Trash2 size={18} />
                                            </button>
                                        </td>
                                    </tr>
                                ))
                            ) : (
                                <tr>
                                    <td colSpan="6" className="p-8 text-center text-slate-500">
                                        No se encontraron registros que coincidan con la búsqueda.
                                    </td>
                                </tr>
                            )}
                        </tbody>
                    </table>
                </div>

                {/* Paginación Simple */}
                <div className="p-4 border-t border-slate-200 flex justify-between items-center text-sm text-slate-500">
                    <span>Mostrando {filteredData.length} registros</span>
                    <div className="flex space-x-2">
                        <button className="p-1 border rounded hover:bg-slate-50 disabled:opacity-50" disabled><ChevronLeft size={16} /></button>
                        <button className="p-1 border rounded hover:bg-slate-50 disabled:opacity-50" disabled><ChevronRight size={16} /></button>
                    </div>
                </div>
            </div>

            {/* Modal de Formulario */}
            {isModalOpen && (
                <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
                    <div className="bg-white rounded-lg shadow-xl w-full max-w-md overflow-hidden">
                        <div className="p-4 border-b border-slate-200 flex justify-between items-center bg-slate-50">
                            <h3 className="font-bold text-lg text-slate-800">{editingId ? 'Editar Registro' : 'Nuevo Registro'}</h3>
                            <button onClick={handleCloseModal} className="text-slate-400 hover:text-slate-600">
                                <X size={20} />
                            </button>
                        </div>
                        <form onSubmit={handleSubmit} className="p-6 space-y-4">
                            <div>
                                <label className="block text-sm font-medium text-slate-700 mb-1">Fecha</label>
                                <input
                                    type="date"
                                    name="fecha"
                                    required
                                    value={formData.fecha}
                                    onChange={handleInputChange}
                                    className="w-full border-slate-300 rounded-md shadow-sm focus:ring-primary focus:border-primary"
                                />
                            </div>
                            <div>
                                <label className="block text-sm font-medium text-slate-700 mb-1">Tipo de Delito</label>
                                <select
                                    name="tipo"
                                    required
                                    value={formData.tipo}
                                    onChange={handleInputChange}
                                    className="w-full border-slate-300 rounded-md shadow-sm focus:ring-primary focus:border-primary"
                                >
                                    <option value="">Seleccionar...</option>
                                    <option value="Homicidio">Homicidio</option>
                                    <option value="Hurto a Personas">Hurto a Personas</option>
                                    <option value="Hurto a Comercio">Hurto a Comercio</option>
                                    <option value="Lesiones Personales">Lesiones Personales</option>
                                    <option value="Violencia Intrafamiliar">Violencia Intrafamiliar</option>
                                    <option value="Riña">Riña</option>
                                </select>
                            </div>
                            <div>
                                <label className="block text-sm font-medium text-slate-700 mb-1">Barrio</label>
                                <input
                                    type="text"
                                    name="barrio"
                                    required
                                    value={formData.barrio}
                                    onChange={handleInputChange}
                                    className="w-full border-slate-300 rounded-md shadow-sm focus:ring-primary focus:border-primary"
                                />
                            </div>
                            <div>
                                <label className="block text-sm font-medium text-slate-700 mb-1">Descripción</label>
                                <textarea
                                    name="descripcion"
                                    rows="3"
                                    value={formData.descripcion}
                                    onChange={handleInputChange}
                                    className="w-full border-slate-300 rounded-md shadow-sm focus:ring-primary focus:border-primary"
                                ></textarea>
                            </div>
                            <div>
                                <label className="block text-sm font-medium text-slate-700 mb-1">Estado</label>
                                <select
                                    name="estado"
                                    value={formData.estado}
                                    onChange={handleInputChange}
                                    className="w-full border-slate-300 rounded-md shadow-sm focus:ring-primary focus:border-primary"
                                >
                                    <option value="Abierto">Abierto</option>
                                    <option value="En Investigación">En Investigación</option>
                                    <option value="Cerrado">Cerrado</option>
                                </select>
                            </div>
                            <div className="pt-4 flex justify-end space-x-3">
                                <button
                                    type="button"
                                    onClick={handleCloseModal}
                                    className="px-4 py-2 border border-slate-300 rounded-md text-slate-700 hover:bg-slate-50"
                                >
                                    Cancelar
                                </button>
                                <button
                                    type="submit"
                                    className="px-4 py-2 bg-primary text-white rounded-md hover:bg-primary/90 flex items-center"
                                >
                                    <Save size={16} className="mr-2" />
                                    Guardar
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            )}

            {/* Modal de Análisis IA */}
            <AIAnalysisModal
                isOpen={isAIModalOpen}
                onClose={() => setIsAIModalOpen(false)}
                data={pendingImportData}
                onConfirm={handleConfirmImport}
            />
        </div>
    );
};

export default DataPage;
