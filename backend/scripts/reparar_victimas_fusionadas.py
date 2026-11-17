"""Recupera en la tabla maestra las víctimas que la carga fundió en una sola fila.

Antes del arreglo de la huella por víctima, dos víctimas del mismo hecho con igual sexo, edad, fecha,
conducta y arma quedaban como UNA fila en hechos_seguridad, aunque la foto de la entrega
(sabana_snapshot_rows) sí traía las dos. Este script compara, para cada entrega, la foto contra la
tabla maestra y crea las filas que faltan, con la misma huella que hoy les daría la carga.

Uso (dentro del contenedor):  python -m scripts.reparar_victimas_fusionadas          -> solo muestra
                              python -m scripts.reparar_victimas_fusionadas --aplicar -> guarda
"""
import sys
import uuid

from sqlalchemy import func, inspect

import db.models_dq  # noqa: F401
from db.models_hechos_seguridad import HechoSeguridad, SabanaSnapshotRow
from db.session import SessionLocal
from services.excel_policia_processor import PoliciaJamundiProcessor

GRUPO = ("id_fuente", "conducta_estandar", "fecha_evento", "sexo", "edad", "arma_medio")


def _conteos(db, model, extra=None):
    columnas = [model.ingestion_id] + [getattr(model, c) for c in GRUPO]
    consulta = db.query(*columnas, func.count()).filter(model.id_fuente.isnot(None))
    if extra is not None:
        consulta = consulta.filter(extra)
    return {tuple(fila[:-1]): fila[-1] for fila in consulta.group_by(*columnas).all()}


def faltantes(db):
    maestra = _conteos(db, HechoSeguridad, HechoSeguridad.fuente_codigo == "POLICIA_SEMANAL")
    entregas = {clave[0] for clave in maestra}
    foto = _conteos(db, SabanaSnapshotRow, SabanaSnapshotRow.ingestion_id.in_(entregas))
    resultado, dudosos = [], []
    for clave, en_foto in foto.items():
        en_maestra = maestra.get(clave, 0)
        if en_foto <= en_maestra or en_maestra == 0:
            continue
        if en_maestra > 1:
            dudosos.append(clave)
            continue
        resultado.append((clave, en_foto))
    return resultado, dudosos


def reparar(db, aplicar=False):
    pendientes, dudosos = faltantes(db)
    columnas = [c.key for c in inspect(HechoSeguridad).mapper.column_attrs if c.key not in ("id", "fingerprint")]
    creadas = []
    for clave, en_foto in pendientes:
        filtro = [HechoSeguridad.ingestion_id == clave[0], HechoSeguridad.fuente_codigo == "POLICIA_SEMANAL"]
        filtro += [getattr(HechoSeguridad, c) == v for c, v in zip(GRUPO, clave[1:])]
        original = db.query(HechoSeguridad).filter(*filtro).one()
        for ocurrencia in range(2, en_foto + 1):
            huella = PoliciaJamundiProcessor.huella_de_victima(original.fingerprint, ocurrencia)
            if db.query(HechoSeguridad.id).filter(HechoSeguridad.fingerprint == huella).first():
                continue
            copia = HechoSeguridad(id=uuid.uuid4(), fingerprint=huella,
                                   **{c: getattr(original, c) for c in columnas})
            db.add(copia)
            creadas.append((clave[1], clave[2], str(clave[3]), ocurrencia))
    if aplicar:
        db.commit()
    else:
        db.rollback()
    return creadas, dudosos


if __name__ == "__main__":
    aplicar = "--aplicar" in sys.argv
    with SessionLocal() as sesion:
        creadas, dudosos = reparar(sesion, aplicar)
    for hecho, conducta, fecha, ocurrencia in creadas:
        print(f"{'Creada' if aplicar else 'Faltante'}: hecho {hecho} ({conducta}, {fecha}) víctima #{ocurrencia}")
    for clave in dudosos:
        print(f"Revisar a mano (varias filas en la maestra): {clave[1:]}")
    print(f"Total: {len(creadas)} víctimas {'recuperadas' if aplicar else 'por recuperar (use --aplicar)'}")
