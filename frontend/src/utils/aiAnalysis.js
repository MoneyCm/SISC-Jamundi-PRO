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
            'LESIONES PERSONALES', 'VIOLENCIA INTRAFAMILIAR', 'RIÑA'
        ];

        if (!validTypes.includes(item.tipo)) {
            // Simple fuzzy match or correction logic could go here
            // For now, just mark as warning if unknown
            status = 'warning';
            issues.push(`Tipo de delito no estándar: ${item.tipo}`);
        }

        // 3. Enrich/Fix Barrio (Capitalization)
        if (item.barrio) {
            const capitalized = item.barrio.replace(/\w\S*/g, (w) => (w.replace(/^\w/, (c) => c.toUpperCase())));
            if (capitalized !== item.barrio) {
                correctedItem.barrio = capitalized;
                corrections.push('Capitalización de barrio corregida');
                if (status === 'ok') status = 'warning'; // Show as a change
            }
        } else {
            status = 'error';
            issues.push('Barrio faltante');
        }

        // 4. Description check
        if (!item.descripcion || item.descripcion.length < 5) {
            status = 'warning';
            issues.push('Descripción muy corta o faltante');
        }

        // Construct message
        let message = 'Validado correctamente';
        if (issues.length > 0 || corrections.length > 0) {
            message = [...issues, ...corrections].join('. ');
        }

        return {
            original: item,
            corrected: correctedItem,
            status,
            message
        };
    });
};
