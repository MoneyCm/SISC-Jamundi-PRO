// Estudios del Observatorio: textos, orden del trabajo de campo y datos que se envían al guardar.

export const FIELD_NOTE_KINDS = {
    ENTREVISTA: 'Entrevista',
    RECORRIDO: 'Recorrido',
    GRUPO_FOCAL: 'Grupo focal',
    REUNION: 'Reunión',
    OTRO: 'Otro',
};

/** Más reciente primero; a igual fecha, el último registrado primero. */
export const sortFieldNotes = (notes = []) => [...notes].sort((a, b) => (
    b.on_date.localeCompare(a.on_date) || String(b.at || '').localeCompare(String(a.at || ''))
));

/** Cuerpo del PUT de un estudio: los campos editables más la versión esperada. */
export const studyUpdate = (study, changes) => {
    const {
        id, code, version, created_by, updated_by, created_at, updated_at, recommendations,
        recommendations_count, field_notes, ...fields
    } = study;
    const body = { ...fields, ...changes, expected_version: version };
    for (const key of ['findings', 'associated_factors', 'review_on', 'status_note']) {
        if (body[key] === '') body[key] = null;
    }
    if (body.status !== 'PAUSADO') body.status_note = null;
    return body;
};

export const reviewLabel = (study, today) => {
    if (!study.review_on) return '';
    if (study.review_on <= today) return 'Revisión posterior pendiente';
    const [year, month, day] = study.review_on.split('-');
    return `Revisión posterior: ${day}/${month}/${year}`;
};
