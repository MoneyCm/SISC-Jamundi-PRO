processed_files = 3
total_files = 27
p = round((processed_files / total_files) * 100) if total_files > 0 else 100
import json
print(json.dumps({"processed_files": processed_files, "progress": p}))
