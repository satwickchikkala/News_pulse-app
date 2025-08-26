import streamlit as st
import bcrypt
import sqlite3
from datetime import datetime

# Database setup for users
def init_user_db():
    conn = sqlite3.connect("news_pulse.db")
    cursor = conn.cursor()
    
    # Create users table if it doesn't exist
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            email TEXT,
            created_at TEXT,
            last_login TEXT
        )
    """)
    
    conn.commit()
    conn.close()

# Initialize the user database
init_user_db()

def hash_password(password):
    """Hash a password using bcrypt"""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(password, hashed):
    """Verify a password against its hash"""
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

def create_user(username, password, email=None):
    """Create a new user in the database"""
    try:
        conn = sqlite3.connect("news_pulse.db")
        cursor = conn.cursor()
        
        # Check if username already exists
        cursor.execute("SELECT COUNT(*) FROM users WHERE username = ?", (username,))
        if cursor.fetchone()[0] > 0:
            return False, "Username already exists!"
        
        # Insert new user
        hashed_password = hash_password(password)
        created_at = datetime.now().isoformat()
        
        cursor.execute(
            "INSERT INTO users (username, password, email, created_at) VALUES (?, ?, ?, ?)",
            (username, hashed_password, email, created_at)
        )
        
        conn.commit()
        conn.close()
        return True, "User created successfully!"
    except Exception as e:
        if 'conn' in locals():
            conn.close()
        return False, f"Error creating user: {str(e)}"

def verify_user(username, password):
    """Verify user credentials"""
    try:
        conn = sqlite3.connect("news_pulse.db")
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT password FROM users WHERE username = ?", 
            (username,)
        )
        
        result = cursor.fetchone()
        conn.close()
        
        if result and verify_password(password, result[0]):
            # Update last login time
            update_last_login(username)
            return True, "Login successful!"
        else:
            return False, "Invalid username or password!"
            
    except Exception as e:
        if 'conn' in locals():
            conn.close()
        return False, f"Error during login: {str(e)}"

def update_last_login(username):
    """Update the last login time for a user"""
    try:
        conn = sqlite3.connect("news_pulse.db")
        cursor = conn.cursor()
        
        last_login = datetime.now().isoformat()
        cursor.execute(
            "UPDATE users SET last_login = ? WHERE username = ?",
            (last_login, username)
        )
        
        conn.commit()
        conn.close()
    except Exception as e:
        if 'conn' in locals():
            conn.close()