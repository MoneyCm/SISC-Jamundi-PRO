import React, { useState } from 'react';
import { Loader2, Plus, Trash2 } from 'lucide-react';
import { apiJson } from '../utils/apiClient';
import { localToday } from '../utils/localDate';
import { FIELD_NOTE_KINDS, sortFieldNotes } from '../utils/studies';

const inputClass = 'w-full border border-slate-300 bg-white px-3 py-2 text-sm font-semibold text-slate-900 focus:border-[#281FD0] focus:outline-none';
const formatDate = (value) => new Intl.DateTimeFormat('es-CO', { day: 'numeric', month: 'short', year: 'numeric' }).format(new Date(`${value}T12:00:00`));

/** Trabajo de campo de un estudio: entrevistas, recorridos, grupos focales y reuniones. */
const StudyFieldNotes = ({ study, canEdit, onChanged }) => {
    const [adding, setAdding] = useState(false);
    const [form, setForm] = useState({ kind: 'ENTREVISTA', on_date: localToday(), place: '', participants: '', summary: '' });
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState('');
    const set = (field) => (event) => setForm((current) => ({ ...current, [field]: event.target.value }));
    const notes = sortFieldNotes(study.field_notes);

    const save = async (event) => {
        event.preventDefault();
        setSaving(true);
        setError('');
        try {
            await apiJson(`/observatory/studies/${study.id}/field-notes`, {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ ...form, place: form.place || null, participants: form.participants || null }),
            });
            setAdding(false);
            setForm((current) => ({ ...current, place: '', participants: '', summary: '' }));
            onChanged();
        } catch (saveError) {
            setError(saveError.message);
        } finally {
            setSaving(false);
        }
    };
    const remove = async (note) => {
        if (!window.confirm('¿Borrar esta nota de campo?')) return;
        try {
            await apiJson(`/observatory/studies/${study.id}/field-notes/${note.id}`, { method: 'DELETE' });
            onChanged();
        } catch (removeError) {
            setError(removeError.message);
        }
    };

    return (
        <section className="space-y-2">
            <div className="flex items-center justify-between gap-2">
                <h4 className="text-xs font-black uppercase tracking-wide text-slate-600">Trabajo de campo ({notes.length})</h4>
                {canEdit && !adding && (
                    <button onClick={() => setAdding(true)} className="inline-flex items-center gap-1 text-sm font-black text-[#281FD0] hover:underline"><Plus size={15} /> Agregar nota</button>
                )}
            </div>
            {!notes.length && !adding && <p className="text-sm font-semibold text-slate-500">Sin entrevistas ni recorridos registrados.</p>}
            <ul className="space-y-2">
                {notes.map((note) => (
                    <li key={note.id} className="border-l-4 border-slate-300 bg-slate-50 px-3 py-2">
                        <div className="flex items-start justify-between gap-2">
                            <p className="text-xs font-black text-slate-600">
                                {FIELD_NOTE_KINDS[note.kind]} · {formatDate(note.on_date)}{note.place ? ` · ${note.place}` : ''}{note.participants ? ` · ${note.participants}` : ''}
                            </p>
                            {canEdit && <button onClick={() => remove(note)} aria-label="Borrar nota" className="text-slate-400 hover:text-red-700"><Trash2 size={14} /></button>}
                        </div>
                        <p className="mt-1 whitespace-pre-line text-sm font-semibold text-slate-800">{note.summary}</p>
                        <p className="mt-1 text-[11px] font-semibold text-slate-400">Registró {note.by}</p>
                    </li>
                ))}
            </ul>
            {adding && (
                <form onSubmit={save} className="grid gap-3 border border-slate-200 bg-white p-3 md:grid-cols-2">
                    <label className="block">
                        <span className="text-xs font-black uppercase tracking-wide text-slate-600">Tipo</span>
                        <select className={`${inputClass} mt-1`} value={form.kind} onChange={set('kind')}>
                            {Object.entries(FIELD_NOTE_KINDS).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                        </select>
                    </label>
                    <label className="block">
                        <span className="text-xs font-black uppercase tracking-wide text-slate-600">Fecha</span>
                        <input type="date" required className={`${inputClass} mt-1`} value={form.on_date} onChange={set('on_date')} />
                    </label>
                    <label className="block">
                        <span className="text-xs font-black uppercase tracking-wide text-slate-600">Lugar</span>
                        <input className={`${inputClass} mt-1`} value={form.place} onChange={set('place')} maxLength={200} placeholder="Barrio, vereda o sede" />
                    </label>
                    <label className="block">
                        <span className="text-xs font-black uppercase tracking-wide text-slate-600">Con quién</span>
                        <input className={`${inputClass} mt-1`} value={form.participants} onChange={set('participants')} maxLength={300} placeholder="Roles, no nombres: líder comunal, comerciante…" />
                    </label>
                    <label className="block md:col-span-2">
                        <span className="text-xs font-black uppercase tracking-wide text-slate-600">Qué se encontró</span>
                        <textarea required minLength={10} rows={3} className={`${inputClass} mt-1`} value={form.summary} onChange={set('summary')} maxLength={5000} />
                        <span className="mt-1 block text-xs font-semibold text-slate-500">No escriba nombres ni datos que identifiquen a las personas.</span>
                    </label>
                    {error && <p role="alert" className="bg-red-50 p-2 text-sm font-bold text-red-800 md:col-span-2">{error}</p>}
                    <div className="flex gap-2 md:col-span-2">
                        <button type="submit" disabled={saving} className="inline-flex min-h-10 items-center gap-2 bg-[#281FD0] px-4 text-sm font-black text-white disabled:opacity-60">
                            {saving && <Loader2 size={15} className="animate-spin" />} Guardar nota
                        </button>
                        <button type="button" onClick={() => setAdding(false)} className="min-h-10 border border-slate-300 px-4 text-sm font-bold text-slate-700">Cancelar</button>
                    </div>
                </form>
            )}
            {error && !adding && <p role="alert" className="text-sm font-bold text-red-700">{error}</p>}
        </section>
    );
};

export default StudyFieldNotes;
