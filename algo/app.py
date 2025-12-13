# app.py  (merged version)
import sys
import os
from pathlib import Path
from functools import wraps
from typing import Dict, List, Tuple

from flask import Flask, render_template_string, jsonify, request, send_file
from flask_cors import CORS
import sqlite3
import json
from werkzeug.utils import secure_filename
import csv
import uuid
import io

# Import StudentDataParser for robust file parsing
from student_parser import StudentDataParser

# --- adjust path so Backend (auth_service, database helpers) can be imported ---
# Assumes your project layout has a sibling folder "Backend" at the parent level
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "Backend"))
# If your Backend is elsewhere, change the path above appropriately

# Import seating algorithm
try:
    from algo import SeatingAlgorithm
except Exception as ex:
    raise RuntimeError("Failed to import algo.SeatingAlgorithm: " + str(ex))

# Import auth helpers from Backend/auth_service.py
# auth_service should export: signup, login, verify_token, get_user_by_token, update_user_profile
try:
    from auth_service import signup as auth_signup, login as auth_login, verify_token, get_user_by_token, update_user_profile  # noqa: F401
except Exception:
    # Fail gracefully but allow server to run for seating features
    auth_signup = auth_login = verify_token = get_user_by_token = update_user_profile = None

# -------------------------------------------------------------------
# App + paths
# -------------------------------------------------------------------
app = Flask(__name__)
CORS(app)

BASE_DIR = Path(__file__).parent.resolve()
DB_PATH = BASE_DIR / "demo.db"           # demo DB used for student uploads
INDEX_HTML = BASE_DIR / "index.html"     # optional admin UI/index page

# Load HTML template if present
if INDEX_HTML.exists():
    HTML_TEMPLATE = INDEX_HTML.read_text(encoding="utf-8")
else:
    HTML_TEMPLATE = "<html><body><h1>Seat Allocation API</h1><p>Use the JSON API endpoints.</p></body></html>"

