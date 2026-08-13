import sys
import os
import unittest
from sqlalchemy.orm import Session
from db.session import SessionLocal, engine
from services.inspeccion_service import InspeccionService
from db.models_inspecciones import InspeccionExpediente, InspeccionMedida
import io

class TestInspecciones(unittest.TestCase):
    def setUp(self):
        self.db = SessionLocal()
        self.service = InspeccionService(self.db)

    def tearDown(self):
        test_record = self.db.query(InspeccionExpediente).filter_by(numero_expediente="TEST-001").first()
        if test_record:
            self.db.delete(test_record)
            self.db.commit()
        self.db.close()

    def test_ingesta_basica(self):
        # Crear un Excel en memoria para la prueba
        import pandas as pd
        data = [{
            "DTO": "VALLE",
            "MUNICIPIO": "JAMUNDI",
            "LOCALIDAD": "CENTRO",
            "EXPEDIENTE": "TEST-001",
            "MEDIDA": "MULTA PRUEBA",
            "FECHA_ACTUACION": "2026-03-10",
            "ESTADO": "RATIFICADA",
            "VALOR_NETO": 500000,
            "VALOR_PAGADO": 0
        }]
        df = pd.DataFrame(data)
        out = io.BytesIO()
        df.to_excel(out, index=False)
        out.seek(0)

        import asyncio
        result = asyncio.run(self.service.ingest_excel(out.read(), "test.xlsx"))
        print(f"Resultado Ingesta: {result}")

        # Verificar en DB
        exp = self.db.query(InspeccionExpediente).filter_by(numero_expediente="TEST-001").first()
        self.assertIsNotNone(exp)
        self.assertEqual(exp.localidad, "CENTRO")

        medida = self.db.query(InspeccionMedida).filter_by(expediente_id=exp.id).first()
        self.assertEqual(medida.nombre_medida, "MULTA PRUEBA")
        self.assertEqual(medida.finanza.valor_neto, 500000)

    def test_parse_date_uses_colombian_day_first_format(self):
        parsed = self.service.parse_date("10/03/2026")

        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.date().isoformat(), "2026-03-10")

    def test_parse_date_preserves_iso_year_month_day_format(self):
        parsed = self.service.parse_date("2026-07-10")

        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.date().isoformat(), "2026-07-10")

    def test_parse_date_supports_excel_serial_values(self):
        parsed = self.service.parse_date(46000)

        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.date().isoformat(), "2025-12-09")

if __name__ == "__main__":
    unittest.main()
