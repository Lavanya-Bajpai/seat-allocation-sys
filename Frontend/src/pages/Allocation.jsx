// AllocationPage.jsx
import React, { useEffect, useState, useRef } from "react";

/**
 * AllocationPage
 *
 * Features:
 * - Full controls for rows/cols/numBatches/blockWidth/broken seats/etc.
 * - "Use Demo DB" toggle: when enabled, server will pull batch_roll_numbers & batch_labels
 * - Dynamic per-batch start-roll inputs
 * - Generates seating via POST /api/generate-seating
 * - Renders neat grid UI with colors, displays enrollment+set, branch label (batch_label)
 * - Download PDF using html2pdf (script must be included globally)
 * - Constraints modal via /api/constraints-status (server-side)
 *
 * Usage:
 * - Place in frontend React app and route to it.
 * - Requires Tailwind in your project (component uses Tailwind classes).
 */

const defaultColors = [
  "bg-sky-100",
  "bg-emerald-100",
  "bg-rose-100",
  "bg-amber-100",
  "bg-violet-100",
  "bg-pink-100",
  "bg-cyan-100",
  "bg-lime-100",
  "bg-fuchsia-100",
  "bg-slate-100",
];

const AllocationPage = () => {
  const [rows, setRows] = useState(8);
  const [cols, setCols] = useState(10);
  const [numBatches, setNumBatches] = useState(3);
  const [blockWidth, setBlockWidth] = useState(3);
  const [brokenSeats, setBrokenSeats] = useState(""); // "1-3,2-1"
  const [batchStudentCounts, setBatchStudentCounts] = useState("");
  const [batchLabelsInput, setBatchLabelsInput] = useState(""); // optional manual labels
  const [useDemoDb, setUseDemoDb] = useState(true);
  const [batchStartRolls, setBatchStartRolls] = useState({}); // {1: '1001', 2: '2001'}
  const [batchRollNumbers, setBatchRollNumbers] = useState({}); // optional in-page override
  const [batchColorsInput, setBatchColorsInput] = useState(""); // "1:#DBEAFE,2:#DCFCE7"
  const [serialMode, setSerialMode] = useState("per_batch");
  const [serialWidth, setSerialWidth] = useState(0);
  const [batchByColumn, setBatchByColumn] = useState(true);
  const [enforceNoAdjacentBatches, setEnforceNoAdjacentBatches] = useState(false);

  const [loading, setLoading] = useState(false);
  const [webData, setWebData] = useState(null);
  const [error, setError] = useState(null);

  const chartRef = useRef();

  // Keep a derived list of dynamic start-roll inputs synced to numBatches
  useEffect(() => {
    const next = { ...batchStartRolls };
    for (let i = 1; i <= numBatches; i++) {
      if (!(i in next)) next[i] = "";
    }
    // remove extraneous
    Object.keys(next)
      .map(Number)
      .forEach((k) => {
        if (k > numBatches) delete next[k];
      });
    setBatchStartRolls(next);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [numBatches]);

  function parseKVList(str) {
    // "1:BTCS,2:BTCD" -> {1: "BTCS", 2: "BTCD"}
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
    // Compose batch_start_rolls like "1:123,2:201"
    const start_rolls_entries = Object.entries(batchStartRolls)
      .filter(([, v]) => v && String(v).trim() !== "")
      .map(([k, v]) => `${k}:${v}`)
      .join(",");
    // include any provided per-batch roll lists if present (should be an object)
    // but we don't include them here, server expects JSON object for batch_roll_numbers if used
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
      start_rolls: start_rolls_entries,
      serial_mode: serialMode,
      serial_width: serialWidth || 0,
      use_demo_db: useDemoDb,
      // optional: if user supplied batch_roll_numbers JSON via UI (rare), pass it
      batch_roll_numbers: Object.keys(batchRollNumbers).length ? batchRollNumbers : undefined,
      // optional: pass explicit batch_labels mapping if typed (e.g., "1:CSE,2:ECE")
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
        // smooth scroll to seating
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
    // call constraints-status endpoint and show modal
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
      // show a simple modal (we'll just inject into DOM via window.alert for simplicity)
      // build nicer modal
      const body = data.constraints
        .map(
          (c) =>
            `${c.applied ? "Applied" : "Not applied"} — ${c.name}\n  ${c.description}\n  Status: ${
              c.satisfied ? "SATISFIED" : "NOT SATISFIED"
            }\n`
        )
        .join("\n\n");
      // show in native modal for now
      alert(`Constraints status:\n\n${body}`);
    } catch (err) {
      alert("Error fetching constraints: " + (err.message || err));
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

  function downloadPdf() {
    // Uses global html2pdf (include script in public/index.html)
    if (!webData) return;
    const container = document.createElement("div");
    container.style.padding = "12px";
    container.style.fontFamily = "Inter, Arial, sans-serif";
    
    // title
    const h = document.createElement("h3");
    h.innerText = "Seating Arrangement";
    h.style.textAlign = "center";
    h.style.marginBottom = "8px";
    h.style.fontSize = "18px";
    h.style.fontWeight = "bold";
    container.appendChild(h);

    // info line
    const info = document.createElement("div");
    info.style.textAlign = "center";
    info.style.fontSize = "12px";
    info.style.marginBottom = "10px";
    info.innerText = `Rows: ${rows} | Cols: ${cols} | Batches: ${numBatches} | Generated: ${new Date().toLocaleString()}`;
    container.appendChild(info);

    // grid
    const grid = document.createElement("div");
    grid.style.display = "grid";
    grid.style.gridTemplateColumns = `repeat(${cols}, 68px)`;
    grid.style.gap = "6px";
    grid.style.justifyContent = "center";

    const seats = webData.seating.flat();
    seats.forEach((s) => {
      const seatEl = document.createElement("div");
      seatEl.style.width = "68px";
      seatEl.style.height = "68px";
      seatEl.style.border = "1px solid #333";
      seatEl.style.boxSizing = "border-box";
      seatEl.style.display = "flex";
      seatEl.style.flexDirection = "column";
      seatEl.style.justifyContent = "center";
      seatEl.style.alignItems = "center";
      seatEl.style.fontSize = "10px";
      seatEl.style.background = s.color || "#fff";
      seatEl.style.padding = "4px";
      seatEl.style.textAlign = "center";
      // content
      if (s.is_broken) {
        seatEl.innerHTML = `<div style="font-weight:bold;color:#8B0000">BROKEN</div><div style="font-size:9px;color:#800000">${s.position}</div>`;
      } else if (s.is_unallocated) {
        seatEl.innerHTML = `<div style="font-weight:600;color:#666">Batch ${s.batch || ""}</div><div style="font-weight:bold;color:#444">UNALLOC</div>`;
      } else {
        const setVal = s.paper_set ? s.paper_set : "";
        const roll = s.roll_number ? s.roll_number : "";
        const bLabel = s.batch_label ? s.batch_label : `B${s.batch || ""}`;
        seatEl.innerHTML = `<div style="font-size:10px;font-weight:600">${bLabel}</div><div style="font-weight:bold">${roll}${setVal}</div><div style="font-size:9px;color:#333">${s.position}</div>`;
      }
      grid.appendChild(seatEl);
    });

    container.appendChild(grid);

    const opt = {
      margin: 8,
      filename: "seating_arrangement.pdf",
      image: { type: "jpeg", quality: 0.98 },
      html2canvas: { scale: 2, useCORS: true },
      jsPDF: { unit: "mm", format: "a4", orientation: "landscape" },
    };

    if (window && window.html2pdf) {
      window.html2pdf().set(opt).from(container).save();
    } else {
      alert("html2pdf library not loaded. Add the script to public/index.html for PDF downloads.");
    }
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
                <div className="flex gap-3 flex-wrap">
                  <button onClick={generate} disabled={loading} className="bg-blue-600 hover:bg-blue-700 text-white px-6 py-2 rounded font-medium transition"> 
                    {loading ? "Generating..." : "Generate Chart"}
                  </button>
                  <button onClick={downloadPdf} className="bg-green-600 hover:bg-green-700 text-white px-6 py-2 rounded font-medium transition" disabled={!webData}>
                    Download PDF
                  </button>
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

              {/* Summary */}
              <div className="mt-6 grid grid-cols-1 md:grid-cols-4 gap-4">
                <div className="p-3 bg-gray-50 rounded border">
                  <strong className="text-gray-700">Total Available Seats:</strong>
                  <div className="text-lg font-bold text-gray-900">{webData.summary.total_available_seats ?? "-"}</div>
                </div>
                <div className="p-3 bg-gray-50 rounded border">
                  <strong className="text-gray-700">Allocated Students:</strong>
                  <div className="text-lg font-bold text-gray-900">{webData.summary.total_allocated_students ?? "-"}</div>
                </div>
                <div className="p-3 bg-gray-50 rounded border">
                  <strong className="text-gray-700">Broken Seats:</strong>
                  <div className="text-lg font-bold text-gray-900">{webData.summary.broken_seats_count ?? 0}</div>
                </div>
                <div className="p-3 bg-gray-50 rounded border">
                  <strong className="text-gray-700">Unallocated:</strong>
                  <div className="text-lg font-bold text-gray-900">{(webData.summary.total_available_seats ?? 0) - (webData.summary.total_allocated_students ?? 0)}</div>
                </div>
              </div>

              {/* Unallocated per batch */}
              {webData.summary.unallocated_per_batch && (
                <div className="mt-4 p-3 bg-orange-50 rounded border border-orange-200">
                  <strong className="text-orange-700">Unallocated Students per Batch:</strong>
                  <div className="mt-2 grid grid-cols-2 md:grid-cols-4 gap-2">
                    {Object.entries(webData.summary.unallocated_per_batch).map(([batch, count]) => (
                      <div key={batch} className="text-sm text-orange-600">
                        Batch {batch}: <strong>{count}</strong>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="p-3 bg-blue-50 rounded border border-blue-200">
                  <strong className="text-blue-900">Batch Distribution</strong>
                  <pre className="text-xs mt-2 overflow-auto">{JSON.stringify(webData.summary.batch_distribution || {}, null, 2)}</pre>
                </div>
                <div className="p-3 bg-blue-50 rounded border border-blue-200">
                  <strong className="text-blue-900">Paper Set Distribution</strong>
                  <pre className="text-xs mt-2 overflow-auto">{JSON.stringify(webData.summary.paper_set_distribution || webData.summary.paper_set_distribution_per_batch || {}, null, 2)}</pre>
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
