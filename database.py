import sqlite3
import hashlib
import json
import os
import random
import string
import time

DB_FILE = "news_app_v2.db"
SESSION_TIMEOUT = 48 * 60 * 60  # 48 hours in seconds

def init_db():
    """Initialize the database tables."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # Users table
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            email TEXT PRIMARY KEY,
            password_hash TEXT NOT NULL,
            two_factor_secret TEXT,
            recovery_code TEXT,
            auth_code TEXT
        )
    ''')
    
    # User Settings/Data table
    c.execute('''
        CREATE TABLE IF NOT EXISTS user_data (
            email TEXT,
            key TEXT,
            value TEXT,
            PRIMARY KEY (email, key),
            FOREIGN KEY (email) REFERENCES users (email)
        )
    ''')
    
    # Persistent Session Table (Multi-user token-based)
    c.execute('''
        CREATE TABLE IF NOT EXISTS persistent_sessions (
            token TEXT PRIMARY KEY,
            email TEXT NOT NULL,
            ip_address TEXT,
            expires_at REAL NOT NULL,
            FOREIGN KEY (email) REFERENCES users (email)
        )
    ''')
    
    # --- Migrations ---
    # Add ip_address column if it doesn't exist (it might be missing if table was created in previous step)
    try:
        c.execute("ALTER TABLE persistent_sessions ADD COLUMN ip_address TEXT")
    except sqlite3.OperationalError:
        # Column already exists
        pass

    try:
        c.execute("ALTER TABLE users ADD COLUMN auth_code TEXT")
    except sqlite3.OperationalError:
        pass

    # Read History Table
    c.execute('''
        CREATE TABLE IF NOT EXISTS read_history (
            email TEXT,
            article_url TEXT,
            read_at REAL,
            PRIMARY KEY (email, article_url),
            FOREIGN KEY (email) REFERENCES users (email)
        )
    ''')

    conn.commit()
    conn.close()

# --- User Management ---
def hash_password(password):
    """Hash a password for storage."""
    return hashlib.sha256(password.encode()).hexdigest()

def create_user(email, password):
    """Register a new user with email."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    try:
        # Generate a random base32-like string as a mock 2FA secret (for future use/display)
        secret = ''.join(random.choices(string.ascii_uppercase + string.digits, k=16))
        
        c.execute("INSERT INTO users (email, password_hash, two_factor_secret) VALUES (?, ?, ?)", 
                  (email, hash_password(password), secret))
        conn.commit()
        return secret 
    except sqlite3.IntegrityError:
        return None 
    finally:
        conn.close()

def ensure_user_exists(email):
    """Checks if user exists, creates if not. Returns the 2FA secret."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT two_factor_secret FROM users WHERE email = ?", (email,))
    row = c.fetchone()
    if row:
        conn.close()
        return row[0]
    else:
        # Create new user with dummy password
        # Generate a random base32-like string as a mock 2FA secret
        secret = ''.join(random.choices(string.ascii_uppercase + string.digits, k=16))
        c.execute("INSERT INTO users (email, password_hash, two_factor_secret) VALUES (?, ?, ?)", 
                  (email, hash_password("magic_password_placeholder"), secret))
        conn.commit()
        conn.close()
        return secret

def verify_user(email, password):
    """Verify login credentials. Returns 2FA secret if valid, None otherwise."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT password_hash, two_factor_secret FROM users WHERE email = ?", (email,))
    row = c.fetchone()
    conn.close()
    
    if row and row[0] == hash_password(password):
        return row[1] 
    return None

