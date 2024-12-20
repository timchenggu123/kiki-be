import sqlite3


def init_db():
    create_table_if_not_exists()

def create_table_if_not_exists():
    db = sqlite3.connect("auth.db")
    db.execute("CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password TEXT)")
    db.commit()
    db.close()
    
def add_user(username, password):
    db = sqlite3.connect("auth.db")
    db.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, password))
    db.commit()
    db.close()

def get_password(username):
    db = sqlite3.connect("auth.db")
    cursor = db.execute("SELECT password FROM users WHERE username = ?", (username,))
    return cursor.fetchone()[0]

def user_exists(username):
    db = sqlite3.connect("auth.db")
    cursor = db.execute("SELECT * FROM users WHERE username = ?", (username,))
    return cursor.fetchone() is not None

init_db()