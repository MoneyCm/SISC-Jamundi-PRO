import io
from datetime import date, timedelta
from unittest.mock import MagicMock

import pandas as pd

from services.ingest_rnmc import RNMCIngestor


def _excel(rows):
    buffer = io.BytesIO()
    pd.DataFrame(rows).to_excel(buffer, index=False)
    return buffer.getvalue()


def _row(expediente, fecha):
    return {
        "DTO": "VALLE DEL CAUCA", "MUNICIPIO": "JAMUNDI", "LOCALIDAD": "ZONA URBANA",
        "EXPEDIENTE": expediente, "MEDIDA": "Multa General Tipo 2", "FECHA_ACTUACION": fecha,
        "ID_REGISTRA": "1", "FUNCIONARIO": "INSPECTOR", "FECHA_INICIO": fecha, "FECHA_FIN": fecha,
        "DIAS": 10, "ESTADO": "EN PROCESO", "TIPO_SEGUIMIENTO": "", "VALOR_NETO": 1000, "VALOR_PAGADO": 0,
    }


def test_measures_dated_after_today_are_rejected_and_reported():
    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = []
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    content = _excel([_row("76-364-6-2026-0001", "2026-01-22 14:25:32"), _row("EXP-TEST-001", tomorrow)])

    result = RNMCIngestor(db).process_file(content, "rnmc.xlsx")

    assert result.get("total") == 1, result
    assert result["rejected_future"] == [{"expediente": "-001", "fecha_actuacion": tomorrow}]
    inserted = [call.args[0].compile().params for call in db.execute.call_args_list]
    assert all(params["expediente"] != "EXP-TEST-001" for params in inserted)
