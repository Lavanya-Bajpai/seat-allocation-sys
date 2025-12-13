# parser_app.py
"""
Student Parser Service
----------------------
Responsibilities:
- Upload CSV/XLSX
- Preview parsed students
- Commit uploads to demo.db
- Expose stored students

This file is intentionally boring and stable.
DO NOT merge allocation logic here.
"""

import json
import sqlite3
from pathlib import Path

from flask import Flask, request, jsonify
from flask_cors import CORS

from student_parser import StudentDataParser, ParseResult

# -------------------------------------------------------------------
# App & Paths
# -------------------------------------------------------------------
app = Flask(__name__)
CORS(app)

BASE_DIR = Path(__file__).parent.resolve()
DB_PATH = BASE_DIR / "demo.db"
PREVIEWS_DIR = BASE_DIR / "previews"
PREVIEWS_DIR.mkdir(exist_ok=True)

parser = StudentDataParser()

# -------------------------------------------------------------------
# DB bootstrap (SAFE, backward compatible)
# -------------------------------------------------------------------
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
            batch_id TEXT NOT NULL,
            batch_name TEXT,
            enrollment TEXT NOT NULL,
            name TEXT,
            meta TEXT,
            inserted_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (upload_id) REFERENCES uploads(id),
            UNIQUE(upload_id, enrollment)
        );
    """)

    # Light migration support
    cur.execute("PRAGMA table_info(students);")
    cols = [r[1] for r in cur.fetchall()]

    if "meta" not in cols:
        cur.execute("ALTER TABLE students ADD COLUMN meta TEXT;")

    conn.commit()
    conn.close()

ensure_demo_db()

# -------------------------------------------------------------------
# Upload → Preview
# -------------------------------------------------------------------
@app.route("/api/upload", methods=["POST"])
def api_upload():
    """
    multipart/form-data:
      - file
      - mode: 1 or 2
      - batch_name
    """
    try:
        file = request.files.get("file")
        if not file:
            return jsonify({"error": "No file uploaded"}), 400

        mode = int(request.form.get("mode", 2))
        batch_name = request.form.get("batch_name", "BATCH1")

        pr: ParseResult = parser.parse_file(file, mode=mode, batch_name=batch_name)

        preview_path = PREVIEWS_DIR / f"{pr.batch_id}.json"
        preview_path.write_text(parser.to_json_str(pr), encoding="utf-8")

        sample = pr.data.get(pr.batch_name, [])[:10]

        return jsonify({
            "batch_id": pr.batch_id,
            "batch_name": pr.batch_name,
            "rows_total": pr.rows_total,
            "rows_extracted": pr.rows_extracted,
            "warnings": pr.warnings,
            "errors": pr.errors,
            "sample": sample
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# -------------------------------------------------------------------
# Commit Upload
# -------------------------------------------------------------------
@app.route("/api/commit-upload", methods=["POST"])
def api_commit_upload():
    try:
        body = request.get_json(force=True)
        batch_id = body.get("batch_id")
        if not batch_id:
            return jsonify({"error": "batch_id required"}), 400

        preview_path = PREVIEWS_DIR / f"{batch_id}.json"
        if not preview_path.exists():
            return jsonify({"error": "Preview not found"}), 404

        pr_dict = json.loads(preview_path.read_text(encoding="utf-8"))
        batch_name = pr_dict.get("batch_name")
        rows = pr_dict.get("data", {}).get(batch_name, [])

        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()

        cur.execute("""
            INSERT OR IGNORE INTO uploads (batch_id, batch_name)
            VALUES (?, ?)
        """, (batch_id, batch_name))
        conn.commit()

        cur.execute("SELECT id FROM uploads WHERE batch_id = ?", (batch_id,))
        upload_id = cur.fetchone()[0]

        inserted, skipped = 0, 0

        for r in rows:
            if isinstance(r, str):
                enrollment, name = r.strip(), None
            else:
                enrollment = str(r.get("enrollmentNo", "")).strip()
                name = str(r.get("name", "")).strip() if r.get("name") else None

            if not enrollment:
                skipped += 1
                continue

            try:
                cur.execute("""
                    INSERT INTO students
                    (upload_id, batch_id, batch_name, enrollment, name, meta)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (upload_id, batch_id, batch_name, enrollment, name, json.dumps({})))
                inserted += 1
            except sqlite3.IntegrityError:
                skipped += 1

        conn.commit()
        conn.close()

        return jsonify({
            "upload_id": upload_id,
            "batch_id": batch_id,
            "inserted": inserted,
            "skipped": skipped
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# -------------------------------------------------------------------
# Students Listing
# -------------------------------------------------------------------
@app.route("/api/students", methods=["GET"])
def api_students():
    batch_id = request.args.get("batch_id")
    upload_id = request.args.get("upload_id")

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    sql = """
        SELECT s.id, s.upload_id, s.batch_id, s.batch_name,
               s.enrollment, s.name, s.inserted_at
        FROM students s
    """
    params = []

    if upload_id:
        sql += " WHERE s.upload_id = ?"
        params.append(upload_id)
    elif batch_id:
        sql += " WHERE s.batch_id = ?"
        params.append(batch_id)

    sql += " ORDER BY s.upload_id DESC, s.id ASC LIMIT 1000"

    cur.execute(sql, params)
    rows = cur.fetchall()
    conn.close()

    return jsonify([dict(r) for r in rows])

# -------------------------------------------------------------------
# Run
# -------------------------------------------------------------------
if __name__ == "__main__":
    print("Parser service running at http://127.0.0.1:5001")
    app.run(debug=True, port=5001)
