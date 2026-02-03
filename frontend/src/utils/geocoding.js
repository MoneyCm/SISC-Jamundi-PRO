/**
 * Módulo de Geocodificación Local para Jamundí
 * Proporciona coordenadas de referencia para barrios y corregimientos 
 * cuando el archivo de origen no las contiene.
 */

const NEIGHBORHOOD_COORDS = {
    // Casco Urbano - Sectores principales
    "CENTRO": [3.2606, -76.5364],
    "EL ROSARIO": [3.2635, -76.5300],
    "EL JORDAN": [3.2720, -76.5340],
    "PORTALES DEL JORDAN": [3.2730, -76.5350],
    "PORTAL DE JORDAN": [3.2730, -76.5350],
    "TERRANOVA": [3.2690, -76.5315],
    "BONANZA": [3.2542, -76.5412],
    "ALFAGUARA": [3.2505, -76.5350],
    "VERDE ALFAGUARA": [3.2480, -76.5380],
    "PASADENA": [3.2580, -76.5380],
    "SACHAMATE": [3.2750, -76.5280],
    "PANGOLA": [3.2760, -76.5260],
    "CIUDAD SUR": [3.2530, -76.5450],
    "BELALCAZAR": [3.2620, -76.5330],
    "LAS ACACIAS": [3.2650, -76.5250],
    "LA ESPERANZA": [3.2680, -76.5380],
    "EL JARDIN": [3.2560, -76.5320],
    "CIRO VELASCO": [3.2590, -76.5300],
    "ARIZONA": [3.2510, -76.5390],
    "LOS CHALOS": [3.2550, -76.5490],
    "FARALLONES": [3.2600, -76.5500],
    "VILLA COLOMBIA": [3.2650, -76.5420],
    "SANTUARIO": [3.2680, -76.5450],
    "ZARAGOZA": [3.2700, -76.5400],
    "MANDARINOS": [3.2520, -76.5320],
    "COVICEDROS": [3.2540, -76.5300],

    // Nuevos Barrios y Urbanizaciones
    "JUAN PABLO II": [3.2670, -76.5280],
    "EL CAIRO": [3.2550, -76.5250],
    "LA PRADERA": [3.2620, -76.5180],
    "RINCON DE JAMUNDI": [3.2580, -76.5220],
    "CIUDAD COUNTRY": [3.2820, -76.5250],
    "CASTILA": [3.2830, -76.5260],
    "ARBOLEDA": [3.2780, -76.5300],
    "LAS FLORES": [3.2590, -76.5320],
    "SOLAR DE JAMUNDI": [3.2510, -76.5420],
    "PARQUE NATURA": [3.2880, -76.5320],
    "PAGOLA": [3.2760, -76.5260],
    "LOS NARANJOS": [3.2560, -76.5350],
    "MARBELLA": [3.2630, -76.5380],
    "TORRES DE JAMUNDI": [3.2580, -76.5310],
    "LIBERTADORES": [3.2620, -76.5350],
    "PRIMERO DE MAYO": [3.2650, -76.5390],
    "JALISCO": [3.2600, -76.5420],
    "OCEANO VERDE": [3.2450, -76.5550],
    "BOSQUELAGO": [3.2650, -76.5450],
    "CIUDAD DE DIOS": [3.2500, -76.5400],
    "CIUDADELA DEL VIENTO": [3.2700, -76.5300],
    "EL RODEO": [3.2550, -76.5500],
    "OPORTO": [3.2520, -76.5350],
    "LOS CINCO SOLES": [3.2450, -76.5400],
    "VERDI": [3.2480, -76.5420],
    "PARQUES": [3.2500, -76.5450],

    // Corregimientos / Zonas Rurales
    "POTRERITO": [3.2380, -76.5950],
    "QUINAMAYO": [3.2050, -76.5150],
    "VILLA PAZ": [3.1850, -76.4950],
    "ROBLES": [3.1600, -76.4800],
    "GUACHINTE": [3.1400, -76.5100],
    "SAN ISIDRO": [3.1900, -76.5500],
    "LA LIBERIA": [3.2100, -76.6200],
    "SAN ANTONIO": [3.2000, -76.6500],
    "AMPUDIA": [3.2500, -76.6000],
    "PASO DE LA BOLSA": [3.2450, -76.4750],
    "BOCAS DEL PALO": [3.2800, -76.4600],
    "TIMBA": [3.1050, -76.6150],
    "PUENTE VELEZ": [3.2200, -76.6800],
    "SAN VICENTE": [3.2800, -76.6500],
    "CHAGRES": [3.1850, -76.4750],
    "LA MESETA": [3.1650, -76.6400],
    "PEON": [3.2250, -76.6200],

    // Vías y otros
    "VIA CALI": [3.2850, -76.5250],
    "VIA CALI JAMUNDI": [3.2850, -76.5250],
    "VIA SANTANDER": [3.2400, -76.5300],
};

/**
 * Normaliza nombres (quita tildes y caracteres especiales)
 */
const normalizeText = (text) => {
    if (!text) return "";
    return text.toString()
        .toUpperCase()
        .normalize("NFD")
        .replace(/[\u0300-\u036f]/g, "")
        .trim();
};

/**
 * Obtiene coordenadas para un barrio con desplazamiento aleatorio (jitter)
 * para evitar solapamiento masivo.
 */
export const geocodeNeighborhood = (neighborhoodName) => {
    const normalized = normalizeText(neighborhoodName);

    // Buscar coincidencia exacta o parcial
    let baseCoords = NEIGHBORHOOD_COORDS["CENTRO"]; // Fallback
    let isFallback = true;

    const key = Object.keys(NEIGHBORHOOD_COORDS).find(k => {
        if (normalized === k) return true;
        return normalized.includes(k) && k.length > 3;
    });

    if (key) {
        baseCoords = NEIGHBORHOOD_COORDS[key];
        isFallback = false;
    }

    // Jitter dinámico: Más dispersión para el centro y corregimientos grandes
    // para evitar "clusters" que se ven poco realistas
    // 0.001 grados aprox 111 metros.
    const jitterFactor = isFallback || normalized === "CENTRO" || normalized === "POTRERITO" ? 0.008 : 0.003;

    const jitterLat = (Math.random() - 0.5) * jitterFactor;
    const jitterLng = (Math.random() - 0.5) * jitterFactor;

    return {
        lat: baseCoords[0] + jitterLat,
        lng: baseCoords[1] + jitterLng
    };
};
