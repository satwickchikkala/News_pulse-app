import sqlite3

def init_db():
    conn = sqlite3.connect("news_pulse.db")
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            link TEXT,
            published_at TEXT
        )
    ''')
    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
    print("Database created successfully!")

