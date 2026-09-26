// Plan de acción del PISCC: textos y cálculos de la pantalla de seguimiento semestral.

export const ACTION_STATUS_LABELS = {
    SIN_INICIAR: 'Sin iniciar',
    EN_EJECUCION: 'En ejecución',
    CUMPLIDA: 'Cumplida',
    SUSPENDIDA: 'Suspendida',
};

export const semesterLabel = (semester) => {
    const [year, half] = String(semester || '').split('-');
    if (!year || !half) return semester || '';
    return `${half === '1' ? 'Primer' : 'Segundo'} semestre de ${year}`;
};

/** Qué se muestra del avance: el reporte del semestre o, si falta, el último anterior señalado. */
export const progressReading = (action) => {
    const report = action.report || action.last_report;
    if (!report) return { text: 'Sin reportes', tone: 'empty' };
    const value = report.value === null || report.value === undefined ? 'sin cifra' : String(report.value).replace('.', ',');
    const pct = action.progress_pct === null || action.progress_pct === undefined ? '' : ` · ${String(action.progress_pct).replace('.', ',')} %`;
    if (action.report) return { text: `${value} de ${action.goal}${pct}`, tone: 'current' };
    return { text: `${value} de ${action.goal}${pct} (último reporte: ${report.semester})`, tone: 'stale' };
};

export const emptyReport = (action) => {
    const base = action.report || action.last_report || {};
    return {
        value: base.value ?? '',
        status: base.status || 'EN_EJECUCION',
        reporting_entity: base.reporting_entity || action.lead_entity || '',
        evidence: action.report ? base.evidence || '' : '',
        note: action.report ? base.note || '' : '',
        received_on: action.report ? base.received_on || '' : '',
    };
};

export const reportPayload = (form, action) => ({
    value: form.value === '' || form.value === null ? null : Number(String(form.value).replace(',', '.')),
    status: form.status,
    reporting_entity: form.reporting_entity || null,
    evidence: form.evidence || null,
    note: form.note || null,
    received_on: form.received_on || null,
    expected_version: action.report ? action.report.version : null,
});
