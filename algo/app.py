import sys
import os
import time
import io  # ✅ FIXED: Added missing import
import json
import sqlite3
from pathlib import Path
from functools import wraps
from typing import Dict, List, Tuple

from flask import Flask, jsonify, request, send_file
from flask_cors import CORS

# --------------------------------------------------
# Optional Modules (PDF & Auth)
# --------------------------------------------------
try:
    from pdf_gen import create_seating_pdf
except ImportError:
    create_seating_pdf = None

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "Backend"))
try:
    from Backend.auth_service import signup as auth_signup, login as auth_login, verify_token, get_user_by_token, update_user_profile
except Exception:
    auth_signup = auth_login = verify_token = get_user_by_token = update_user_profile = None

# --------------------------------------------------
# Local Modules
# --------------------------------------------------
try:
    from student_parser import StudentDataParser
    from algo import SeatingAlgorithm
except ImportError as e:
    print(f"Warning: Could not import local modules: {e}")
    StudentDataParser = None
    SeatingAlgorithm = None

# --------------------------------------------------
# App setup
# --------------------------------------------------
app = Flask(__name__)
CORS(app, supports_credentials=True)

BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "demo.db"

# --------------------------------------------------
# DB bootstrap (MERGED)
# --------------------------------------------------
def ensure_demo_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS uploads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            batch_id TEXT UNIQUE,
            batch_name TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            upload_id INTEGER,
            batch_id TEXT,
            batch_name TEXT,
            enrollment TEXT NOT NULL,
            name TEXT,
            inserted_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(upload_id, enrollment)
        );
    """)

    # ✅ RESTORED: Allocations table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS allocations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id TEXT,
            upload_id INTEGER,
            enrollment TEXT,
            room_id TEXT,
            seat_id TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()

ensure_demo_db()

# --------------------------------------------------
# Helpers (MERGED)
# --------------------------------------------------
def parse_int_dict(val):
    if isinstance(val, dict): return {int(k): int(v) for k, v in val.items()}
    if isinstance(val, str) and val:
        try: return json.loads(val)
        except: pass
    return {}

def parse_str_dict(val):
    if isinstance(val, dict): return {int(k): str(v) for k, v in val.items()}
    if isinstance(val, str) and val:
        try: return json.loads(val)
        except: pass
    return {}

def get_batch_counts_and_labels_from_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT batch_name, COUNT(*) FROM students GROUP BY batch_name ORDER BY batch_name")
    rows = cur.fetchall()
    conn.close()
    counts, labels = {}, {}
    for i, (name, count) in enumerate(rows, start=1):
        counts[i] = count
        labels[i] = name
    return counts, labels

def get_batch_roll_numbers_from_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT batch_name, enrollment FROM students ORDER BY id")
    rows = cur.fetchall()
    conn.close()
    groups = {}
    for batch, enr in rows:
        groups.setdefault(batch, []).append(enr)
    return {i + 1: groups[k] for i, k in enumerate(sorted(groups))}

# --------------------------------------------------
# Auth Decorator
# --------------------------------------------------
def token_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if verify_token is None: return fn(*args, **kwargs)
        auth = request.headers.get("Authorization")
        if not auth: return jsonify({"error": "Token missing"}), 401
        token = auth.split(" ")[1]
        payload = verify_token(token)
        if not payload: return jsonify({"error": "Invalid token"}), 401
        request.user_id = payload.get("user_id")
        return fn(*args, **kwargs)
    return wrapper

# --------------------------------------------------
# AUTH ROUTES
# --------------------------------------------------
@app.route("/api/auth/signup", methods=["POST"])
def signup_route():
    if auth_signup is None: return jsonify({"error": "Auth module missing"}), 501
    data = request.get_json(force=True)
    ok, msg = auth_signup(
        data.get("username"),
        data.get("email"),
        data.get("password"),
        data.get("role", "STUDENT"),
    )
    return jsonify({"success": ok, "message": msg}), 201 if ok else 400

@app.route("/api/auth/login", methods=["POST"])
def login_route():
    if auth_login is None: return jsonify({"error": "Auth module missing"}), 501
    data = request.get_json(force=True)
    ok, user, token = auth_login(data.get("email"), data.get("password"))
    if not ok:
        return jsonify({"error": token}), 401
    return jsonify({"token": token, "user": user})

# --------------------------------------------------
# Upload Routes
# --------------------------------------------------

@app.route("/api/upload-preview", methods=["POST"])
def api_upload_preview():
    """Collaborator Feature: Preview file before committing"""
    try:
        if "file" not in request.files: return jsonify({"error": "No file provided"}), 400
        file = request.files["file"]
        if file.filename == '': return jsonify({"error": "No file selected"}), 400
        
        file_content = file.read()
        parser = StudentDataParser()
        preview_data = parser.preview(io.BytesIO(file_content), max_rows=10)
        
        return jsonify({"success": True, **preview_data}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/upload", methods=["POST"])
def api_upload():
    """Collaborator Feature: Cache upload"""
    try:
        if "file" not in request.files: return jsonify({"error": "No file"}), 400
        file = request.files["file"]
        mode = int(request.form.get("mode", 2))
        batch_name = request.form.get("batch_name", "BATCH1")
        name_col = request.form.get("nameColumn", None)
        enrollment_col = request.form.get("enrollmentColumn", None)
        
        file_content = file.read()
        parser = StudentDataParser()
        pr = parser.parse_file(
            io.BytesIO(file_content),
            mode=mode, 
            batch_name=batch_name,
            name_col=name_col, 
            enrollment_col=enrollment_col
        )
        
        if not hasattr(app, 'config'): app.config = {}
        if 'UPLOAD_CACHE' not in app.config: app.config['UPLOAD_CACHE'] = {}
        app.config['UPLOAD_CACHE'][pr.batch_id] = pr
        
        return jsonify({
            "success": True,
            "batch_id": pr.batch_id,
            "batch_name": pr.batch_name,
            "rows_extracted": pr.rows_extracted,
            "sample": pr.data[pr.batch_name][:10],
            "preview": {
                "columns": list(pr.data[pr.batch_name][0].keys()) if pr.mode == 2 and pr.data[pr.batch_name] else [],
                "totalRows": pr.rows_total,
                "extractedRows": pr.rows_extracted
            }
        }), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/commit-upload", methods=["POST"])
def commit_upload():
    """Merged Feature: Commit to DB"""
    try:
        body = request.get_json(force=True)
        batch_id = body.get("batch_id")
        cache = app.config.get("UPLOAD_CACHE", {})
        pr = cache.get(batch_id)
        
        if not pr: return jsonify({"error": "Preview expired"}), 400
        
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("INSERT INTO uploads (batch_id, batch_name) VALUES (?, ?)", (pr.batch_id, pr.batch_name))
        upload_id = cur.lastrowid
        
        inserted, skipped = 0, 0
        for row in pr.data[pr.batch_name]:
            enr = row.get("enrollmentNo") if isinstance(row, dict) else str(row)
            name = row.get("name") if isinstance(row, dict) else None
            
            if not enr: 
                skipped += 1
                continue
            try:
                cur.execute("INSERT INTO students (upload_id, batch_id, batch_name, enrollment, name) VALUES (?, ?, ?, ?, ?)", 
                           (upload_id, pr.batch_id, pr.batch_name, enr, name))
                inserted += 1
            except sqlite3.IntegrityError:
                skipped += 1
        
        conn.commit()
        conn.close()
        if batch_id in app.config['UPLOAD_CACHE']: del app.config['UPLOAD_CACHE'][batch_id]
        
        return jsonify({"success": True, "inserted": inserted, "skipped": skipped})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --------------------------------------------------
# Data Access (RESTORED)
# --------------------------------------------------
@app.route("/api/students", methods=["GET"])
def api_students():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM students ORDER BY id DESC LIMIT 1000")
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return jsonify(rows)

# --------------------------------------------------
# Allocation Routes (HYBRID MERGE)
# --------------------------------------------------
@app.route("/api/generate-seating", methods=["POST"])
def generate_seating():
    data = request.get_json(force=True)
    use_db = bool(data.get("use_demo_db", True))

    # Hybrid Logic: Switch between DB and raw inputs
    if use_db:
        counts, labels = get_batch_counts_and_labels_from_db()
        rolls = get_batch_roll_numbers_from_db()
        num_batches = len(counts)
    else:
        counts = parse_int_dict(data.get("batch_student_counts"))
        labels = parse_str_dict(data.get("batch_labels"))
        rolls = data.get("batch_roll_numbers") or {}
        num_batches = int(data.get("num_batches", 3))

    if SeatingAlgorithm is None:
        return jsonify({"error": "SeatingAlgorithm missing"}), 500

    broken_str = data.get("broken_seats", "")
    broken_seats = []
    if isinstance(broken_str, str) and "-" in broken_str:
        broken_seats = [(int(r)-1, int(c)-1) for r,c in (p.split("-") for p in broken_str.split(",") if "-" in p)]
    elif isinstance(broken_str, list):
        broken_seats = broken_str 

    algo = SeatingAlgorithm(
        rows=int(data.get("rows", 10)),
        cols=int(data.get("cols", 6)),
        num_batches=num_batches,
        block_width=int(data.get("block_width", 2)),
        batch_by_column=bool(data.get("batch_by_column", True)),
        enforce_no_adjacent_batches=bool(data.get("enforce_no_adjacent_batches", False)),
        broken_seats=broken_seats,
        batch_student_counts=counts,
        batch_roll_numbers=rolls,
        batch_labels=labels,
        start_rolls=parse_str_dict(data.get("start_rolls")),
        batch_colors=parse_str_dict(data.get("batch_colors")),
        serial_mode=data.get("serial_mode", "per_batch"),
        serial_width=int(data.get("serial_width", 0))
    )

    algo.generate_seating()
    web = algo.to_web_format()
    web.setdefault("metadata", {})
    
    ok, errors = algo.validate_constraints()
    web["validation"] = {"is_valid": ok, "errors": errors}
    return jsonify(web)

@app.route("/api/constraints-status", methods=["POST"])
def constraints_status():
    data = request.get_json(force=True)
    if SeatingAlgorithm is None: return jsonify({"error": "Module missing"}), 500
    algo = SeatingAlgorithm(
        rows=int(data.get("rows", 10)),
        cols=int(data.get("cols", 6)),
        num_batches=int(data.get("num_batches", 3)),
        block_width=int(data.get("block_width", 2)),
        batch_by_column=bool(data.get("batch_by_column", True)),
        enforce_no_adjacent_batches=bool(data.get("enforce_no_adjacent_batches", False))
    )
    algo.generate_seating()
    return jsonify(algo.get_constraints_status())

@app.route("/api/generate-pdf", methods=["POST"])
def generate_pdf():
    try:
        data = request.get_json(force=True)
        if not data or "seating" not in data: return jsonify({"error": "Invalid data"}), 400
        output_dir = BASE_DIR / "seat_plan_generated"
        output_dir.mkdir(exist_ok=True)
        filename = output_dir / f"seating_{int(time.time())}.pdf"
        
        if create_seating_pdf is None: return jsonify({"error": "PDF module missing"}), 500
        
        pdf_path = create_seating_pdf(filename=str(filename), data=data)
        return send_file(pdf_path, as_attachment=True, download_name=filename.name, mimetype="application/pdf")
    except Exception as e:
        return jsonify({"error": str(e)}), 500
# --------------------------------------------------
# Admin/Maintenance Routes (NEW)
# --------------------------------------------------
@app.route("/api/reset-data", methods=["POST"])
@token_required
def reset_data():
    """
    Clears all students, uploads, and previous allocations from demo.db.
    Does NOT affect user accounts (auth) or PDF templates.
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        
        # Clear tables relating to exam data
        cur.execute("DELETE FROM students")
        cur.execute("DELETE FROM uploads")
        cur.execute("DELETE FROM allocations")
        
        # Reset auto-increment counters (optional, but cleaner)
        cur.execute("DELETE FROM sqlite_sequence WHERE name='students'")
        cur.execute("DELETE FROM sqlite_sequence WHERE name='uploads'")
        cur.execute("DELETE FROM sqlite_sequence WHERE name='allocations'")
        
        conn.commit()
        conn.close()
        
        print("🧹 Database (demo.db) reset successfully.")
        return jsonify({"success": True, "message": "All student and allocation data has been cleared."})
        
    except Exception as e:
        print(f"❌ RESET ERROR: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

if __name__ == "__main__":
    print("✔ Allocation API running at http://127.0.0.1:5000")
    app.run(debug=True, port=5000)