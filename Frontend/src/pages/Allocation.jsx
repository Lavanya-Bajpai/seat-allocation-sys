// AllocationPage.jsx - WITH HYBRID PDF SUPPORT
import React, { useEffect, useState, useRef } from "react";

/**
 * AllocationPage - Enhanced with Hybrid PDF Generation
 *
 * Features:
 * - All original functionality preserved
 * - Client-side PDF (html2pdf) - Fast, browser-based
 * - Server-side PDF (ReportLab) - Professional quality
 * - Auto-fallback between methods
 * - User can choose PDF method via dropdown
 */

const AllocationPage = ({ showToast }) => {
  const [rows, setRows] = useState(8);
  const [cols, setCols] = useState(10);
  const [numBatches, setNumBatches] = useState(3);
  const [blockWidth, setBlockWidth] = useState(3);
  const [brokenSeats, setBrokenSeats] = useState("");
  const [batchStudentCounts, setBatchStudentCounts] = useState("");
  const [batchLabelsInput, setBatchLabelsInput] = useState("");
  const [useDemoDb, setUseDemoDb] = useState(true);
  const [batchStartRolls, setBatchStartRolls] = useState({});
  const [batchRollNumbers, setBatchRollNumbers] = useState({});
  const [batchColorsInput, setBatchColorsInput] = useState("");
  const [serialMode, setSerialMode] = useState("per_batch");
  const [serialWidth, setSerialWidth] = useState(0);
  const [batchByColumn, setBatchByColumn] = useState(true);
  const [enforceNoAdjacentBatches, setEnforceNoAdjacentBatches] = useState(false);

  const [loading, setLoading] = useState(false);
  const [webData, setWebData] = useState(null);
  const [error, setError] = useState(null);
  const [pdfLoading, setPdfLoading] = useState(false);
  const [resetting, setResetting] = useState(false);

  const chartRef = useRef();

  // Keep a derived list of dynamic start-roll inputs synced to numBatches
  useEffect(() => {
    const next = { ...batchStartRolls };
    for (let i = 1; i <= numBatches; i++) {
      if (!(i in next)) next[i] = "";
    }
    Object.keys(next)
      .map(Number)
      .forEach((k) => {
        if (k > numBatches) delete next[k];
      });
    setBatchStartRolls(next);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [numBatches]);

  function parseKVList(str) {
    const out = {};
    if (!str) return out;
    str
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean)
      .forEach((part) => {
        const sep = part.includes(":") ? ":" : part.includes("=") ? "=" : null;
        if (!sep) return;
        const [k, v] = part.split(sep, 2).map((x) => x.trim());
        if (!k) return;
        const ik = parseInt(k, 10);
        out[isNaN(ik) ? k : ik] = v;
      });
    return out;
  }

  function buildPayload() {
    return {
      rows,
      cols,
      num_batches: numBatches,
      block_width: blockWidth,
      batch_by_column: batchByColumn,
      enforce_no_adjacent_batches: enforceNoAdjacentBatches,
      broken_seats: brokenSeats,
      batch_student_counts: batchStudentCounts,
      batch_colors: batchColorsInput,
      start_rolls: Object.keys(batchStartRolls).length
        ? Object.fromEntries(
            Object.entries(batchStartRolls)
              .filter(([, v]) => v && String(v).trim() !== "")
              .map(([k, v]) => [parseInt(k, 10), String(v).trim()])
            )
        : undefined,
      serial_mode: serialMode,
      serial_width: serialWidth || 0,
      use_demo_db: useDemoDb,
      batch_roll_numbers: Object.keys(batchRollNumbers).length ? batchRollNumbers : undefined,
      batch_labels: Object.keys(parseKVList(batchLabelsInput)).length ? parseKVList(batchLabelsInput) : undefined,
    };
  }

  async function generate() {
    setLoading(true);
    setError(null);
    setWebData(null);
    try {
      const payload = buildPayload();
      const res = await fetch("/api/generate-seating", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data.error || "Server error");
      } else {
        setWebData(data);
        setTimeout(() => {
          chartRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
        }, 80);
      }
    } catch (err) {
      setError(err.message || "Network error");
    } finally {
      setLoading(false);
    }
  }

  async function showConstraints() {
    try {
      const payload = buildPayload();
      const res = await fetch("/api/constraints-status", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data.error || "Failed to fetch constraints");
        return;
      }
      const body = data.constraints
        .map(
          (c) =>
            `${c.applied ? "Applied" : "Not applied"} — ${c.name}\n  ${c.description}\n  Status: ${
              c.satisfied ? "SATISFIED" : "NOT SATISFIED"
            }\n`
        )
        .join("\n\n");
      alert(`Constraints status:\n\n${body}`);
    } catch (err) {
      alert("Error fetching constraints: " + (err.message || err));
    }
  }
  async function handleResetDatabase() {
    if (!window.confirm("⚠️ ARE YOU SURE?\n\nThis will delete ALL student data, uploads, and previous allocations from the database.\n\nThis action cannot be undone.")) {
      return;
    }

    setResetting(true);
    try {
      const token = localStorage.getItem('token'); 
      const headers = { "Content-Type": "application/json" };
      if (token) headers["Authorization"] = `Bearer ${token}`;

      const res = await fetch("/api/reset-data", {
        method: "POST",
        headers: headers
      });

      const data = await res.json();

      if (!res.ok) {
        throw new Error(data.error || "Reset failed");
      }

      alert("✅ Database reset successful. All student data cleared.");
      setWebData(null); 
      if (showToast) showToast("Database cleared successfully", "success");

    } catch (err) {
      console.error("Reset error:", err);
      alert("Failed to reset database: " + err.message);
    } finally {
      setResetting(false);
    }
}

  // CLIENT-SIDE PDF - With forced render and longer delay
