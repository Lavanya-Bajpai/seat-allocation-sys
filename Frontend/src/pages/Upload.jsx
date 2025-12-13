// frontend/src/pages/UploadPage.jsx
import React, { useState, useEffect, useRef } from "react";

/**
 * UploadPage.jsx
 * Student Parser UI (Upload → Preview → Commit)
 *
 * - Uses /api/upload (multipart/form-data)
 * - Uses /api/commit-upload (POST JSON { batch_id })
 * - Uses /api/students (GET) to show stored students
 *
 * Tailwind-based styling.
 */

const UploadPage = () => {
  const [file, setFile] = useState(null);
  const [mode, setMode] = useState("2"); // "2" -> Name+Enrollment, "1" -> Enrollment-only
  const [batchName, setBatchName] = useState("CSE");
  const [uploading, setUploading] = useState(false);
  const [preview, setPreview] = useState(null);
  const [uploadError, setUploadError] = useState(null);
  const [commitLoading, setCommitLoading] = useState(false);
  const [commitResult, setCommitResult] = useState(null);

  const [students, setStudents] = useState([]);
  const [studentsLoading, setStudentsLoading] = useState(false);
  const [studentsError, setStudentsError] = useState(null);
  const [filterBatchId, setFilterBatchId] = useState("");

  const fileInputRef = useRef();

  useEffect(() => {
    fetchStudents();
  }, []);

  async function uploadAndPreview() {
    setUploadError(null);
    setPreview(null);
    setCommitResult(null);

    if (!file) {
      setUploadError("Please select a file first.");
      return;
    }

    const fd = new FormData();
    fd.append("file", file);
    fd.append("mode", mode);
    fd.append("batch_name", batchName || "BATCH1");

    setUploading(true);
    try {
      const res = await fetch("/api/upload", {
        method: "POST",
        body: fd,
      });
      const data = await res.json();
      if (!res.ok) {
        setUploadError(data.error || "Upload failed");
      } else {
        // Save preview UI
        setPreview(data);
      }
    } catch (err) {
      setUploadError(err.message || "Network error");
    } finally {
      setUploading(false);
    }
  }

  async function commitPreview() {
    if (!preview || !preview.batch_id) {
      setCommitResult({ error: "No preview available to commit." });
      return;
    }

    setCommitLoading(true);
    setCommitResult(null);
    try {
      const res = await fetch("/api/commit-upload", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ batch_id: preview.batch_id }),
      });
      const data = await res.json();
      if (!res.ok) {
        setCommitResult({ error: data.error || "Commit failed" });
      } else {
        setCommitResult({ success: true, ...data });
        // refresh students list and clear preview's commit button (one-time)
        await fetchStudents();
      }
    } catch (err) {
      setCommitResult({ error: err.message || "Network error" });
    } finally {
      setCommitLoading(false);
    }
  }

  async function fetchStudents(batch_id = "") {
    setStudentsError(null);
    setStudentsLoading(true);
    try {
      const url = batch_id ? `/api/students?batch_id=${encodeURIComponent(batch_id)}` : "/api/students";
      const res = await fetch(url);
      const data = await res.json();
      if (!res.ok) {
        setStudentsError(data.error || "Failed to fetch students");
        setStudents([]);
      } else {
        setStudents(Array.isArray(data) ? data : []);
      }
    } catch (err) {
      setStudentsError(err.message || "Network error");
    } finally {
      setStudentsLoading(false);
    }
  }

  function clearPreview() {
    setPreview(null);
    setUploadError(null);
    setCommitResult(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
    setFile(null);
  }

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      <div className="max-w-6xl mx-auto">
        <h1 className="text-2xl font-bold mb-4">Student Parser — Upload & Demo DB</h1>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Upload Card */}
          <div className="bg-white rounded-xl shadow p-6">
            <h2 className="text-lg font-semibold mb-3">Upload File</h2>

            <div className="space-y-3">
              <div>
                <label className="block text-sm font-medium text-gray-700">Choose CSV / XLSX</label>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".csv,.xls,.xlsx"
                  onChange={(e) => setFile(e.target.files && e.target.files[0])}
                  className="mt-1 block w-full text-sm text-gray-700"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700">Mode</label>
                <select value={mode} onChange={(e) => setMode(e.target.value)} className="mt-1 block w-full p-2 border rounded">
                  <option value="2">Name + Enrollment (Mode 2)</option>
                  <option value="1">Enrollment only (Mode 1)</option>
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700">Batch name</label>
                <input type="text" value={batchName} onChange={(e) => setBatchName(e.target.value)} className="mt-1 block w-full p-2 border rounded" />
              </div>

              <div className="flex gap-2 mt-2">
                <button onClick={uploadAndPreview} disabled={uploading} className="bg-blue-600 text-white px-4 py-2 rounded disabled:opacity-60">
                  {uploading ? "Uploading..." : "Upload & Preview"}
                </button>
                <button onClick={clearPreview} className="bg-gray-200 px-4 py-2 rounded">Clear</button>
              </div>

              {uploadError && <div className="text-red-600 mt-2">{uploadError}</div>}
            </div>

            {/* Preview area */}
            <div className="mt-6 border-t pt-4">
              <h3 className="font-medium mb-2">Preview & Commit</h3>

              {!preview && <div className="text-sm text-gray-500">Upload a file to get a preview (no DB write).</div>}

              {preview && (
                <div>
                  <div className="text-sm text-green-700 mb-2">
                    Preview ready — batch_id: <code className="bg-gray-100 p-1 rounded">{preview.batch_id}</code>
                  </div>

                  <div className="text-sm text-gray-600 mb-2">
                    <strong>Batch:</strong> {preview.batch_name} &nbsp; <strong>Rows:</strong> {preview.rows_total} &nbsp; <strong>Extracted:</strong> {preview.rows_extracted}
                  </div>

                  <div className="mb-2">
                    <strong>Warnings:</strong> {preview.warnings && preview.warnings.length ? <pre className="text-xs bg-yellow-50 p-2 rounded">{JSON.stringify(preview.warnings, null, 2)}</pre> : <span className="text-gray-500">None</span>}
                  </div>

                  {/* sample table */}
                  {preview.sample && preview.sample.length > 0 && (
                    <div className="overflow-auto max-h-56 border rounded">
                      <table className="min-w-full text-sm">
                        <thead className="bg-gray-50 sticky top-0">
                          <tr>
                            {Object.keys(preview.sample[0]).map((k) => (
                              <th key={k} className="px-2 py-2 text-left">{k}</th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          {preview.sample.map((row, idx) => (
                            <tr key={idx} className={idx % 2 === 0 ? "bg-white" : "bg-gray-50"}>
                              {Object.keys(preview.sample[0]).map((k) => (
                                <td key={k} className="px-2 py-1 align-top">{String(row[k] ?? "")}</td>
                              ))}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}

                  <div className="mt-3 flex gap-2 items-center">
                    <button onClick={commitPreview} disabled={commitLoading} className="bg-green-600 text-white px-4 py-2 rounded disabled:opacity-60">
                      {commitLoading ? "Committing..." : "Commit to demo DB"}
                    </button>
                    {commitResult && commitResult.success && (
                      <div className="text-green-700">Inserted: {commitResult.inserted} &nbsp; Skipped: {commitResult.skipped}</div>
                    )}
                    {commitResult && commitResult.error && <div className="text-red-600">{commitResult.error}</div>}
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Students list */}
          <div className="bg-white rounded-xl shadow p-6">
            <h2 className="text-lg font-semibold mb-3">Stored Students (demo)</h2>

            <div className="flex gap-2 mb-3">
              <input type="text" placeholder="Filter by batch_id (optional)" value={filterBatchId} onChange={(e) => setFilterBatchId(e.target.value)} className="flex-1 p-2 border rounded" />
              <button onClick={() => fetchStudents(filterBatchId)} className="px-3 py-2 bg-indigo-600 text-white rounded">Refresh</button>
            </div>

            {studentsLoading && <div className="text-sm text-gray-500">Loading...</div>}
            {studentsError && <div className="text-red-600">{studentsError}</div>}

            {!studentsLoading && students.length === 0 && <div className="text-sm text-gray-500">No students stored yet.</div>}

            {students.length > 0 && (
              <div className="overflow-auto max-h-80 border rounded">
                <table className="min-w-full text-sm">
                  <thead className="bg-gray-50 sticky top-0">
                    <tr>
                      <th className="px-2 py-2 text-left">ID</th>
                      <th className="px-2 py-2 text-left">Upload ID</th>
                      <th className="px-2 py-2 text-left">Batch</th>
                      <th className="px-2 py-2 text-left">Enrollment</th>
                      <th className="px-2 py-2 text-left">Name</th>
                      <th className="px-2 py-2 text-left">Inserted</th>
                    </tr>
                  </thead>
                  <tbody>
                    {students.map((s) => (
                      <tr key={s.id} className="odd:bg-white even:bg-gray-50">
                        <td className="px-2 py-1 align-top">{s.id}</td>
                        <td className="px-2 py-1 align-top">{s.upload_id ?? "-"}</td>
                        <td className="px-2 py-1 align-top">{s.batch_name}</td>
                        <td className="px-2 py-1 align-top">{s.enrollment}</td>
                        <td className="px-2 py-1 align-top">{s.name ?? "-"}</td>
                        <td className="px-2 py-1 align-top">{s.inserted_at}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            <div className="mt-3 text-xs text-gray-500">
              Tip: Each committed file creates a distinct upload (upload_id) — students from different files won't continue numbering.
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default UploadPage;
