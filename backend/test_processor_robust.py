import sys, os
sys.path.append(os.path.abspath('.'))
from services.excel_processor import NationalStatsProcessor

processor = NationalStatsProcessor()

def run_test(filename):
    print(f"\n--- Probando archivo: {filename} ---")
    if not os.path.exists(filename):
        print("Archivo no encontrado.")
        return
    
    with open(filename, 'rb') as f:
        content = f.read()
        
    records = processor.process_excel(content, filename)
    
    count = 0
    valid_records = []
    
    for r in records:
        count += 1
        valid_records.append(r)
        if count <= 2:
            print(r)
            
    print(f"Total registros extraidos válidos: {count}")
    if count > 0:
        print("Ejemplo final:", valid_records[-1])
        
run_test("homicidio_intencional.xlsx")
run_test("hurto_personas.xlsx")
