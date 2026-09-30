"""Consultas de seguimiento del Consejo, independientes de la sábana policial."""
import unicodedata
from datetime import date

from db.models_council import CouncilCommitment
from services.council_commitments_service import CLOSED_STATUSES

MESES = ('enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto',
         'septiembre', 'octubre', 'noviembre', 'diciembre')


def normalizar(texto):
    return ''.join(c for c in unicodedata.normalize('NFKD', (texto or '').lower()) if not unicodedata.combining(c))


def es_consulta(pregunta):
    return 'compromiso' in normalizar(pregunta)


def es_ranking(pregunta_normalizada):
    return es_consulta(pregunta_normalizada) and any(term in pregunta_normalizada for term in
        ('mas incumpl', 'mas vencido', 'mas atrasado', 'mas reiterado', 'mas repetido', 'mas pedido'))


def fecha(valor):
    return f'{valor.day} de {MESES[valor.month - 1]} de {valor.year}'


def detalle(row):
    return (f'{row.code}: {row.text} Responsable: {row.responsible or "sin registrar"}. '
            f'Pedido {row.mentions or 1} veces. Acta de origen: {row.origin_act or "sin registrar"}.')


def empate(rows, hoy, atraso=False):
    actas = {r.origin_act for r in rows}
    acta = f' del {next(iter(actas))}' if len(actas) == 1 and None not in actas and '' not in actas else ' de varias actas'
    texto = f'{len(rows)} compromisos{acta} siguen abiertos'
    if atraso:
        plazo = rows[0].deadline_date
        texto += f' con plazo vencido el {fecha(plazo)} ({(hoy - plazo).days} días de atraso).'
    else:
        texto += f', pedidos {rows[0].mentions or 1} veces cada uno.'
    return texto


def resumir(rows, hoy: date, por_atraso=False):
    abiertos = [r for r in rows if (r.instance or 'CONSEJO_SEGURIDAD') == 'CONSEJO_SEGURIDAD'
                and (r.kind or 'COMPROMISO') == 'COMPROMISO' and r.status not in CLOSED_STATUSES]
    if not abiertos:
        return 'No hay compromisos abiertos del Consejo de Seguridad en los registros consultados.'
    maximo = max(r.mentions or 1 for r in abiertos)
    reiterados = sorted([r for r in abiertos if (r.mentions or 1) == maximo], key=lambda r: r.code)
    if len(reiterados) == 1:
        row = reiterados[0]
        reiteracion = 'Más reiterado entre los abiertos: ' + detalle(row)
        reiteracion += f' Plazo: {fecha(row.deadline_date)}.' if row.deadline_date else ' Sin fecha límite registrada.'
    else:
        reiteracion = 'Mayor reiteración: ' + empate(reiterados, hoy)
    vencidos = [r for r in abiertos if r.deadline_date and r.deadline_date < hoy]
    if vencidos:
        plazo = min(r.deadline_date for r in vencidos)
        atrasados = sorted([r for r in vencidos if r.deadline_date == plazo], key=lambda r: r.code)
        atraso = 'Mayor atraso: ' + (empate(atrasados, hoy, atraso=True) if len(atrasados) > 1 else
            detalle(atrasados[0]) + f' Plazo vencido el {fecha(plazo)} ({(hoy - plazo).days} días de atraso).')
    else:
        atraso = 'No hay compromisos abiertos con fecha límite vencida.'
    bloques = [atraso, reiteracion] if por_atraso else [reiteracion, atraso]
    return '\n\n'.join(bloques + ['Las reiteraciones son veces que se ha pedido el compromiso, no incumplimientos comprobados.'])


def responder_ranking(db, pregunta_normalizada, hoy):
    rows = db.query(CouncilCommitment).filter(CouncilCommitment.instance == 'CONSEJO_SEGURIDAD',
                                             CouncilCommitment.kind == 'COMPROMISO').all()
    # Honor named institutions without mixing their commitments with the full council.
    responsables = [nombre for nombre in ('policia', 'ejercito', 'movilidad', 'personeria', 'defensoria', 'fiscalia', 'icbf')
                    if nombre in pregunta_normalizada]
    if responsables:
        rows = [r for r in rows if any(nombre in normalizar(r.responsible) for nombre in responsables)]
    respuesta = resumir(rows, hoy, por_atraso=any(w in pregunta_normalizada for w in ('mas atrasado', 'mas vencido')))
    return {'respuesta': respuesta + f'\n\nSeguimiento consultado: {hoy.isoformat()}.',
            'verificada': True, 'redactada_por': 'SISC (sin IA)',
            'fuentes': ['Registro de compromisos y actas del Consejo de Seguridad'],
            'sugerencias': ['¿Cuál es el compromiso más reiterado del Consejo de Seguridad?',
                            '¿Cuál es el compromiso más atrasado del Consejo de Seguridad?'],
            'temas': {'delitos': [], 'barrios': [], 'entidades': responsables, 'seguimiento': ['CONSEJO_SEGURIDAD']}}
