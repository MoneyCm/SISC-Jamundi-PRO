import pandas as pd
from datetime import datetime, timedelta
import random

def generate_sample_excel(filename):
    data = []
    localidades = ["ZONA URBANA", "POTRERITO", "VILLA PAZ", "ROZO", "CENTRO"]
    medidas = [
        "Multa General Tipo 4", 
        "Suspension temporal de actividad", 
        "Decomiso", 
        "Destruccion de bien",
        "Disolucion de reunion o actividad que involucre aglomeraciones"
    ]
    estados = ["RATIFICADA", "EN PROCESO", "PAGADO", "COBRO COACTIVO"]
    seguimientos = ["CONTROL POSTERIOR", "VERIFICACION CAMPO", "DOCUMENTACION"]
    
    for i in range(1, 11):
        f_act = datetime(2026, 1, 1) + timedelta(days=random.randint(1, 60))
        f_ini = f_act + timedelta(days=1)
        f_fin = f_ini + timedelta(days=random.randint(3, 15))
        
        v_neto = random.choice([200000, 400000, 800000, 1200000])
        v_pagado = v_neto if random.random() > 0.7 else 0
        
        row = {
            "DTO": "VALLE DEL CAUCA",
            "MUNICIPIO": "JAMUNDI",
            "LOCALIDAD": random.choice(localidades),
            "EXPEDIENTE": f"EXP-2026-{1000 + i}",
            "MEDIDA": random.choice(medidas),
            "FECHA_ACTUACION": f_act.strftime("%d/%m/%Y"),
            "ID_REGISTRA": f"REG-{random.randint(100, 999)}",
            "FUNCIONARIO": "INSPECTOR PRUEBA",
            "FECHA_INICIO": f_ini.strftime("%d/%m/%Y"),
            "FECHA_FIN": f_fin.strftime("%d/%m/%Y"),
            "DIAS": (f_fin - f_ini).days,
            "ANOTACION": f"Prueba de gestion para expediente {i}",
            "OTROS_MEDIOS_PRUEBA": "Fotografias, Testimonio",
            "TIPO_SEGUIMIENTO": random.choice(seguimientos),
            "ESTADO": random.choice(estados),
            "FECHA_PAGO": (f_act + timedelta(days=10)).strftime("%d/%m/%Y") if v_pagado > 0 else "",
            "ENTIDAD_PAGO": "BANCO POPULAR" if v_pagado > 0 else "",
            "COMPROBANTE_PAGO": f"COMP-{random.randint(10000, 99999)}" if v_pagado > 0 else "",
            "NUMERO_CUENTA": "123456789",
            "VALOR_INTERES": 0,
            "VALOR_DESCUENTO": v_neto * 0.1 if random.random() > 0.8 else 0,
            "VALOR_COACTIVO": v_neto if "COACTIVO" in estados else 0,
            "VALOR_NETO": v_neto,
            "VALOR_PAGADO": v_pagado,
            "FECHA_LIQUIDACION": f_act.strftime("%d/%m/%Y")
        }
        data.append(row)
    
    df = pd.DataFrame(data)
    df.to_excel(filename, index=False)
    print(f"✅ Archivo de prueba generado: {filename}")

if __name__ == "__main__":
    generate_sample_excel("c:/Proyectos/SISC-Jamundi-PRO/backend/backlog_inspecciones_test.xlsx")
