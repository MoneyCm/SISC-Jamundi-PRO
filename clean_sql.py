import os

def clean_sql():
    with open("backup.sql", "r", encoding="utf-8") as f:
        lines = f.readlines()
        
    with open("backup_clean.sql", "w", encoding="utf-8") as f:
        for line in lines:
            if "transaction_timeout" in line or line.startswith("\\restrict"):
                continue
            if "OWNER TO neondb_owner" in line:
                line = line.replace("neondb_owner", "sisc_user")
            f.write(line)

if __name__ == "__main__":
    clean_sql()
