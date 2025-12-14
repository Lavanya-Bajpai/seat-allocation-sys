# pdf_gen/database.py
import sqlite3
import os
from datetime import datetime

DATABASE_PATH = "pdf_templates.db"

def init_database():
    """Initialize SQLite database with user templates"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    # Create user_templates table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            template_name TEXT DEFAULT 'default',
            dept_name TEXT DEFAULT 'Department of Computer Science & Engineering',
            exam_details TEXT DEFAULT 'Minor-II Examination (2025 Admitted), November 2025',
            seating_plan_title TEXT DEFAULT 'Seating Plan',
            branch_text TEXT DEFAULT 'Branch: B.Tech(CSE & CSD Ist year)',
            room_number TEXT DEFAULT 'Room no. 103A',
            coordinator_name TEXT DEFAULT 'Dr. Dheeraj K. Dixit',
            coordinator_title TEXT DEFAULT 'Dept. Exam Coordinator',
            banner_image_path TEXT DEFAULT 'pdf_gen/data/banner.png',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, template_name)
        )
    ''')
    
    # Insert system default template
    cursor.execute('''
        INSERT OR IGNORE INTO user_templates (user_id, template_name) 
        VALUES ('system', 'default')
    ''')
    
    conn.commit()
    conn.close()
    print("✅ Database initialized successfully!")

def get_db_connection():
    """Get database connection with Row factory"""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# Initialize on first run
if __name__ == "__main__":
    init_database()