import sqlite3
import os

DB_PATH = "mini_erp.db"

if not os.path.exists(DB_PATH):
    print("mini_erp.db not found, nothing to fix.")
    raise SystemExit

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

# check columns in employee table
cur.execute("PRAGMA table_info(employee);")
cols = [row[1] for row in cur.fetchall()]
print("Columns:", cols)

if "password_hash" not in cols:
    print("Adding password_hash column...")
    cur.execute("ALTER TABLE employee ADD COLUMN password_hash VARCHAR(255) DEFAULT '';")
    conn.commit()
    print("password_hash column added.")
else:
    print("password_hash column already exists.")

conn.close()
print("Done.")
