import sys
import os
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from services.excel_processor import NationalStatsProcessor

processor = NationalStatsProcessor()
filename = r'c:\Users\USER\Downloads\ASPERSION.xlsx'

with open(filename, 'rb') as f:
    content = f.read()
    records = list(processor.process_excel(content, 'ASPERSION.xlsx'))
    print(f"Yielded {len(records)} records")
    if records:
        print("First record sample:")
        print(records[0])
    
    valle_records = [r for r in records if r.get('codigo_depto') == 76]
    print(f"Valle del Cauca records: {len(valle_records)}")
    
    jamundi_records = [r for r in records if r.get('codigo_muni') == 76364]
    print(f"Jamundí records: {len(jamundi_records)}")
