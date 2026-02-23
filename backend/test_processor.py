import sys, os
sys.path.append(os.path.abspath('.'))
from services.excel_processor import NationalStatsProcessor
print("Starting test")
p = NationalStatsProcessor()
f = "test_policia_2025.xlsx"
if os.path.exists(f):
    print("Testing", f)
    with open(f, "rb") as file:
        content = file.read()
        print("File read, size:", len(content))
        try:
            it = p.process_excel(content, os.path.basename(f))
            print("Got iterator")
            records = []
            for count, r in enumerate(it):
                records.append(r)
                if count % 1000 == 0:
                    print("Parsed", count, "records...")
                if count > 5000:
                    print("Stopping at 5000")
                    break
            print("Done parsing, total:", len(records))
            if records:
                print("First record:", records[0])
        except Exception as e:
            print("Error:", e)
else:
    print("Not found")
