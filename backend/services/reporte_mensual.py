"""Reporte mensual para la Secretaria: metas del PISCC y respuesta judicial de la Fiscalía, en cuadros.

Complementa el reporte semanal (services/reporte_semanal.py). Estas fuentes se publican una vez al mes, así
que no van en el semanal: MinDefensa (metas del PISCC), RNMC (convivencia) y la Fiscalía (SPOA, datos.gov.co).
Cada cuadro lleva su propia fuente y fecha de corte. Sin IA.
"""
from datetime import date
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
         "noviembre", "diciembre"]
PALABRAS = ("reporte mensual", "informe mensual", "reporte del mes", "informe del mes")


def pide_reporte(p: str) -> bool:
    return any(w in p for w in PALABRAS)


def _fecha(iso: Optional[str]) -> Optional[str]:
    if not iso:
        return None
    d = date.fromisoformat(str(iso)[:10])
    return f"{d.day} de {MESES[d.month - 1]} de {d.year}"


def _metas(db: Session, hoy: date) -> List[Dict]:
    from services.piscc_goals import build_goals
    filas = []
    for g in build_goals(db, hoy, None).get("indicators", []):
        reciente = g.get("reciente") or {}
        filas.append({
            "nombre": g.get("label"), "van": g.get("count"), "anterior": g.get("previous"),
            "limite": g.get("goal_2027"), "estado": g.get("status"), "estado_texto": g.get("status_label"),
            "detalle": g.get("detail"), "corte": g.get("cutoff"), "fuente": g.get("source"),
            "reciente": ({"van": reciente.get("count"), "corte": reciente.get("cutoff")}
                         if reciente.get("count") is not None else None),
        })
    return filas


def _fiscalia(db: Session) -> Optional[Dict]:
    from db.models_source_center import SourceConnectorState
    from services.fiscalia_datos_sync import CONECTOR
    estado = db.get(SourceConnectorState, CONECTOR)
    seguimiento = (estado.details or {}).get("seguimiento") if estado else None
    if not seguimiento:
        return None
    en_curso = str(seguimiento.get("anio_en_curso"))
    anios = [str(a) for a in seguimiento.get("anios", []) if str(a) != en_curso]
    filas = []
    for nombre, clave in (("Todos los delitos", "todos"), ("Homicidio doloso", "homicidio_doloso")):
        for anio in anios:
            f = (seguimiento.get(clave) or {}).get(anio) or {}
            if f.get("total"):
                filas.append({"nombre": nombre, "anio": anio, "procesos": f["total"],
                              "juicio_o_condena": f["juicio_o_condena"],
                              "porcentaje": round(100 * f["juicio_o_condena"] / f["total"], 1)})
    return {"filas": filas, "corte": estado.source_cutoff_date.isoformat() if estado.source_cutoff_date else None,
            "nota": f"Se cuentan procesos, no homicidios: un hecho puede abrir varios. Los procesos de {en_curso} "
                    "son muy recientes para medir resultados. El avance depende de la Fiscalía y los jueces."}


def generar(db: Session, hoy: Optional[date] = None) -> Optional[Dict]:
    hoy = hoy or date.today()
    metas = _metas(db, hoy)
    if not metas:
        return None
    fiscalia = _fiscalia(db)
    cortes_md = sorted({m["corte"] for m in metas if m["corte"] and m["fuente"] and "MinDefensa" in m["fuente"]})
    fuentes = []
    if cortes_md:
        fuentes.append(f"Metas: MinDefensa / Policía Nacional, hasta el {_fecha(cortes_md[-1])}")
    conv = next((m for m in metas if m["fuente"] and "RNMC" in m["fuente"]), None)
    if conv:
        fuentes.append(f"Convivencia: RNMC / Inspecciones de Policía, hasta el {_fecha(conv['corte'])}")
    if fiscalia and fiscalia["corte"]:
        fuentes.append(f"Fiscalía: SPOA en datos.gov.co, corte al {_fecha(fiscalia['corte'])}")
    return {
        "titulo": "Reporte mensual de seguridad",
        "subtitulo": f"Metas del PISCC {hoy.year} y respuesta judicial",
        "fecha": _fecha(hoy.isoformat()),
        "fecha_iso": hoy.isoformat(),
        "anio": hoy.year,
        "anio_anterior": hoy.year - 1,
        "metas": metas,
        "fiscalia": fiscalia,
        "fuentes": fuentes,
        "notas": ["Cada fuente tiene su propia fecha de corte.",
                  "Metas del PISCC 2024-2027: límite anual de casos; el estado compara lo que va del año con ese límite."],
    }


def texto(reporte: Dict) -> str:
    """Versión en texto, para copiar o enviar por WhatsApp."""
    lineas = [f"*{reporte['titulo']}*", reporte["subtitulo"], "", "*Metas del PISCC*"]
    for m in reporte["metas"]:
        reciente = (f" Registro semanal de la Policía al {_fecha(m['reciente']['corte'])}: {m['reciente']['van']}."
                    if m.get("reciente") else "")
        lineas.append(f"• {m['nombre']}: {m['van']} (límite anual {m['limite']}) — {m['estado_texto']}.{reciente}")
    if reporte.get("fiscalia"):
        lineas += ["", "*Fiscalía: procesos que llegaron a juicio o condena*"]
        for f in reporte["fiscalia"]["filas"]:
            pct = str(f["porcentaje"]).replace(".", ",")
            lineas.append(f"• {f['nombre']}, hechos de {f['anio']}: {f['juicio_o_condena']} de {f['procesos']} ({pct} %).")
    lineas += ["", "Fuentes: " + "; ".join(reporte["fuentes"]) + "."]
    return "\n".join(lineas)
