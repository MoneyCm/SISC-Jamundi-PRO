"""Consultas de seguimiento del Consejo, independientes de la sábana policial."""
import unicodedata
from datetime import date

from db.models_council import CouncilCommitment
from services.council_commitments_service import CLOSED_STATUSES

MESES = ('enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto',
         'septiembre', 'octubre', 'noviembre', 'diciembre')
# Clave en la pregunta -> texto que aparece en el responsable del compromiso.
RESPONSABLES = {'policia': 'policia', 'ejercito': 'ejercito', 'movilidad': 'movilidad', 'personeria': 'personeria',
                'defensoria': 'defensoria', 'fiscalia': 'fiscalia', 'icbf': 'icbf', 'gobierno': 'gobierno',
                'secretaria de seguridad': 'seguridad', 'comisaria': 'comisaria', 'inspecc': 'inspec'}
MAX_LISTA = 6


def normalizar(texto):
    return ''.join(c for c in unicodedata.normalize('NFKD', (texto or '').lower()) if not unicodedata.combining(c))


def es_consulta(pregunta):
    return 'compromiso' in normalizar(pregunta)


def es_ranking(pregunta_normalizada):
    return es_consulta(pregunta_normalizada) and any(term in pregunta_normalizada for term in
        ('mas incumpl', 'mas vencido', 'mas atrasado', 'mas reiterado', 'mas repetido', 'mas pedido'))


def fecha(valor):
    return f'{valor.day} de {MESES[valor.month - 1]} de {valor.year}'


def veces(n):
    n = n or 1
    return f'{n} vez' if n == 1 else f'{n} veces'


def detalle(row):
    return (f'{row.code}: {row.text} Responsable: {row.responsible or "sin registrar"}. '
            f'Pedido {veces(row.mentions)}. Acta de origen: {row.origin_act or "sin registrar"}.')


def empate(rows, hoy, atraso=False):
    actas = {r.origin_act for r in rows}
    acta = f' del {next(iter(actas))}' if len(actas) == 1 and None not in actas and '' not in actas else ' de varias actas'
    texto = f'{len(rows)} compromisos{acta} siguen abiertos'
    if atraso:
        plazo = rows[0].deadline_date
        texto += f' con plazo vencido el {fecha(plazo)} ({(hoy - plazo).days} días de atraso).'
    else:
        texto += f', pedidos {veces(rows[0].mentions)} cada uno.'
    return texto


def _abiertos(rows):
    return [r for r in rows if (r.instance or 'CONSEJO_SEGURIDAD') == 'CONSEJO_SEGURIDAD'
            and (r.kind or 'COMPROMISO') == 'COMPROMISO' and r.status not in CLOSED_STATUSES]


def _vencido(row, hoy):
    return bool(row.deadline_date and row.deadline_date < hoy)


def resumir(rows, hoy: date, por_atraso=False):
    abiertos = _abiertos(rows)
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
    vencidos = [r for r in abiertos if _vencido(r, hoy)]
    if vencidos:
        plazo = min(r.deadline_date for r in vencidos)
        atrasados = sorted([r for r in vencidos if r.deadline_date == plazo], key=lambda r: r.code)
        atraso = 'Mayor atraso: ' + (empate(atrasados, hoy, atraso=True) if len(atrasados) > 1 else
            detalle(atrasados[0]) + f' Plazo vencido el {fecha(plazo)} ({(hoy - plazo).days} días de atraso).')
    else:
        atraso = 'No hay compromisos abiertos con fecha límite vencida.'
    bloques = [atraso, reiteracion] if por_atraso else [reiteracion, atraso]
    return '\n\n'.join(bloques + ['Las reiteraciones son veces que se ha pedido el compromiso, no incumplimientos comprobados.'])


def listar(rows, hoy: date, quien: str, solo_vencidos=False):
    """Los compromisos abiertos (o solo los vencidos) de una entidad o del Consejo, los más urgentes primero."""
    abiertos = _abiertos(rows)
    vencidos = [r for r in abiertos if _vencido(r, hoy)]
    if not abiertos:
        return f'No hay compromisos abiertos del Consejo de Seguridad a cargo de {quien}.'
    cabeza = (f'{quien[:1].upper()}{quien[1:]} tiene {len(abiertos)} compromisos abiertos del Consejo de Seguridad; '
              f'{len(vencidos)} con el plazo vencido.')
    lista = vencidos if solo_vencidos else abiertos
    if not lista:
        return cabeza + '\n\nNinguno tiene el plazo vencido.'
    # Vencidos primero (el más antiguo arriba), luego los más pedidos.
    lista = sorted(lista, key=lambda r: (not _vencido(r, hoy), r.deadline_date or date.max, -(r.mentions or 1), r.code))
    lineas = []
    for r in lista[:MAX_LISTA]:
        if _vencido(r, hoy):
            plazo = f'plazo vencido el {fecha(r.deadline_date)}, {(hoy - r.deadline_date).days} días de atraso'
        elif r.deadline_date:
            plazo = f'plazo: {fecha(r.deadline_date)}'
        else:
            plazo = 'sin fecha límite registrada'
        lineas.append(f'• {r.code}: {r.text} (pedido {veces(r.mentions)}; {plazo}).')
    faltan = len(lista) - MAX_LISTA
    if faltan > 0:
        lineas.append(f'Y {faltan} más: la lista completa está en Compromisos del Consejo.')
    return cabeza + '\n\n' + '\n'.join(lineas)


def responder_ranking(db, pregunta_normalizada, hoy):
    rows = db.query(CouncilCommitment).filter(CouncilCommitment.instance == 'CONSEJO_SEGURIDAD',
                                             CouncilCommitment.kind == 'COMPROMISO').all()
    # Honor named institutions without mixing their commitments with the full council.
    responsables = [clave for clave in RESPONSABLES if clave in pregunta_normalizada]
    if responsables:
        rows = [r for r in rows if any(RESPONSABLES[c] in normalizar(r.responsible) for c in responsables)]
    if es_ranking(pregunta_normalizada):
        respuesta = resumir(rows, hoy, por_atraso=any(w in pregunta_normalizada for w in ('mas atrasado', 'mas vencido')))
    else:
        quien = ', '.join({'policia': 'la Policía', 'ejercito': 'el Ejército', 'fiscalia': 'la Fiscalía',
                           'secretaria de seguridad': 'la Secretaría de Seguridad', 'gobierno': 'la Secretaría de Gobierno',
                           'inspecc': 'las Inspecciones'}.get(c, c.capitalize()) for c in responsables) or 'el Consejo en total'
        respuesta = listar(rows, hoy, quien, solo_vencidos=any(w in pregunta_normalizada for w in ('vencid', 'atrasad', 'incumpl')))
    return {'respuesta': respuesta + f'\n\nSeguimiento consultado: {fecha(hoy)}.',
            'verificada': True, 'redactada_por': 'SISC (sin IA)',
            'fuentes': ['Registro de compromisos y actas del Consejo de Seguridad'],
            'sugerencias': ['¿Cuál es el compromiso más reiterado del Consejo de Seguridad?',
                            '¿Cuál es el compromiso más atrasado del Consejo de Seguridad?',
                            '¿Qué compromisos tiene vencidos la Policía?'],
            'temas': {'delitos': [], 'barrios': [], 'entidades': responsables, 'seguimiento': ['CONSEJO_SEGURIDAD']}}
