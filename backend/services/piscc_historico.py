"""Años cerrados de las metas del PISCC (2024, 2025...) y su semáforo frente a la meta de 2027.

La línea base del PISCC (2023) sale de los datos abiertos de MinDefensa en datos.gov.co: homicidios 115,
lesiones 453, motos 200, extorsión 58 y violencia intrafamiliar 187 coinciden exactamente con esa fuente.
Por eso los años cerrados se miden con la misma fuente, año completo (enero a diciembre), y no con la
sábana, que en 2024 y 2025 no trae diciembre. Convivencia sale del RNMC cargado en el SISC.

Semáforo de un año cerrado:
- VERDE: la cifra ya está en la meta de 2027 o por debajo.
- AMARILLO: mejor que la línea base de 2023, pero todavía por encima de la meta.
- ROJO: igual o peor que la línea base de 2023.

Se guarda en data/piscc/historico.json y se actualiza con la revisión semanal de MinDefensa (main.py).
"""
import json
import logging
import urllib.parse
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Callable, Dict, List, Optional

ARCHIVO = Path(__file__).resolve().parents[1] / "data" / "piscc" / "historico.json"
DANE_JAMUNDI = "76364"
DESDE = 2023
# id de la meta -> (conjunto en datos.gov.co, filtro adicional)
CONJUNTOS = {
    "homicidios": ("m8fd-ahd9", ""),
    "secuestro": ("d7zw-hpf4", ""),
    "extorsion": ("q2ib-t9am", ""),
    "vif": ("gepp-dxcs", ""),
    "motos": ("csb4-y6v2", " AND tipo_delito like '%MOTOCICLETAS%'"),
    "lesiones": ("jr6v-i33g", ""),
}
FUENTE = "MinDefensa / Policía Nacional (datos.gov.co), año completo"
SEMAFORO = {
    "VERDE": "En la meta",
    "AMARILLO": "Mejor que 2023, sin llegar a la meta",
    "ROJO": "Igual o peor que la línea base 2023",
}

logger = logging.getLogger("piscc_historico")


def consultar(dataset: str, **parametros) -> List[dict]:
    url = f"https://www.datos.gov.co/resource/{dataset}.json?" + urllib.parse.urlencode(parametros)
    with urllib.request.urlopen(url, timeout=120) as respuesta:
        return json.loads(respuesta.read())


def semaforo(valor: Optional[int], linea_base: int, meta: int) -> Optional[str]:
    if valor is None:
        return None
    if valor <= meta:
        return "VERDE"
    if valor < linea_base:
        return "AMARILLO"
    return "ROJO"


def mensual(dataset: str, filtro: str, consulta: Callable = consultar) -> Dict[str, Dict[str, int]]:
    """{"2024": {"1": n, ..., "12": n}, ...} desde DESDE, con los meses que publica MinDefensa."""
    filas = consulta(dataset, **{
        "$select": "date_extract_y(fecha_hecho) as anio, date_extract_m(fecha_hecho) as mes, sum(cantidad) as total",
        "$where": f"cod_muni='{DANE_JAMUNDI}' AND fecha_hecho >= '{DESDE}-01-01'{filtro}",
        "$group": "anio, mes", "$order": "anio, mes", "$limit": 5000,
    })
    datos: Dict[str, Dict[str, int]] = {}
    for fila in filas:
        datos.setdefault(str(int(fila["anio"])), {})[str(int(fila["mes"]))] = int(float(fila["total"]))
    return datos


