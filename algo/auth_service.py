import sqlite3
import os
import secrets
from datetime import datetime, timedelta, timezone
import jwt
import bcrypt
from dotenv import load_dotenv

# Load environment variables (especially SECRET_KEY)
load_dotenv()

# ============================================================================
# CONFIGURATION & INITIALIZATION
# ============================================================================

# Define database path relative to this file
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'user_auth.db')

# IMPORTANT: NEVER expose this key. Load it from environment variables.
# Fallback to a random generated key if not set (for development only).
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", secrets.token_urlsafe(32))
JWT_ALGORITHM = "HS256"
TOKEN_EXPIRATION_DAYS = 7

def init_user_database():
    """Initializes the SQLite database and creates the users table."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # User roles: ADMIN, COORDINATOR, STUDENT
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'STUDENT',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()
    print("✅ User authentication database initialized successfully!")

# Ensure the database is initialized on module load
init_user_database()


# ============================================================================
# JWT AND TOKEN HANDLERS
# ============================================================================

def create_auth_token(user_id: int, role: str) -> str:
    """Generates a JWT token for the user."""
    expiration_time = datetime.now(timezone.utc) + timedelta(days=TOKEN_EXPIRATION_DAYS)
    payload = {
        'exp': expiration_time,
        'iat': datetime.now(timezone.utc),
        'sub': str(user_id), # Subject: user ID
        'user_id': user_id,
        'role': role
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)

def verify_token(token: str) -> dict or None:
    """Verifies a JWT token and returns its payload if valid."""
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        return None # Token expired
    except jwt.InvalidTokenError:
        return None # Invalid token (bad signature, etc.)

# ============================================================================
# USER MANAGEMENT FUNCTIONS
# ============================================================================

def get_user_by_email(email: str) -> dict or None:
    """Fetches a user by email."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, username, email, password_hash, role FROM users WHERE email = ?", (email,))
    user_data = cursor.fetchone()
    conn.close()
    
    if user_data:
        return {
            "id": user_data[0],
            "username": user_data[1],
            "email": user_data[2],
            "password_hash": user_data[3],
            "role": user_data[4],
        }
    return None

def get_user_by_token(token: str) -> dict or None:
    """Fetches a user profile using a raw JWT token string."""
    payload = verify_token(token)
    if not payload:
        return None
    
    user_id = payload.get('user_id')
    if not user_id:
        return None
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, username, email, role FROM users WHERE id = ?", (user_id,))
    user_data = cursor.fetchone()
    conn.close()
    
    if user_data:
        return {
            "id": user_data[0],
            "username": user_data[1],
            "email": user_data[2],
            "role": user_data[3],
        }
    return None


# ============================================================================
# ENDPOINT IMPLEMENTATIONS
# ============================================================================

def signup(username: str, email: str, password: str, role: str) -> tuple[bool, str]:
    """Handles user registration."""
    if not username or not email or not password:
        return False, "All fields are required."
    
    if get_user_by_email(email):
        return False, "User with this email already exists."
    
    # Hash password
    password_bytes = password.encode('utf-8')
    password_hash = bcrypt.hashpw(password_bytes, bcrypt.gensalt()).decode('utf-8')
    
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO users (username, email, password_hash, role) VALUES (?, ?, ?, ?)",
            (username, email, password_hash, role.upper())
        )
        conn.commit()
        conn.close()
        return True, "User registered successfully."
    except sqlite3.Error as e:
        return False, f"Database error during registration: {str(e)}"

def login(email: str, password: str) -> tuple[bool, dict or None, str]:
    """Authenticates user and returns a token."""
    user = get_user_by_email(email)
    
    if not user:
        return False, None, "Invalid email or password."
    
    # Verify password hash
    if bcrypt.checkpw(password.encode('utf-8'), user['password_hash'].encode('utf-8')):
        # Authentication successful
        token = create_auth_token(user['id'], user['role'])
        
        # Prepare public user data to return
        user_data = {
            "id": user['id'],
            "username": user['username'],
            "email": user['email'],
            "role": user['role'],
        }
        return True, user_data, token
    else:
        return False, None, "Invalid email or password."


def update_user_profile(user_id: int, username: str = None, email: str = None) -> tuple[bool, str]:
    """Updates user profile information."""
    updates = []
    params = []
    
    if username:
        updates.append("username = ?")
        params.append(username)
    
    if email:
        updates.append("email = ?")
        params.append(email)
        
    if not updates:
        return False, "No data provided for update."
        
    query = f"UPDATE users SET {', '.join(updates)} WHERE id = ?"
    params.append(user_id)
    
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(query, tuple(params))
        conn.commit()
        
        if cursor.rowcount == 0:
            conn.close()
            return False, "User not found or no changes made."
            
        conn.close()
        return True, "Profile updated successfully."
        
    except sqlite3.IntegrityError:
        return False, "Email address already in use."
    except sqlite3.Error as e:
        return False, f"Database error during update: {str(e)}"