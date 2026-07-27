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

if __name__ == "__main__":
    unittest.main()