def actualizar(consulta: Callable = consultar, archivo: Path = ARCHIVO) -> Dict:
    """Consulta los seis conjuntos y reescribe el archivo (solo si todos respondieron)."""
    series = {clave: mensual(dataset, filtro, consulta) for clave, (dataset, filtro) in CONJUNTOS.items()}
    ultimo = max((date(int(a), int(max(meses, key=int)), 1) for s in series.values() for a, meses in s.items()), default=None)
    datos = {"actualizado": datetime.now(timezone.utc).isoformat(), "fuente": FUENTE,
             "ultimo_mes": ultimo.isoformat()[:7] if ultimo else None, "series": series}
    archivo.write_text(json.dumps(datos, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return datos


def cargar(archivo: Path = ARCHIVO) -> Optional[Dict]:
    if not archivo.exists():
        return None
    return json.loads(archivo.read_text(encoding="utf-8"))


def _ultimo_publicado(datos: Optional[Dict]):
    """(año, mes) del último mes que publica MinDefensa. Los meses sin casos no aparecen: valen 0."""
    ultimo = (datos or {}).get("ultimo_mes")
    return (int(ultimo[:4]), int(ultimo[5:7])) if ultimo else None


def anios_cerrados(clave: str, linea_base: int, meta: int, hoy: Optional[date] = None, datos: Optional[Dict] = None) -> List[Dict]:
    """Años completos entre 2024 y el año pasado, con su semáforo. Un año sin los 12 meses no se califica."""
    hoy = hoy or date.today()
    datos = datos if datos is not None else cargar()
    serie = ((datos or {}).get("series") or {}).get(clave) or {}
    resultado = []
    publicado = _ultimo_publicado(datos)
    for anio in range(2024, hoy.year):
        meses = serie.get(str(anio)) or {}
        completo = bool(publicado) and (anio < publicado[0] or publicado[1] == 12)
        total = sum(meses.values()) if completo else (sum(meses.values()) if meses else None)
        estado = semaforo(total, linea_base, meta) if completo else None
        resultado.append({"anio": anio, "total": total, "completo": bool(completo), "semaforo": estado,
                          "semaforo_label": SEMAFORO.get(estado) if estado else "Sin año completo"})
    return resultado


def serie_mensual(clave: str, anio: int, datos: Optional[Dict] = None) -> List[int]:
    datos = datos if datos is not None else cargar()
    meses = (((datos or {}).get("series") or {}).get(clave) or {}).get(str(anio)) or {}
    publicado = _ultimo_publicado(datos)
    if not publicado:
        return [meses.get(str(m)) for m in range(1, 13)]
    hasta = 12 if anio < publicado[0] else (publicado[1] if anio == publicado[0] else 0)
    return [meses.get(str(m), 0) if m <= hasta else None for m in range(1, 13)]


def actualizar_si_toca(dias: int = 7, archivo: Path = ARCHIVO) -> Optional[Dict]:
    """Lo llama la revisión semanal de main.py: vuelve a consultar si el archivo tiene más de `dias`."""
    datos = cargar(archivo)
    if datos and datos.get("actualizado"):
        edad = datetime.now(timezone.utc) - datetime.fromisoformat(datos["actualizado"])
        if edad.days < dias:
            return None
    try:
        return actualizar(archivo=archivo)
    except Exception as error:  # noqa: BLE001 - sin red se conserva lo anterior
        logger.warning(f"[PISCC histórico] No se pudo consultar datos.gov.co: {error}")
        return None


MESES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
# Metas medidas con la sábana en el año en curso: su detalle trae barrios y horario.
CONDUCTAS_SABANA = {"homicidios": ["Homicidio"], "motos": ["Hurto a motocicletas"], "lesiones": ["Lesiones personales"]}


def _detalle_sabana(db, conductas: List[str], hoy: date) -> Dict:
    from sqlalchemy import func

    from db.models_hechos_seguridad import HechoSeguridad as H
    from services.entrega_vigente import filtro_hechos
    from services.hechos_metrics import hechos_unicos_expr

    base = [H.fuente_codigo == "POLICIA_SEMANAL", H.conducta_estandar.in_(conductas), filtro_hechos(db)]
    corte = db.query(func.max(H.fecha_evento)).filter(*base, H.fecha_evento <= hoy).scalar()
    if not corte:
        return {}
    en_anio = base + [H.fecha_evento.between(date(corte.year, 1, 1), corte)]
    barrios = (db.query(H.barrio_normalizado, hechos_unicos_expr().label("n")).filter(*en_anio, H.barrio_normalizado.isnot(None))
               .group_by(H.barrio_normalizado).order_by(hechos_unicos_expr().desc()).limit(5).all())
    horas = db.query(func.extract("hour", H.hora_evento).label("h"), hechos_unicos_expr()).filter(
        *en_anio, H.hora_evento.isnot(None)).group_by("h").all()
    franjas = {"Madrugada (0 a 6)": 0, "Mañana (6 a 12)": 0, "Tarde (12 a 18)": 0, "Noche (18 a 24)": 0}
    for hora, n in horas:
        franjas[list(franjas)[min(int(hora) // 6, 3)]] += int(n)
    return {
        "fuente_detalle": f"Sábana de la Policía (hechos únicos), año {corte.year} hasta el {corte.isoformat()}",
        "barrios": [{"nombre": b, "total": int(n)} for b, n in barrios],
        "franjas": [{"nombre": k, "total": v} for k, v in franjas.items()] if sum(franjas.values()) else [],
    }


def detalle(db, clave: str, hoy: Optional[date] = None) -> Optional[Dict]:
    """Lo que se despliega al hacer clic en una meta: meses por año y, según la fuente, barrios, horario o comportamientos."""
    from services.piscc_goals import TABLE_16

    hoy = hoy or date.today()
    fila = next((f for f in TABLE_16 if f[0] == clave), None)
    if fila is None:
        return None
    _clave, etiqueta, linea_base, meta, _indicador = fila
    resultado: Dict = {"id": clave, "label": etiqueta, "baseline_2023": linea_base, "goal_2027": meta, "meses": MESES}
    if clave == "convivencia":
        from services import comparendos_rnmc

        corte = comparendos_rnmc.corte(db, hoy)
        if corte:
            resumen = comparendos_rnmc.resumen_convivencia(db, date(corte.year, 1, 1), corte, barrios=5)
            por_mes = {m["mes"]: m["total"] for m in resumen["meses"]}
            resultado.update({
                "series": [{"anio": corte.year, "valores": [por_mes.get(m) for m in MESES]}],
                "fuente_series": f"RNMC (comparendos, cada uno una vez) hasta el {corte.isoformat()}",
                "comportamientos": resumen["comportamientos"][:6],
                "barrios": [{"nombre": b["barrio"], "total": b["total"],
                             "principal": b["principal"]["etiqueta"] if b["principal"] else None} for b in resumen["barrios"]],
                "nota": "El SISC tiene comparendos del RNMC solo desde 2026; para 2024 y 2025 hacen falta esos reportes.",
            })
        return resultado
    datos = cargar()
    resultado["series"] = [{"anio": anio, "valores": serie_mensual(clave, anio, datos)} for anio in range(2024, hoy.year + 1)]
    resultado["fuente_series"] = FUENTE
    if clave in CONDUCTAS_SABANA:
        resultado.update(_detalle_sabana(db, CONDUCTAS_SABANA[clave], hoy))
    return resultado