# -------------------------------------------------------------------
# Utility: ensure demo DB schema exists (light bootstrap/migration)
# -------------------------------------------------------------------
def ensure_demo_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    # uploads table
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS uploads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            batch_id TEXT UNIQUE,
            batch_name TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    # students table (linked to uploads)
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            upload_id INTEGER,
            batch_id TEXT,
            batch_name TEXT,
            enrollment TEXT NOT NULL,
            name TEXT,
            meta TEXT,
            inserted_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(upload_id, enrollment)
        );
        """
    )
    # rooms & allocations (kept lightweight)
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS rooms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room_id TEXT UNIQUE,
            name TEXT,
            layout_json TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS allocations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id TEXT,
            upload_id INTEGER,
            batch_id TEXT,
            enrollment TEXT,
            room_id TEXT,
            seat_id TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    conn.commit()
    conn.close()

ensure_demo_db()

# -------------------------------------------------------------------
# Auth decorator
# -------------------------------------------------------------------
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if verify_token is None:
            return jsonify({"error": "Auth not configured on server"}), 501

        token = None
        if "Authorization" in request.headers:
            auth_header = request.headers["Authorization"]
            try:
                token = auth_header.split(" ")[1]
            except Exception:
                return jsonify({"error": "Invalid Authorization header"}), 401
        if not token:
            return jsonify({"error": "Token missing"}), 401

        payload = verify_token(token)
        if not payload:
            return jsonify({"error": "Invalid or expired token"}), 401

        # attach user id for route usage
        request.user_id = payload.get("user_id")
        return f(*args, **kwargs)
    return decorated

# -------------------------------------------------------------------
# Small helpers to read demo DB and produce batch mappings
# -------------------------------------------------------------------
def get_batch_counts_and_labels_from_db() -> Tuple[Dict[int,int], Dict[int,str]]:
    """
    Returns:
      - batch_student_counts: {1: count, 2: count, ...}
      - batch_labels: {1: batch_name, 2: batch_name, ...}
    Groups students by batch_name (alphabetical order) and assigns numeric keys.
    """
    if not DB_PATH.exists():
        return {}, {}
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT batch_name, COUNT(*) FROM students GROUP BY batch_name ORDER BY batch_name;")
    rows = cur.fetchall()
    conn.close()

    counts = {}
    labels = {}
    for idx, (batch_name, count) in enumerate(rows, start=1):
        name = batch_name if batch_name else f"BATCH{idx}"
        counts[idx] = int(count)
        labels[idx] = name
    return counts, labels

def get_batch_roll_numbers_from_db() -> Dict[int, List[str]]:
    """
    Build mapping of numeric batch index -> list of enrollment strings (in insertion order).
    Batches are grouped by batch_name and assigned numeric indices in sorted order.
    """
    if not DB_PATH.exists():
        return {}
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    # fetch all students ordered by upload/insert time
    cur.execute("SELECT batch_name, enrollment FROM students ORDER BY inserted_at, id;")
    rows = cur.fetchall()
    conn.close()

    # group by batch_name
    groups = {}
    for batch_name, enrollment in rows:
        groups.setdefault(batch_name or "UNKNOWN", []).append(str(enrollment))

    # map to numeric indices deterministically (sorted keys)
    batch_rolls = {}
    for idx, bn in enumerate(sorted(groups.keys()), start=1):
        batch_rolls[idx] = groups[bn]
    return batch_rolls

# -------------------------------------------------------------------
# Authentication endpoints (if auth_service present)
# -------------------------------------------------------------------
@app.route("/api/auth/signup", methods=["POST"])
def signup():
    if auth_signup is None:
        return jsonify({"error": "Auth not configured"}), 501
    try:
        data = request.get_json(force=True)
        username = data.get("username", "").strip()
        email = data.get("email", "").strip()
        password = data.get("password", "")
        role = data.get("role", "STUDENT")
        success, message = auth_signup(username, email, password, role)
        if success:
            return jsonify({"success": True, "message": message}), 201
        return jsonify({"success": False, "error": message}), 400
    except Exception as e:
        return jsonify({"error": f"Signup failed: {str(e)}"}), 500

@app.route("/api/auth/login", methods=["POST"])
def login():
    if auth_login is None:
        return jsonify({"error": "Auth not configured"}), 501
    try:
        data = request.get_json(force=True)
        email = data.get("email", "").strip()
        password = data.get("password", "")
        ok, user, result = auth_login(email, password)
        if ok:
            return jsonify({"success": True, "token": result, "user": user}), 200
        return jsonify({"success": False, "error": result}), 401
    except Exception as e:
        return jsonify({"error": f"Login failed: {str(e)}"}), 500

@app.route("/api/auth/profile", methods=["GET"])
@token_required
def profile_get():
    if get_user_by_token is None:
        return jsonify({"error": "Auth not configured"}), 501
    try:
        token = request.headers.get("Authorization", "").split(" ")[1]
        user = get_user_by_token(token)
        if not user:
            return jsonify({"error": "User not found"}), 404
        return jsonify({"success": True, "user": user}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/auth/profile", methods=["PUT"])
@token_required
def profile_put():
    if update_user_profile is None:
        return jsonify({"error": "Auth not configured"}), 501
    try:
        body = request.get_json(force=True)
        username = body.get("username")
        email = body.get("email")
        ok, msg = update_user_profile(request.user_id, username, email)
        if ok:
            # return updated user
            token = request.headers.get("Authorization", "").split(" ")[1]
            user = get_user_by_token(token)
            return jsonify({"success": True, "message": msg, "user": user}), 200
        return jsonify({"success": False, "error": msg}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/auth/logout", methods=["POST"])
def logout():
    # logout is client-side token removal in this simple setup
    return jsonify({"success": True, "message": "Logged out"}), 200

# -------------------------------------------------------------------
# Students listing endpoint (for demo UI / tooling)
# -------------------------------------------------------------------
@app.route("/api/students", methods=["GET"])
def api_students():
    """
    Returns students stored in demo.db.
    Optional query params:
      - batch_id (string)
      - upload_id (integer)
    """
    batch_id = request.args.get("batch_id")
    upload_id = request.args.get("upload_id")

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    try:
        if upload_id:
            cur.execute(
                "SELECT id, upload_id, batch_id, batch_name, enrollment, name, inserted_at FROM students WHERE upload_id=? ORDER BY id",
                (upload_id,),
            )
        elif batch_id:
            cur.execute(
                "SELECT id, upload_id, batch_id, batch_name, enrollment, name, inserted_at FROM students WHERE batch_id=? ORDER BY id",
                (batch_id,),
            )
        else:
            cur.execute(
                "SELECT id, upload_id, batch_id, batch_name, enrollment, name, inserted_at FROM students ORDER BY id DESC LIMIT 1000"
            )
        rows = cur.fetchall()
    except Exception as e:
        conn.close()
        return jsonify({"error": str(e)}), 500

    conn.close()

    out = []
    for r in rows:
        out.append(
            {
                "id": r["id"],
                "upload_id": r["upload_id"],
                "batch_id": r["batch_id"],
                "batch_name": r["batch_name"],
                "enrollment": r["enrollment"],
                "name": r["name"],
                "inserted_at": r["inserted_at"],
            }
        )
    return jsonify(out)

# -------------------------------------------------------------------
# Upload file endpoint (preview mode, no DB write yet)
# -------------------------------------------------------------------
@app.route("/api/upload", methods=["POST"])
def api_upload():
    """
    Parse CSV/XLSX file and return preview without writing to DB.
    Uses robust StudentDataParser for handling various file formats.
    
    Form data:
      - file: CSV or XLSX file
      - mode: "1" (enrollment only) or "2" (name + enrollment)
      - batch_name: name of batch (e.g., "CSE")
    
    Returns:
      {
        "batch_id": unique ID for this preview,
        "batch_name": batch name,
        "rows_total": total rows in file,
        "rows_extracted": rows successfully parsed,
        "warnings": list of parsing issues,
        "sample": first 5 parsed rows
      }
    """
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400
    
    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "Empty filename"}), 400
    
    mode = int(request.form.get("mode", "2"))
    batch_name = request.form.get("batch_name", "BATCH1")
    
    try:
        # Initialize parser
        parser = StudentDataParser()
        
        # Read file content into bytes
        file.seek(0)
        file_bytes = file.read()
        
        # Parse using StudentDataParser
        parse_result = parser.parse_file(
            file_bytes,
            mode=mode,
            batch_name=batch_name
        )
        
        # Convert ParseResult to API response format
        # parse_result.data is {"batch_name": [...rows...]}
        sample_data = parse_result.data.get(batch_name, [])[:5]
        
        # Transform warnings to user-friendly format
        warnings_list = []
        for w in parse_result.warnings:
            if isinstance(w, dict):
                warnings_list.append(w)
            else:
                warnings_list.append({"message": str(w)})
        
        # Store parsed data in cache for later commit
        if not hasattr(app, 'upload_cache'):
            app.upload_cache = {}
        
        app.upload_cache[parse_result.batch_id] = {
            "batch_name": batch_name,
            "mode": mode,
            "parsed_data": parse_result.data.get(batch_name, [])
        }
        
        return jsonify({
            "batch_id": parse_result.batch_id,
            "batch_name": batch_name,
            "rows_total": parse_result.rows_total,
            "rows_extracted": parse_result.rows_extracted,
            "warnings": warnings_list,
            "sample": sample_data
        }), 200
    
    except Exception as e:
        return jsonify({"error": f"Parse error: {str(e)}"}), 500


# -------------------------------------------------------------------
# Commit upload endpoint (write to DB)
# -------------------------------------------------------------------
@app.route("/api/commit-upload", methods=["POST"])
def api_commit_upload():
    """
    Commit a previewed upload to the demo DB.
    
    JSON body:
      {
        "batch_id": batch ID from preview
      }
    
    Returns:
      {
        "success": true,
        "inserted": count of inserted rows,
        "skipped": count of skipped rows (duplicates)
      }
    """
    data = request.get_json()
    batch_id = data.get("batch_id")
    
    if not batch_id:
        return jsonify({"error": "Missing batch_id"}), 400
    
    # Retrieve cached parsed data
    if not hasattr(app, 'upload_cache') or batch_id not in app.upload_cache:
        return jsonify({"error": "Preview data expired or not found"}), 400
    
    cache_data = app.upload_cache[batch_id]
    batch_name = cache_data["batch_name"]
    mode = cache_data.get("mode", 2)
    parsed_data = cache_data["parsed_data"]
    
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    try:
        # Create upload record
        cur.execute(
            "INSERT INTO uploads (batch_id, batch_name) VALUES (?, ?)",
            (batch_id, batch_name)
        )
        upload_id = cur.lastrowid
        
        inserted = 0
        skipped = 0
        
        # Insert students - handle both mode 1 (strings) and mode 2 (dicts)
        for row in parsed_data:
            if mode == 1:
                # Mode 1: row is just an enrollment string
                enrollment = row if isinstance(row, str) else ""
                name = None
            else:
                # Mode 2: row is a dict with 'enrollmentNo' and 'name'
                enrollment = row.get("enrollmentNo", "") if isinstance(row, dict) else row
                name = row.get("name") if isinstance(row, dict) else None
            
            if not enrollment:
                skipped += 1
                continue
            
            try:
                cur.execute(
                    "INSERT INTO students (upload_id, batch_id, batch_name, enrollment, name) VALUES (?, ?, ?, ?, ?)",
                    (upload_id, batch_id, batch_name, enrollment, name)
                )
                inserted += 1
            except sqlite3.IntegrityError:
                # Duplicate enrollment in this upload
                skipped += 1
        
        conn.commit()
        
        # Clean up cache
        del app.upload_cache[batch_id]
        
        return jsonify({
            "success": True,
            "inserted": inserted,
            "skipped": skipped
        }), 201
    
    except Exception as e:
        conn.rollback()
        return jsonify({"error": f"Commit error: {str(e)}"}), 500
    finally:
        conn.close()

# -------------------------------------------------------------------
# Generate seating (main endpoint)
# -------------------------------------------------------------------
@app.route("/api/generate-seating", methods=["POST"])
def generate_seating():
    """
    POST JSON:
        rows, cols, num_batches, block_width, batch_by_column,
        enforce_no_adjacent_batches, broken_seats (CSV of r-c),
        use_demo_db (bool) -> if true, pull batch info from demo.db
        other roll-formatting options...
    Response: seating JSON from SeatingAlgorithm.to_web_format()
    """
    try:
        data = request.get_json(force=True)

        rows = int(data.get("rows", 10))
        cols = int(data.get("cols", 15))
        num_batches = int(data.get("num_batches", 3))
        block_width = int(data.get("block_width", 3))
        batch_by_column = bool(data.get("batch_by_column", True))
        enforce_no_adjacent_batches = bool(data.get("enforce_no_adjacent_batches", False))
        use_demo_db = bool(data.get("use_demo_db", False))

        # Parse broken seats "r-c,r-c"
        broken_seats = []
        broken_seats_str = data.get("broken_seats", "")
        if broken_seats_str:
            for part in [p.strip() for p in broken_seats_str.split(",") if p.strip()]:
                if "-" in part:
                    try:
                        r, c = part.split("-", 1)
                        r0 = int(r.strip()) - 1
                        c0 = int(c.strip()) - 1
                        if 0 <= r0 < rows and 0 <= c0 < cols:
                            broken_seats.append((r0, c0))
                    except Exception:
                        pass

        # Basic roll-formatting inputs (kept compatible with your previous UI)
        roll_template = data.get("roll_template")
        batch_prefixes_csv = data.get("batch_prefixes", "")
        batch_prefixes = {}
        if batch_prefixes_csv:
            parts = [p.strip() for p in batch_prefixes_csv.split(",") if p.strip()]
            for i, p in enumerate(parts):
                batch_prefixes[i + 1] = p
        year = data.get("year")
        try:
            year = int(year) if year not in (None, "") else None
        except Exception:
            year = None
        start_serial = int(data.get("start_serial", 1))
        serial_width = int(data.get("serial_width", 0))
        serial_mode = data.get("serial_mode", "per_batch")

        # Decide batch_student_counts, batch_labels, batch_roll_numbers
        batch_student_counts = {}
        batch_labels = {}
        batch_roll_numbers = {}

        if use_demo_db:
            # Pull counts & labels and real enrollments from demo DB
            batch_student_counts, batch_labels = get_batch_counts_and_labels_from_db()
            batch_roll_numbers = get_batch_roll_numbers_from_db()
            # If DB returned batches, update num_batches to match
            if batch_student_counts:
                num_batches = len(batch_student_counts)
        else:
            # parse string "1:35,2:30"
            bcounts = data.get("batch_student_counts", "")
            if bcounts:
                for part in [p.strip() for p in bcounts.split(",") if p.strip()]:
                    if ":" in part:
                        try:
                            k, v = part.split(":", 1)
                            batch_student_counts[int(k.strip())] = int(v.strip())
                        except Exception:
                            pass
            # optional explicit roll lists passed in JSON as object { "1": ["ENR1",...], "2":[...] }
            brn = data.get("batch_roll_numbers")
            if isinstance(brn, dict):
                # ensure keys are ints
                for k, arr in brn.items():
                    try:
                        ik = int(k)
                    except Exception:
                        continue
                    if isinstance(arr, list):
                        batch_roll_numbers[ik] = [str(x) for x in arr if x]
            # optional batch labels mapping
            bl = data.get("batch_labels")
            if isinstance(bl, dict):
                for k, v in bl.items():
                    try:
                        ik = int(k)
                        batch_labels[ik] = str(v)
                    except Exception:
                        pass

        # Colors
        batch_colors = {}
        bc_str = data.get("batch_colors", "")
        if bc_str:
            for part in [p.strip() for p in bc_str.split(",") if p.strip()]:
                if ":" in part:
                    try:
                        k, v = part.split(":", 1)
                        batch_colors[int(k.strip())] = v.strip()
                    except Exception:
                        pass

        # Basic validation
        if rows < 1 or cols < 1 or num_batches < 1 or num_batches > 200:
            return jsonify({"error": "Invalid rows/cols/num_batches"}), 400
        if block_width < 1 or block_width > cols:
            return jsonify({"error": "Invalid block_width"}), 400

        # Build algorithm instance
        algorithm = SeatingAlgorithm(
            rows=rows,
            cols=cols,
            num_batches=num_batches,
            block_width=block_width,
            batch_by_column=batch_by_column,
            enforce_no_adjacent_batches=enforce_no_adjacent_batches,
            roll_template=roll_template,
            batch_prefixes=batch_prefixes,
            year=year,
            start_serial=start_serial,
            start_serials=data.get("start_serials", {}),
            start_rolls=data.get("start_rolls", {}),
            serial_width=serial_width,
            serial_mode=serial_mode,
            broken_seats=broken_seats,
            batch_student_counts=batch_student_counts,
            batch_colors=batch_colors,
            batch_roll_numbers=batch_roll_numbers,
            batch_labels=batch_labels,
        )

        algorithm.generate_seating()
        is_valid, errors = algorithm.validate_constraints()
        web_data = algorithm.to_web_format()
        web_data["validation"] = {"is_valid": is_valid, "errors": errors}
        web_data["constraints_status"] = algorithm.get_constraints_status()
        if batch_labels:
            web_data["batch_labels"] = batch_labels
        return jsonify(web_data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# -------------------------------------------------------------------
# Constraints status endpoint (quick check)
# -------------------------------------------------------------------
@app.route("/api/constraints-status", methods=["POST"])
def constraints_status():
    try:
        data = request.get_json(force=True)
        rows = int(data.get("rows", 10))
        cols = int(data.get("cols", 15))
        num_batches = int(data.get("num_batches", 3))
        block_width = int(data.get("block_width", 3))
        batch_by_column = bool(data.get("batch_by_column", True))
        enforce_no_adjacent_batches = bool(data.get("enforce_no_adjacent_batches", False))

        broken_seats = []
        broken_seats_str = data.get("broken_seats", "")
        if broken_seats_str:
            for part in [p.strip() for p in broken_seats_str.split(",") if p.strip()]:
                if "-" in part:
                    try:
                        r, c = part.split("-", 1)
                        r0 = int(r.strip()) - 1
                        c0 = int(c.strip()) - 1
                        if 0 <= r0 < rows and 0 <= c0 < cols:
                            broken_seats.append((r0, c0))
                    except Exception:
                        pass

        algorithm = SeatingAlgorithm(
            rows=rows,
            cols=cols,
            num_batches=num_batches,
            block_width=block_width,
            batch_by_column=batch_by_column,
            enforce_no_adjacent_batches=enforce_no_adjacent_batches,
            broken_seats=broken_seats,
        )
        algorithm.generate_seating()
        return jsonify(algorithm.get_constraints_status())
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# -------------------------------------------------------------------
# Minimal index route
# -------------------------------------------------------------------
@app.route("/")
def index():
    return render_template_string(HTML_TEMPLATE)

# -------------------------------------------------------------------
# PDF generation helper
# -------------------------------------------------------------------
def create_seating_pdf(filename: str, data: Dict) -> str:
    """
    Create a PDF from seating data using ReportLab.
    Returns the filepath where the PDF was saved.
    
    Args:
        filename: Output filename (e.g., 'seat_plan_generated/seating_1234567890.pdf')
        data: Dictionary containing seating arrangement data
    """
    try:
        from reportlab.lib.pagesizes import landscape, A4
        from reportlab.pdfgen import canvas
        from reportlab.lib.units import mm
    except ImportError:
        raise RuntimeError("reportlab not installed. Install with: pip install reportlab")
    
    # Create directory if it doesn't exist
    output_dir = BASE_DIR / "seat_plan_generated"
    output_dir.mkdir(parents=True, exist_ok=True)
    filepath = output_dir / filename.split('/')[-1]
    
    # Get seating data
    seating = data.get('seating', [])
    if not seating:
        raise ValueError("No seating data provided")
    
    rows = len(seating)
    cols = len(seating[0]) if rows > 0 else 0
    
    # Create PDF
    c = canvas.Canvas(str(filepath), pagesize=landscape(A4))
    width, height = landscape(A4)
    
    # Title
    c.setFont("Helvetica-Bold", 16)
    c.drawString(mm * 10, height - mm * 15, "Seating Arrangement Plan")
    
    # Metadata
    c.setFont("Helvetica", 10)
    c.drawString(mm * 10, height - mm * 20, f"Rows: {rows} | Columns: {cols} | Generated: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Draw seats in grid
    seat_width = (width - mm * 20) / cols
    seat_height = (height - mm * 35) / rows
    
    c.setLineWidth(0.5)
    for r_idx, row in enumerate(seating):
        for c_idx, seat in enumerate(row):
            x = mm * 10 + c_idx * seat_width
            y = height - mm * 30 - (r_idx + 1) * seat_height
            
            # Draw seat box
            if seat and seat.get('is_broken'):
                c.setFillColorRGB(1, 0, 0)  # Red for broken
                c.rect(x, y, seat_width, seat_height, fill=1, stroke=1)
                c.setFont("Helvetica-Bold", 7)
                c.setFillColorRGB(1, 1, 1)
                c.drawCentredString(x + seat_width/2, y + seat_height/2 + 2, "BROKEN")
            elif seat and seat.get('is_unallocated'):
                c.setFillColorRGB(0.95, 0.95, 0.95)  # Light gray
                c.rect(x, y, seat_width, seat_height, fill=1, stroke=1)
                c.setFont("Helvetica", 6)
                c.setFillColorRGB(0.2, 0.2, 0.2)
                c.drawCentredString(x + seat_width/2, y + seat_height/2, "UNALLOC")
            elif seat:
                # Parse hex color from seat data
                color_hex = seat.get('color', '#ffffff')
                if color_hex.startswith('#'):
                    r = int(color_hex[1:3], 16) / 255.0
                    g = int(color_hex[3:5], 16) / 255.0
                    b = int(color_hex[5:7], 16) / 255.0
                    c.setFillColorRGB(r, g, b)
                else:
                    c.setFillColorRGB(1, 1, 1)
                
                c.rect(x, y, seat_width, seat_height, fill=1, stroke=1)
                
                # Draw seat info
                c.setFont("Helvetica-Bold", 6)
                c.setFillColorRGB(0.1, 0.1, 0.1)
                roll = seat.get('roll_number', '')
                batch = seat.get('batch_label', f"B{seat.get('batch', '')}")
                c.drawCentredString(x + seat_width/2, y + seat_height/2 + 4, batch)
                c.drawCentredString(x + seat_width/2, y + seat_height/2 - 2, roll)
    
    c.save()
    return str(filepath)

# -------------------------------------------------------------------
# PDF generation endpoint
# -------------------------------------------------------------------
@app.route('/api/generate-pdf', methods=['POST'])
def generate_pdf():
    """Generate PDF from seating data"""
    try:
        data = request.get_json()
        if not data or 'seating' not in data:
            return jsonify({"error": "Invalid seating data"}), 400
        
        filename = f"seat_plan_generated/seating_{int(__import__('time').time())}.pdf"
        filepath = create_seating_pdf(filename=filename, data=data)
        
        return send_file(filepath, as_attachment=True, download_name=filename)
    except Exception as e:
        return jsonify({"error": str(e)}), 500



if __name__ == "__main__":
    print("Allocation + Auth server running at http://127.0.0.1:5000")
    app.run(debug=True, port=5000)
