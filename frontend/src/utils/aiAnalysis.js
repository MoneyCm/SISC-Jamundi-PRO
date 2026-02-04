export const analyzeData = async (data) => {
    // Simulate a short delay for "processing" feel, or remove if instant is preferred.
    await new Promise(resolve => setTimeout(resolve, 1500));

    if (!data || !Array.isArray(data)) return [];

    return data.map(item => {
        const issues = [];
        const corrections = [];
        let status = 'ok';
        let correctedItem = { ...item };

        // 1. Validate Date
        if (!item.fecha) {
            status = 'error';
            issues.push('Fecha faltante');
        } else {
            // Basic check if it looks like a date
            const date = new Date(item.fecha);
            if (isNaN(date.getTime())) {
                status = 'error';
                issues.push('Fecha inválida');
            }
        }

        // 2. Validate/Fix Type
        const validTypes = [
            'HOMICIDIO', 'HURTO A PERSONAS', 'HURTO A COMERCIO',
            'LESIONES PERSONALES', 'VIOLENCIA INTRAFAMILIAR', 'RIÑA',
            'HURTO', 'LESIONES', 'VIOLENCIA'
        ];

        const itemTipoUpper = (item.tipo || '').toString().toUpperCase();

        // Normalización Inteligente
        if (itemTipoUpper.startsWith('H.PERSONA') || itemTipoUpper === 'H. PERSONAS') {
            correctedItem.tipo = 'HURTO A PERSONAS';
            corrections.push('Tipo normalizado a HURTO A PERSONAS');
        } else if (itemTipoUpper.startsWith('H.COMERCIO') || itemTipoUpper === 'H. COMERCIO') {
            correctedItem.tipo = 'HURTO A COMERCIO';
            corrections.push('Tipo normalizado a HURTO A COMERCIO');
        } else if (itemTipoUpper.startsWith('H.RESIDENCIA')) {
            correctedItem.tipo = 'HURTO A RESIDENCIAS';
            corrections.push('Tipo normalizado a HURTO A RESIDENCIAS');
        } else if (itemTipoUpper.startsWith('LESIONES') || itemTipoUpper === 'L.PERSONALES') {
            correctedItem.tipo = 'LESIONES PERSONALES';
            corrections.push('Tipo normalizado a LESIONES PERSONALES');
        } else if (itemTipoUpper.includes('HOMICI')) {
            correctedItem.tipo = 'HOMICIDIO';
            corrections.push('Tipo normalizado a HOMICIDIO');
        }

        const finalTipo = correctedItem.tipo.toUpperCase();
        const isValidType = validTypes.some(vt => finalTipo.includes(vt));

        if (!isValidType && item.tipo) {
            status = 'warning';
            issues.push(`Tipo de delito no estándar: ${item.tipo}`);
        }

        // 3. Enrich/Fix Barrio (Capitalization)
        if (item.barrio && item.barrio !== 'undefined') {
            const capitalized = item.barrio.toString().replace(/\w\S*/g, (w) => (w.replace(/^\w/, (c) => c.toUpperCase())));
            if (capitalized !== item.barrio) {
                correctedItem.barrio = capitalized;
                corrections.push('Capitalización de barrio corregida');
                if (status === 'ok') status = 'warning';
            }
        } else {
            status = 'error';
            issues.push('Barrio faltante');
        }

        // 4. Description check
        if (!item.descripcion || item.descripcion.length < 3 || item.descripcion === 'undefined') {
            status = 'warning';
            issues.push('Descripción insuficiente');
        }

        // Construct message
        let message = 'Validado correctamente';
        if (issues.length > 0 || corrections.length > 0) {
            message = [...new Set([...issues, ...corrections])].join('. ');
        }

        return {
            original: item,
            corrected: correctedItem,
            status,
            message
        };
    });
};
