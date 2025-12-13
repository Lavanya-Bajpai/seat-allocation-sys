# Upload API Integration - Complete Flow

## Endpoints Added

### 1. POST /api/upload
**Purpose**: Parse CSV file and preview data without writing to DB

**Request**:
```
POST /api/upload
Content-Type: multipart/form-data

file: [CSV file]
mode: "1" or "2" (1=enrollment only, 2=name+enrollment)
batch_name: "CSE" (or any batch name)
```

**Response** (200 OK):
```json
{
  "batch_id": "a1b2c3d4",
  "batch_name": "CSE",
  "rows_total": 50,
  "rows_extracted": 48,
  "warnings": [
    "Row 5: Missing enrollment",
    "Row 23: Missing enrollment"
  ],
  "sample": [
    {"enrollment": "CSE001", "name": "John Doe"},
    {"enrollment": "CSE002", "name": "Jane Smith"},
    ...
  ]
}
```

**Key Features**:
- Parses CSV and shows preview
- Generates unique batch_id for this preview
- Caches parsed data in app.upload_cache (in-memory)
- Shows warnings for invalid rows
- Returns sample of first 5 rows


### 2. POST /api/commit-upload
**Purpose**: Commit the previewed upload to the database

**Request**:
```json
{
  "batch_id": "a1b2c3d4"
}
```

**Response** (201 Created):
```json
{
  "success": true,
  "inserted": 48,
  "skipped": 0
}
```

**Key Features**:
- Retrieves cached data using batch_id
- Creates upload record in uploads table
- Inserts all students into students table
- Handles duplicate enrollments gracefully (skips them)
- Cleans up cache after commit
- Returns count of inserted/skipped rows


### 3. GET /api/students (Already Existing)
**Purpose**: Retrieve stored students

**Query Parameters**:
- `batch_id`: Filter by batch_id
- `upload_id`: Filter by upload_id

**Response**:
```json
[
  {
    "id": 1,
    "upload_id": 1,
    "batch_id": "CSE",
    "batch_name": "CSE",
    "enrollment": "CSE001",
    "name": "John Doe",
    "inserted_at": "2025-12-12 10:30:00"
  },
  ...
]
```


## Database Schema

### uploads table
```sql
id              INTEGER PRIMARY KEY AUTOINCREMENT
batch_id        TEXT UNIQUE
batch_name      TEXT
created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
```

### students table
```sql
id              INTEGER PRIMARY KEY AUTOINCREMENT
upload_id       INTEGER
batch_id        TEXT
batch_name      TEXT
enrollment      TEXT NOT NULL
name            TEXT
inserted_at     DATETIME DEFAULT CURRENT_TIMESTAMP
UNIQUE(upload_id, enrollment)
```


## Frontend Flow (UploadPage.jsx)

### Step 1: Upload & Preview
```javascript
// User selects file, chooses mode, enters batch name
// Click "Upload & Preview"
const fd = new FormData();
fd.append("file", file);
fd.append("mode", mode);
fd.append("batch_name", batchName);

const res = await fetch("/api/upload", { method: "POST", body: fd });
const preview = await res.json();
// preview.batch_id is stored for next step
```

### Step 2: Review Data
- Shows preview table with sample rows
- Shows warnings if any
- Shows stats (rows_total, rows_extracted, batch_id)

### Step 3: Commit to DB
```javascript
// User reviews and clicks "Commit to demo DB"
const res = await fetch("/api/commit-upload", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ batch_id: preview.batch_id })
});
const result = await res.json();
// result.inserted, result.skipped
```

### Step 4: View Stored Students
- Refreshes student list from GET /api/students
- Shows all uploaded students
- Can filter by batch_id


## CSV File Format

### Mode 1 (Enrollment only)
```
enrollment
CSE001
CSE002
CSE003
```

### Mode 2 (Name + Enrollment)
```
name,enrollment
John Doe,CSE001
Jane Smith,CSE002
Bob Johnson,CSE003
```

**Note**: Column names are case-insensitive (enrollment, Enrollment, ENROLLMENT all work)


## Error Handling

### Upload Errors
- No file provided → 400
- Empty filename → 400
- Parse error → 500 (with error message)
- Unsupported file format (non-CSV) → 400

### Commit Errors
- Missing batch_id → 400
- Preview data expired → 400
- Database error → 500

### Student Insertion Errors
- Duplicate enrollment in same upload → skipped (counted but not inserted)
- Other DB errors → commit fails entirely


## Caching Strategy

**Current**: In-memory app.upload_cache (dictionary)

**Issues**:
- Lost on server restart
- Not shared across multiple server instances
- No automatic expiry

**Production Recommendations**:
- Use Redis for distributed caching
- Add TTL (Time To Live) for previews (e.g., 30 minutes)
- Implement cleanup job for expired previews


## Testing

### Sample CSV
```
name,enrollment
Alice,E001
Bob,E002
Charlie,E003
David,E004
Eve,E005
```

### Test Flow
1. Save above as `test.csv`
2. Go to Upload page
3. Select Mode 2 (Name + Enrollment)
4. Enter batch name "TEST"
5. Upload file
6. Should see preview with 5 students
7. Click "Commit to demo DB"
8. Should see "Inserted: 5, Skipped: 0"
9. Go to Students list (right panel)
10. Should see all 5 students listed


## API Sequence Diagram

```
User                Frontend              Backend
 |                    |                     |
 |-- Select File ----->|                     |
 |                    |-- POST /api/upload -->|
 |                    |<-- batch_id + sample---|
 |                    |                     |
 |-- Review Preview -->|                     |
 |                    |                     |
 |-- Click Commit ---->|                     |
 |                    |-- POST /api/commit -->|
 |                    |<-- inserted count ---|
 |                    |                     |
 |-- Refresh List ---->|                     |
 |                    |-- GET /api/students-->|
 |                    |<-- student list ---|
 |                    |                     |
```


## Next Steps

1. ✅ Endpoints created
2. ✅ Database integration
3. ⏳ Test with actual CSV files
4. ⏳ Add XLSX support (requires openpyxl)
5. ⏳ Implement Redis caching for production
6. ⏳ Add file size validation
7. ⏳ Add progress tracking for large files