function downloadPdfClientSide() {
  if (!webData) {
    alert('No seating data available. Generate chart first.');
    return;
  }

  if (!window.html2pdf) {
    alert('html2pdf library not loaded.');
    return;
  }

  console.log('📄 Generating PDF...');
  setPdfLoading(true);

  // Create container VISIBLE on screen
  const container = document.createElement("div");
  container.id = "pdf-capture-container";
  container.style.cssText = `
    padding: 30px;
    font-family: Arial, sans-serif;
    background: #ffffff;
    width: 900px;
    position: fixed;
    left: 50%;
    top: 50%;
    transform: translate(-50%, -50%);
    z-index: 999999;
    box-shadow: 0 0 50px rgba(0,0,0,0.5);
    max-height: 90vh;
    overflow: auto;
  `;

  // Overlay
  const overlay = document.createElement("div");
  overlay.style.cssText = `
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0,0,0,0.8);
    z-index: 999998;
  `;

  const loadingText = document.createElement("div");
  loadingText.style.cssText = `
    position: fixed;
    top: 20px;
    left: 50%;
    transform: translateX(-50%);
    color: white;
    font-size: 20px;
    font-weight: bold;
    text-align: center;
    z-index: 9999999;
    background: rgba(0,0,0,0.9);
    padding: 20px 40px;
    border-radius: 10px;
  `;
  loadingText.innerHTML = `
    <div>🔄 Generating PDF...</div>
    <div style="font-size: 14px; margin-top: 10px;">Please wait 3-4 seconds</div>
  `;

  // Header
  const h = document.createElement("h2");
  h.style.cssText = `
    text-align: center;
    margin: 0 0 20px 0;
    color: #000000;
    font-size: 28px;
    font-weight: bold;
    font-family: Arial, sans-serif;
  `;
  h.textContent = "Seating Arrangement";
  container.appendChild(h);

  // Info
  const info = document.createElement("div");
  info.style.cssText = `
    text-align: center;
    font-size: 14px;
    margin-bottom: 20px;
    color: #000000;
    font-weight: normal;
    font-family: Arial, sans-serif;
  `;
  info.textContent = `Rows: ${rows} | Cols: ${cols} | Batches: ${numBatches} | Generated: ${new Date().toLocaleString()}`;
  container.appendChild(info);

  // Grid wrapper
  const gridWrapper = document.createElement("div");
  gridWrapper.style.cssText = `
    background: #ffffff;
    padding: 15px;
    border: 3px solid #000000;
  `;

  // Grid
  const grid = document.createElement("div");
  grid.style.cssText = `
    display: grid;
    grid-template-columns: repeat(${cols}, 1fr);
    gap: 6px;
    background-color: #ffffff;
  `;

  webData.seating.flat().forEach((s, idx) => {
    const seatEl = document.createElement("div");
    seatEl.style.cssText = `
      border: 2px solid #000000;
      box-sizing: border-box;
      display: flex;
      flex-direction: column;
      justify-content: center;
      align-items: center;
      padding: 8px 4px;
      text-align: center;
      min-height: 70px;
      background-color: ${s.color || "#ffffff"};
      font-family: Arial, sans-serif;
    `;
    
    if (s.is_broken) {
      const brokenLabel = document.createElement("div");
      brokenLabel.style.cssText = "font-weight: bold; color: #8B0000; font-size: 13px; font-family: Arial, sans-serif;";
      brokenLabel.textContent = "BROKEN";
      
      const posLabel = document.createElement("div");
      posLabel.style.cssText = "font-size: 10px; color: #800000; margin-top: 4px; font-family: Arial, sans-serif;";
      posLabel.textContent = s.position;
      
      seatEl.appendChild(brokenLabel);
      seatEl.appendChild(posLabel);
    } else if (s.is_unallocated) {
      const unallocLabel = document.createElement("div");
      unallocLabel.style.cssText = "font-weight: bold; color: #444444; font-size: 12px; font-family: Arial, sans-serif;";
      unallocLabel.textContent = "UNALLOC";
      seatEl.appendChild(unallocLabel);
    } else {
      const bLabel = s.batch_label || `B${s.batch || ""}`;
      const roll = s.roll_number || "";
      const pSet = s.paper_set || "";
      
      const batchDiv = document.createElement("div");
      batchDiv.style.cssText = "font-weight: 600; margin-bottom: 4px; font-size: 11px; color: #000000; font-family: Arial, sans-serif;";
      batchDiv.textContent = bLabel;
      
      const rollDiv = document.createElement("div");
      rollDiv.style.cssText = "font-weight: bold; font-size: 14px; color: #000000; font-family: Arial, sans-serif;";
      rollDiv.textContent = roll;
      
      seatEl.appendChild(batchDiv);
      seatEl.appendChild(rollDiv);
      
      if (pSet) {
        const setDiv = document.createElement("div");
        setDiv.style.cssText = "font-size: 9px; margin-top: 3px; color: #000000; font-family: Arial, sans-serif;";
        setDiv.textContent = `Set: ${pSet}`;
        seatEl.appendChild(setDiv);
      }
    }
    
    grid.appendChild(seatEl);
  });

  gridWrapper.appendChild(grid);
  container.appendChild(gridWrapper);
  
  document.body.appendChild(overlay);
  document.body.appendChild(loadingText);
  document.body.appendChild(container);

  // Force reflow
  void container.offsetHeight;

  const opt = { 
    margin: 15,
    filename: "seating_arrangement.pdf", 
    image: { 
      type: "jpeg", 
      quality: 1.0
    }, 
    html2canvas: { 
      scale: 3,
      useCORS: true,
      allowTaint: true,
      logging: true,
      backgroundColor: '#ffffff',
      width: 900,
      height: container.scrollHeight,
      scrollY: 0,
      scrollX: 0,
      windowWidth: 900,
      windowHeight: container.scrollHeight
    }, 
    jsPDF: { 
      unit: "mm", 
      format: "a4", 
      orientation: "landscape"
    }
  };

  // CRITICAL: Wait longer for fonts and render
  setTimeout(() => {
    console.log('🔄 Starting capture in 2 seconds...');
    loadingText.innerHTML = `
      <div>📸 Capturing content...</div>
      <div style="font-size: 14px; margin-top: 10px;">Almost done!</div>
    `;
    
    setTimeout(() => {
      console.log('📸 Capturing now...');
      
      window.html2pdf()
        .set(opt)
        .from(container)
        .toPdf()
        .get('pdf')
        .then((pdf) => {
          console.log('✅ PDF object created');
          console.log('Pages:', pdf.internal.getNumberOfPages());
          console.log('Page size:', pdf.internal.pageSize);
          return pdf;
        })
        .outputPdf('blob')
        .then((pdfBlob) => {
          console.log('📦 PDF Blob size:', pdfBlob.size, 'bytes');
          
          if (pdfBlob.size < 1000) {
            throw new Error('PDF is too small - likely empty!');
          }
          
          // Download
          const url = URL.createObjectURL(pdfBlob);
          const a = document.createElement('a');
          a.href = url;
          a.download = 'seating_arrangement.pdf';
          document.body.appendChild(a);
          a.click();
          
          setTimeout(() => {
            URL.revokeObjectURL(url);
            document.body.removeChild(a);
          }, 100);
          
          console.log('✅✅✅ PDF downloaded!');
          return pdfBlob;
        })
        .then(() => {
          // Cleanup
          if (document.body.contains(container)) {
            document.body.removeChild(container);
          }
          if (document.body.contains(overlay)) {
            document.body.removeChild(overlay);
          }
          if (document.body.contains(loadingText)) {
            document.body.removeChild(loadingText);
          }
          
          setPdfLoading(false);
          alert('✅ PDF downloaded successfully!\n\nCheck your Downloads folder for "seating_arrangement.pdf"');
        })
        .catch((err) => {
          console.error('❌ PDF Error:', err);
          console.error('Error details:', {
            message: err.message,
            stack: err.stack
          });
          
          // Cleanup
          if (document.body.contains(container)) {
            document.body.removeChild(container);
          }
          if (document.body.contains(overlay)) {
            document.body.removeChild(overlay);
          }
          if (document.body.contains(loadingText)) {
            document.body.removeChild(loadingText);
          }
          
          setPdfLoading(false);
          alert('❌ PDF generation failed!\n\nError: ' + err.message + '\n\nTry the Server-Side option instead.');
        });
    }, 2000); // Wait 2 more seconds after initial render
  }, 1000); // Wait 1 second for initial render
}

  // SERVER-SIDE PDF (Using your pdf_gen.py)
  async function downloadPdfServerSide() {
    if (!webData) {
      alert('No seating data available. Generate chart first.');
      return;
    }

    setPdfLoading(true);

    try {
      console.log('📄 Requesting server-side PDF...');
      const pdfPayload = {
        ...buildPayload(),
        seating: webData.seating,
        metadata: webData.metadata
      };
      console.log('Sending PDF payload:', pdfPayload);
      
      const response = await fetch('/api/generate-pdf', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(webData),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || 'PDF generation failed');
      }

      const blob = await response.blob();
      
      if (blob.size === 0) {
        throw new Error('PDF file is empty');
      }

      console.log(`✅ PDF received: ${blob.size} bytes`);

      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `seating_arrangement_server_${new Date().getTime()}.pdf`;
      document.body.appendChild(a);
      a.click();
      
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
      
      console.log('✅ PDF downloaded successfully (server-side)');
      
    } catch (error) {
      console.error('❌ Server PDF Error:', error);
      alert(`Server-side PDF generation failed: ${error.message}`);
    } finally {
      setPdfLoading(false);
    }
  }

  // MAIN DOWNLOAD - Auto-detects best method
  function downloadPdf() {
    if (!webData) {
      alert('No seating data available. Generate chart first.');
      return;
    }

    if (window.html2pdf) {
      downloadPdfClientSide();
    } else {
      console.log('⚠️ html2pdf not available, using server-side generation');
      downloadPdfServerSide();
    }
  }

  function renderSeat(seat, rIdx, cIdx) {
    if (!seat) {
      return (
        <div
          key={`${rIdx}-${cIdx}`}
          className="p-2 border rounded bg-gray-50 flex flex-col items-center justify-center text-xs min-h-[84px] min-w-[84px]"
        >
          &nbsp;
        </div>
      );
    }
    if (seat.is_broken) {
      return (
        <div
          key={`${rIdx}-${cIdx}`}
          className="p-3 min-w-[84px] min-h-[84px] rounded-lg flex flex-col items-center justify-center text-xs border-2 border-red-400 bg-red-100 shadow-md transition-all duration-200 overflow-hidden"
        >
          <div className="font-bold text-red-800 text-sm">BROKEN</div>
          <div className="text-[10px] text-red-700 mt-1">{seat.position}</div>
        </div>
      );
    }
    if (seat.is_unallocated) {
      return (
        <div
          key={`${rIdx}-${cIdx}`}
          className="p-3 min-w-[84px] min-h-[84px] rounded-lg flex flex-col items-center justify-center text-xs border border-gray-300 bg-gray-100 shadow-md transition-all duration-200 overflow-hidden"
        >
          <div className="font-semibold text-gray-600 text-sm">Batch {seat.batch}</div>
          <div className="font-bold text-gray-500 text-sm">UNALLOCATED</div>
          <div className="text-[10px] text-gray-500">{seat.position}</div>
        </div>
      );
    }
    const color = seat.color || "#ffffff";
    const label = seat.batch_label || (seat.batch ? `Batch ${seat.batch}` : "");
    const rn = seat.roll_number || "";
    const set = seat.paper_set || "";
    const display = seat.display || (rn ? `${rn}${set}` : "UNALLOCATED");
    return (
      <div
        key={`${rIdx}-${cIdx}`}
        className="p-3 min-w-[84px] min-h-[84px] rounded-lg flex flex-col items-center justify-center text-xs border border-gray-300 shadow-md transition-all duration-200 overflow-hidden"
        style={{ background: color }}
      >
        <div className="text-[11px] font-semibold text-center">{label}</div>
        <div className="text-sm font-bold break-words text-center mt-1">{rn}</div>
        {set && <div className="text-[10px] opacity-80 mt-1">Set: {set}</div>}
        <div className="text-[10px] opacity-70 mt-1">{seat.position}</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-white p-6">
      <div className="max-w-6xl mx-auto">
        <h1 className="text-3xl font-bold text-center mb-6">Seating Arrangement — Allocation</h1>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">
          <div className="lg:col-span-2 bg-white rounded-xl shadow p-6">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700">Rows</label>
                <input type="number" className="mt-1 w-full p-2 border rounded" value={rows} onChange={(e)=>setRows(Math.max(1, parseInt(e.target.value||1)))} />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700">Columns</label>
                <input type="number" className="mt-1 w-full p-2 border rounded" value={cols} onChange={(e)=>setCols(Math.max(1, parseInt(e.target.value||1)))} />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700">Number of Batches</label>
                <input type="number" className="mt-1 w-full p-2 border rounded" value={numBatches} onChange={(e)=>setNumBatches(Math.max(1, Math.min(50, parseInt(e.target.value||1))))} />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700">Block Width (cols)</label>
                <input type="number" className="mt-1 w-full p-2 border rounded" value={blockWidth} onChange={(e)=>setBlockWidth(Math.max(1, parseInt(e.target.value||1)))} />
              </div>

              <div className="col-span-1 md:col-span-2">
                <label className="block text-sm font-medium text-gray-700 mb-2">Broken Seats (row-col)</label>
                <input type="text" className="mt-1 w-full p-2 border rounded" placeholder="e.g., 1-3,2-1" value={brokenSeats} onChange={(e)=>setBrokenSeats(e.target.value)} />
                <p className="text-xs text-gray-500 mt-1">Separate entries with commas; rows/cols are 1-based.</p>
              </div>

              <div className="col-span-1 md:col-span-2">
                <label className="block text-sm font-medium text-gray-700 mb-2">Batch Student Counts (optional)</label>
                <input type="text" className="mt-1 w-full p-2 border rounded" placeholder="1:35,2:30,3:25" value={batchStudentCounts} onChange={(e)=>setBatchStudentCounts(e.target.value)} />
                <p className="text-xs text-gray-500 mt-1">Format: batchIndex:count, separated by commas. Shows unallocated if total &lt; available seats</p>
              </div>

              <div className="col-span-1 md:col-span-2">
                <label className="block text-sm font-medium text-gray-700 mb-2">Per-batch Start Roll Strings (optional)</label>
                <div className="space-y-2">
                  {Array.from({ length: numBatches }).map((_, i) => {
                    const idx = i + 1;
                    return (
                      <div key={idx}>
                        <label className="text-xs text-gray-600">Batch {idx}</label>
                        <input
                          type="text"
                          className="w-full p-2 border rounded"
                          placeholder={`e.g., BTCS24O${1000 + (idx - 1) * 100}`}
                          value={batchStartRolls[idx] || ""}
                          onChange={(e) => setBatchStartRolls((prev) => ({ ...prev, [idx]: e.target.value }))}
                        />
                      </div>
                    );
                  })}
                </div>
                <p className="text-xs text-gray-500 mt-2">Format: batchIndex:ROLLSTRING, separated by commas. Example: 1:BTCS24O1135,2:BTCD24O2001</p>
              </div>

              <div className="col-span-1 md:col-span-2">
                <label className="block text-sm font-medium text-gray-700 mb-2">Batch Colors (optional)</label>
                <input type="text" className="mt-1 w-full p-2 border rounded" placeholder="1:#DBEAFE,2:#DCFCE7" value={batchColorsInput} onChange={(e)=>setBatchColorsInput(e.target.value)} />
                <p className="text-xs text-gray-500 mt-1">Format: batchIndex:#HEXCOLOR, separated by commas</p>
              </div>

              <div className="col-span-1 md:col-span-2">
                <label className="block text-sm font-medium text-gray-700 mb-2">Batch Labels (optional)</label>
                <input type="text" className="mt-1 w-full p-2 border rounded" placeholder="1:CSE,2:ECE,3:IT" value={batchLabelsInput} onChange={(e)=>setBatchLabelsInput(e.target.value)} />
                <p className="text-xs text-gray-500 mt-1">Human readable branch names. Format: batchIndex:LABEL</p>
              </div>

              <div className="col-span-1">
                <label className="block text-sm font-medium text-gray-700 mb-2">Fill Batches By Column</label>
                <div className="flex items-center gap-3">
                  <input type="checkbox" checked={batchByColumn} onChange={(e)=>setBatchByColumn(e.target.checked)} className="h-5 w-5" />
                  <span className="text-sm text-gray-600">Column-major assignment</span>
                </div>
              </div>

              <div className="col-span-1">
                <label className="block text-sm font-medium text-gray-700 mb-2">Enforce No Adjacent Same Batch</label>
                <div className="flex items-center gap-3">
                  <input type="checkbox" checked={enforceNoAdjacentBatches} onChange={(e)=>setEnforceNoAdjacentBatches(e.target.checked)} className="h-5 w-5" />
                  <span className="text-sm text-gray-600">Optional constraint</span>
                </div>
              </div>

              <div className="col-span-1 md:col-span-2 mt-4">
                <div className="flex gap-3 flex-wrap items-center">
                  <button onClick={generate} disabled={loading} className="bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400 text-white px-6 py-2 rounded font-medium transition"> 
                    {loading ? "Generating..." : "Generate Chart"}
                  </button>
                  
                  {/* Main PDF Button */}
                  <button 
                    onClick={downloadPdf}
                    disabled={!webData || pdfLoading}
                    className="bg-green-600 hover:bg-green-700 disabled:bg-gray-400 text-white px-6 py-2 rounded font-medium transition inline-flex items-center gap-2"
                  >
                    {pdfLoading ? (
                      <>
                        <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none"></circle>
                          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                        </svg>
                        <span>Generating...</span>
                      </>
                    ) : (
                      <>
                        <span>📥</span>
                        <span>Download PDF</span>
                      </>
                    )}
                  </button>

                  {/* PDF Options Dropdown */}
                  <div className="relative group">
                    <button 
                      disabled={!webData || pdfLoading}
                      className="bg-gray-600 hover:bg-gray-700 disabled:bg-gray-400 text-white px-4 py-2 rounded font-medium transition"
                      title="PDF Options"
                    >
                      ⚙️
                    </button>
                    
                    <div className="absolute left-0 mt-2 w-56 bg-white rounded-lg shadow-xl border border-gray-200 invisible group-hover:visible opacity-0 group-hover:opacity-100 transition-all duration-200 z-20">
                      <button
                        onClick={downloadPdfClientSide}
                        disabled={!webData || pdfLoading}
                        className="w-full text-left px-4 py-3 hover:bg-gray-50 rounded-t-lg transition disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                        <div className="font-semibold text-sm text-gray-800">🌐 Client-Side PDF</div>
                        <div className="text-xs text-gray-500">Fast, browser-based (html2pdf)</div>
                      </button>
                      <div className="border-t border-gray-100"></div>
                      <button
                        onClick={downloadPdfServerSide}
                        disabled={!webData || pdfLoading}
                        className="w-full text-left px-4 py-3 hover:bg-gray-50 rounded-b-lg transition disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                        <div className="font-semibold text-sm text-gray-800">🖥️ Server-Side PDF</div>
                        <div className="text-xs text-gray-500">Professional (ReportLab)</div>
                      </button>
                    </div>
                  </div>
                  
                  <button onClick={showConstraints} className="bg-purple-600 hover:bg-purple-700 text-white px-6 py-2 rounded font-medium transition">
                    View Constraints
                  </button>
                </div>
              </div>

              <div className="col-span-1 md:col-span-2">
                <label className="inline-flex items-center gap-2 cursor-pointer">
                  <input type="checkbox" checked={useDemoDb} onChange={(e)=>setUseDemoDb(e.target.checked)} className="h-5 w-5" />
                  <span className="text-sm text-gray-700">Use demo DB for enrollments/labels</span>
                </label>
              </div>
            

              {error && <div className="col-span-1 md:col-span-2 mt-2 text-red-600 font-medium text-sm">{error}</div>}

              {/* DANGER ZONE - DB RESET */}
                <div className="mt-8 pt-6 border-t border-gray-200">
                    <div className="flex items-center justify-between">
                    <div>
                        <h3 className="text-sm font-bold text-red-600">Danger Zone</h3>
                        <p className="text-xs text-gray-500">Resetting will clear all student data and uploads.</p>
                    </div>
                    <button 
                        onClick={handleResetDatabase} 
                        disabled={resetting}
                        className="bg-red-50 text-red-600 border border-red-200 hover:bg-red-100 px-4 py-2 rounded text-sm font-semibold transition disabled:opacity-50"
                    >
                        {resetting ? "Resetting..." : "Reset Database"}
                    </button>
                    </div>
                </div>
            </div>
            </div>

          <div className="bg-white rounded-xl shadow p-6 h-fit">
            <h3 className="font-semibold mb-3">Quick Summary</h3>
            <div className="space-y-2 text-sm">
              <div>Total rows: <strong>{rows}</strong></div>
              <div>Total cols: <strong>{cols}</strong></div>
              <div>Batch count: <strong>{numBatches}</strong></div>
              <div>Block width: <strong>{blockWidth}</strong></div>
              <div>Using demo DB: <strong>{useDemoDb ? "Yes" : "No"}</strong></div>
            </div>
            <div className="mt-4">
              <button onClick={()=>{ setRows(8); setCols(10); setNumBatches(3); setBlockWidth(3); }} className="text-xs text-gray-600 hover:underline">Reset to defaults</button>
            </div>
          </div>
        </div>

        {/* Seating Chart */}
        <div ref={chartRef} className="bg-white rounded-xl shadow p-6">
          <h2 className="text-xl font-semibold mb-4">Seating Chart</h2>

          {!webData && <div className="text-gray-500">No seating generated yet. Click "Generate Chart".</div>}

          {webData && (
            <>
              <div className="mb-3">
                {webData.validation && webData.validation.is_valid ? (
                  <div className="text-green-700 font-medium">All constraints satisfied</div>
                ) : (
                  <div className="text-red-600 font-medium">Violations detected — open constraints to inspect</div>
                )}
              </div>

              <div className="overflow-auto">
                <div style={{ display: "grid", gridTemplateColumns: `repeat(${webData.metadata?.cols || cols}, minmax(88px, 1fr))`, gap: 12 }}>
                  {webData.seating.map((row, rIdx)=> row.map((seat, cIdx) => renderSeat(seat, rIdx, cIdx)))}
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
};
export default AllocationPage;