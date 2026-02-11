import sqlite3
import os

def init_db():
    db_path = 'data/rental.db'
    schema_path = 'schema.sql'
    
    if not os.path.exists('data'):
        os.makedirs('data')
        
    conn = sqlite3.connect(db_path)
    with open(schema_path, 'r', encoding='utf-8') as f:
        schema = f.read()
        conn.executescript(schema)
    conn.commit()
    conn.close()
    print(f"Database initialized at {db_path}")

if __name__ == "__main__":
    init_db()
