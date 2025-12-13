import React, { useState, useEffect, useRef } from "react";
import { Upload, Loader2 } from "lucide-react";

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

const UploadPage = ({ showToast }) => {
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

  function handleFileChange(e) {
    const selectedFile = e.target.files?.[0];
    if (selectedFile) {
      setFile(selectedFile);
      setUploadError(null);
    }
  }

  function handleUpload() {
    uploadAndPreview();
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
            <h1 className="text-3xl font-bold text-gray-900 dark:text-white">Upload Student Data</h1>
            <p className="text-gray-600 dark:text-gray-400 mt-2">Upload a CSV file with student information</p>
          </div>

          <div className="border-2 border-dashed border-gray-300 dark:border-gray-600 rounded-xl p-12 text-center hover:border-blue-500 dark:hover:border-blue-400 transition bg-gray-50 dark:bg-gray-700/50">
            <input
              type="file"
              accept=".csv"
              onChange={handleFileChange}
              className="hidden"
              id="file-upload"
            />
            <label htmlFor="file-upload" className="cursor-pointer">
              <Upload className="text-gray-400 dark:text-gray-500 mx-auto mb-4" size={48} />
              <p className="text-lg font-medium text-gray-700 dark:text-gray-300 mb-2">
                {file ? file.name : 'Click to upload or drag and drop'}
              </p>
              <p className="text-sm text-gray-500 dark:text-gray-400">CSV files only (max 10MB)</p>
            </label>
          </div>

          {file && (
            <div className="mt-6 p-4 bg-blue-50 dark:bg-blue-900/30 rounded-lg">
              <p className="text-sm text-gray-700 dark:text-gray-300">
                <strong>Selected file:</strong> {file.name} ({(file.size / 1024).toFixed(2)} KB)
              </p>
            </div>
          )}

          <button
            onClick={handleUpload}
            disabled={!file || uploading}
            className="w-full mt-6 bg-blue-600 dark:bg-blue-500 text-white py-3 rounded-lg font-semibold hover:bg-blue-700 dark:hover:bg-blue-600 transition disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
          >
            {uploading ? (
              <>
                <Loader2 className="animate-spin" size={20} />
                Uploading...
              </>
            ) : (
              'Upload File'
            )}
          </button>

          <div className="mt-8 p-6 bg-gray-50 dark:bg-gray-700 rounded-lg transition-colors duration-300">
            <h3 className="font-semibold text-gray-900 dark:text-white mb-3">CSV Format Requirements:</h3>
            <ul className="text-sm text-gray-600 dark:text-gray-400 space-y-2">
              <li>• Include headers: Student ID and Name</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
};

export default UploadPage;