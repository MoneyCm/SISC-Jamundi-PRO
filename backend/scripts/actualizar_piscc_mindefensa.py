"""Actualiza en data/piscc/mindefensa.json los tres indicadores del PISCC que salen de MinDefensa.

Secuestro, extorsión y violencia intrafamiliar (tabla 16 del PISCC) se toman de los datos
abiertos que MinDefensa publica en datos.gov.co, filtrados para Jamundí (DANE 76364):
- "actual": 1 de enero hasta el corte del año en curso.
- "anterior": el mismo periodo del año anterior.
- "ultimo_registro": corte de la publicación (último día del mes con datos), que es la fecha que
  el PISCC muestra como corte y usa para la proyección.

Uso (en la carpeta backend):  python scripts/actualizar_piscc_mindefensa.py
Las demás filas del archivo no se tocan.
"""
import calendar
import json
import sys
import urllib.parse
import urllib.request
from datetime import date, datetime
from pathlib import Path

ARCHIVO = Path(__file__).resolve().parents[1] / "data" / "piscc" / "mindefensa.json"
DANE_JAMUNDI = "76364"
DATASETS = {
    # palabra que identifica la fila en el archivo: (id en datos.gov.co, nombre)
    "secuestro": ("d7zw-hpf4", "Secuestro"),
    "extors": ("q2ib-t9am", "Extorsión"),
    "intrafamiliar": ("gepp-dxcs", "Violencia Intrafamiliar"),
}


def consultar(dataset: str, **parametros):
    url = f"https://www.datos.gov.co/resource/{dataset}.json?" + urllib.parse.urlencode(parametros)
    with urllib.request.urlopen(url, timeout=120) as respuesta:
        return json.loads(respuesta.read())


def fecha(valor: str) -> date:
    return datetime.fromisoformat(valor[:10]).date()


def un_anio_antes(valor: date) -> date:
    try:
        return valor.replace(year=valor.year - 1)
    except ValueError:
        return valor.replace(year=valor.year - 1, day=28)


def indicador(dataset: str) -> dict:
    ultimo = fecha(consultar(dataset, **{"$select": "max(fecha_hecho) as corte"})[0]["corte"])
    corte = ultimo.replace(day=calendar.monthrange(ultimo.year, ultimo.month)[1])
    filas = consultar(dataset, cod_muni=DANE_JAMUNDI, **{"$limit": 50000})

    def suma(inicio: date, fin: date) -> int:
        return sum(int(float(f.get("cantidad") or 1)) for f in filas if inicio <= fecha(f["fecha_hecho"]) <= fin)

    actual = suma(date(corte.year, 1, 1), corte)
    anterior = suma(date(corte.year - 1, 1, 1), un_anio_antes(corte))
    casos = [fecha(f["fecha_hecho"]) for f in filas if fecha(f["fecha_hecho"]) <= corte]
    diferencia = actual - anterior
    return {
        "anterior": anterior,
        "actual": actual,
        "diffAbs": diferencia,
        "varPct": f"{diferencia / anterior * 100:+.1f}%" if anterior else "Sin base",
        "estado": "SUBE" if diferencia > 0 else ("BAJA" if diferencia < 0 else "IGUAL"),
        "ultimo_registro": corte.strftime("%d/%m/%Y"),
        "ultimo_caso_jamundi": max(casos).strftime("%d/%m/%Y") if casos else None,
        "fuente": f"MinDefensa, datos.gov.co/resource/{dataset}",
    }


def main() -> int:
    datos = json.loads(ARCHIVO.read_text(encoding="utf-8-sig"))
    filas = datos.get("indicadores", [])
    for palabra, (dataset, nombre) in DATASETS.items():
        nuevo = indicador(dataset)
        fila = next((f for f in filas if palabra in str(f.get("delito", "")).lower()), None)
        if fila is None:
            fila = {"delito": nombre}
            filas.append(fila)
        antes = (fila.get("anterior"), fila.get("actual"), fila.get("ultimo_registro"))
        fila.update(nuevo)
        print(f"{nombre}: {antes} -> ({nuevo['anterior']}, {nuevo['actual']}, {nuevo['ultimo_registro']})")
    datos["indicadores"] = filas
    datos["actualizacion_piscc"] = {
        "fecha": date.today().isoformat(),
        "indicadores": [nombre for _dataset, nombre in DATASETS.values()],
        "nota": "Estos tres tienen su propio corte (ultimo_registro); las demás filas conservan el corte de mes_corte.",
    }
    ARCHIVO.write_text(json.dumps(datos, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
