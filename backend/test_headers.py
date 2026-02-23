import openpyxl

def inspect_headers(filename):
    print(f"\n--- {filename} ---")
    wb = openpyxl.load_workbook(filename, read_only=True, data_only=True)
    ws = wb.active
    from itertools import islice
    for i, row in enumerate(islice(ws.rows, 0, 5)):
        vals = [str(c.value) for c in row if c.value is not None]
        print(f"Row {i}: {vals}")
        
inspect_headers("homicidio_intencional.xlsx")
inspect_headers("hurto_personas.xlsx")
