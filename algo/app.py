import sys
import os
from datetime import datetime
import time
import io  # ✅ FIXED: Added missing import
import json
import sqlite3
from pathlib import Path
from functools import wraps
from typing import Dict, List, Tuple

from flask import Flask, jsonify, request, send_file,render_template_string,session,render_template
from flask_cors import CORS

from pdf_gen.pdf_generation import get_or_create_seating_pdf
from pdf_gen.template_manager import template_manager
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

# ============================================================================
#   PDF GENERATION CONNECTION
# (Unchanged)
# ============================================================================
@app.route('/template-editor')
def template_editor():
    """Serve the template editor interface (from the templates folder)"""
    # NOTE: Since we changed Flask configuration, if 'template_editor.html'
    # is still a separate file, you should ensure it is in the 'templates' folder
    # or handle it as part of the React build. 
    # If the TemplateEditor is a React component, this route should also use render_template('index.html')
    # and let React Router handle the /template-editor path.
    return render_template('template_editor.html')

# ... (rest of the PDF routes are unchanged)

@app.route('/api/template-config', methods=['GET', 'POST'])
def manage_template():
    # ... (function body unchanged)
    user_id = 'test_user'
    template_name = request.args.get('template_name', 'default')
    
    if request.method == 'GET':
        try:
            template = template_manager.get_user_template(user_id, template_name)
            return jsonify({
                'success': True,
                'template': template,
                'user_id': user_id
            })
        except Exception as e:
            return jsonify({'error': f'Failed to load template: {str(e)}'}), 500
    
    elif request.method == 'POST':
        try:
            template_data = request.form.to_dict()
            print(f"📝 Updating template for test user: {list(template_data.keys())}")
            
            # Handle banner image upload
            if 'bannerImage' in request.files:
                file = request.files['bannerImage']
                if file and file.filename:
                    image_path = template_manager.save_user_banner(user_id, file, template_name)
                    if image_path:
                        template_data['banner_image_path'] = image_path
                        print(f"🖼️ Banner uploaded: {image_path}")
            
            # Save template
            template_manager.save_user_template(user_id, template_data, template_name)
            
            return jsonify({
                'success': True,
                'message': 'Template updated successfully',
                'template': template_manager.get_user_template(user_id, template_name)
            })
            
        except Exception as e:
            print(f"❌ Template update error: {e}")
            return jsonify({'error': f'Failed to update template: {str(e)}'}), 500


# Updated PDF generation route (modify your existing one)
@app.route('/api/generate-pdf', methods=['POST'])
def generate_pdf():
    # ... (function body unchanged)
    try:
        data = request.get_json()
        if not data or 'seating' not in data:
            return jsonify({"error": "Invalid seating data"}), 400
        
        # Use test user for templates, but keep backward compatibility
        user_id = 'test_user'
        template_name = request.args.get('template_name', 'default')
        
        print(f"📊 Generating PDF for test user with template: {template_name}")
        
        # Uses user-specific templates
        pdf_path = get_or_create_seating_pdf(data, user_id=user_id, template_name=template_name)
        
        return send_file(
            pdf_path,
            as_attachment=True,
            download_name=f"seating_plan_{datetime.now().strftime('%Y%m%d%H%M%S')}.pdf"
        )
    except Exception as e:
        print(f"❌ PDF generation error: {e}")
        return jsonify({"error": str(e)}), 500

# Test PDF generation with sample data
@app.route('/api/test-pdf', methods=['GET'])
def test_pdf():
    # ... (function body unchanged)
    user_id = 'test_user'
    template_name = request.args.get('template_name', 'default')
    
    sample_data = {
        'seating': [
            [
                {'roll_number': '2021001', 'paper_set': 'A', 'color': '#e3f2fd'},
                {'roll_number': '2021002', 'paper_set': 'B', 'color': '#f3e5f5'},
                {'roll_number': '2021003', 'paper_set': 'A', 'color': '#e8f5e8'}
            ],
            [
                {'roll_number': '2021004', 'paper_set': 'B', 'color': '#fff3e0'},
                {'is_broken': True, 'display': 'BROKEN', 'color': '#ffebee'},
                {'roll_number': '2021005', 'paper_set': 'A', 'color': '#e3f2fd'}
            ]
        ],
        'metadata': {'rows': 2, 'cols': 3, 'blocks': 1, 'block_width': 3}
    }
    
    try:
        pdf_path = get_or_create_seating_pdf(sample_data, user_id=user_id, template_name=template_name)
        return send_file(
            pdf_path,
            as_attachment=True,
            download_name=f"test_seating_plan.pdf"
        )
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