def verify_2fa(email, code):
    """Verify 2FA auth code."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT auth_code FROM users WHERE email = ?", (email,))
    row = c.fetchone()
    conn.close()
    
    if row and row[0] == code:
        return True 
    return False

def set_auth_code(email):
    """Generate and save a random 6-digit auth code."""
    code = ''.join(random.choices(string.digits, k=6))
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("UPDATE users SET auth_code = ? WHERE email = ?", (code, email))
    updated = c.rowcount > 0
    conn.commit()
    conn.close()
    return code if updated else None

def set_recovery_code(email):
    """Generate and save a recovery code."""
    code = ''.join(random.choices(string.digits, k=6))
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("UPDATE users SET recovery_code = ? WHERE email = ?", (code, email))
    updated = c.rowcount > 0
    conn.commit()
    conn.close()
    return code if updated else None

def verify_recovery_code(email, code):
    """Verify recovery code."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT recovery_code FROM users WHERE email = ?", (email,))
    row = c.fetchone()
    conn.close()
    
    if row and row[0] == code:
        return True
    return False

def update_password(email, new_password):
    """Update password and clear recovery code."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("UPDATE users SET password_hash = ?, recovery_code = NULL WHERE email = ?", 
              (hash_password(new_password), email))
    conn.commit()
    conn.close()

def save_user_data(email, key, value):
    """Save user specific data."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    json_val = json.dumps(value)
    c.execute("INSERT OR REPLACE INTO user_data (email, key, value) VALUES (?, ?, ?)",
              (email, key, json_val))
    conn.commit()
    conn.close()

def load_user_data(email, key, default=None):
    """Load user specific data."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT value FROM user_data WHERE email = ? AND key = ?", (email, key))
    row = c.fetchone()
    conn.close()
    
    if row:
        return json.loads(row[0])
    return default

# --- Token-based Session Management ---
def create_persistent_session(email, ip_address):
    """Generate a random 32-char token and save to DB."""
    token = ''.join(random.choices(string.ascii_letters + string.digits, k=32))
    expires_at = time.time() + SESSION_TIMEOUT
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT INTO persistent_sessions (token, email, ip_address, expires_at) VALUES (?, ?, ?, ?)",
              (token, email, ip_address, expires_at))
    conn.commit()
    conn.close()
    return token

def verify_persistent_session(token, ip_address):
    """Check if token is valid, not expired, and IP matches (loosely). Returns email if OK, else reason string."""
    if not token: return "NO_TOKEN_GIVEN"
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT email, ip_address, expires_at FROM persistent_sessions WHERE token = ?", (token,))
    row = c.fetchone()
    
    if row:
        email, stored_ip, expires_at = row
        # Check Expiry
        if time.time() > expires_at:
            c.execute("DELETE FROM persistent_sessions WHERE token = ?",(token,))
            conn.commit()
            conn.close()
            return "EXPIRED"
            
        # Check IP (Loosened: Check first two octets if possible)
        def get_subnet(ip):
            parts = str(ip).split(".")
            if len(parts) >= 2:
                return ".".join(parts[:2])
            return str(ip)

        if stored_ip and ip_address:
            stored_sub = get_subnet(stored_ip)
            current_sub = get_subnet(ip_address)
            if stored_sub != current_sub:
                conn.close()
                return f"IP_MISMATCH:stored={stored_ip}"
            
        # Success! Update activity
        new_expires = time.time() + SESSION_TIMEOUT
        c.execute("UPDATE persistent_sessions SET expires_at = ? WHERE token = ?", (new_expires, token))
        conn.commit()
        conn.close()
        return email
        
    conn.close()
    return "TOKEN_NOT_FOUND"

def delete_persistent_session(token):
    """Remove a session token on logout."""
    if not token: return
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM persistent_sessions WHERE token = ?", (token,))
    conn.commit()
    conn.close()

def get_latest_session_by_ip(ip_address):
    """Find the most recent valid session for this IP."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    # Check for sessions within the same subnet (Loosened)
    # We'll just look for exact or recent matches for simplicity in this helper
    c.execute("""
        SELECT email, token FROM persistent_sessions 
        WHERE expires_at > ? AND ip_address LIKE ?
        ORDER BY expires_at DESC LIMIT 1
    """, (time.time(), f"{'.'.join(ip_address.split('.')[:2])}%"))
    row = c.fetchone()
    conn.close()
    return row # (email, token) or None
