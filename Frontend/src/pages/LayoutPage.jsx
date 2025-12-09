import { useEffect } from "react";

export default function LayoutPage() {

  useEffect(() => {
    // When component loads, attach listeners & initial generation
    updateBatchInputs();
    generateSeatingChart();

    document.getElementById("num-batches")
      .addEventListener("change", updateBatchInputs);

    document.getElementById("generateBtn")
      .addEventListener("click", generateSeatingChart);
  }, []);

  // -------------------- Dynamic Inputs --------------------
  function updateBatchInputs() {
    const numBatches = parseInt(document.getElementById("num-batches").value) || 3;
    const container = document.getElementById("batch-rolls-inputs");
    container.innerHTML = "";

    const colors = ["blue", "green", "indigo", "purple", "pink", "red", "yellow", "cyan", "amber", "rose"];

    for (let i = 1; i <= numBatches; i++) {
      const colorClass = colors[(i - 1) % colors.length];
      const defaultRoll = i === 1 ? 1 : i === 2 ? 101 : i === 3 ? 201 : (i * 100 + 1);

      const div = document.createElement("div");
      div.innerHTML = `
        <label class="block text-sm font-medium text-gray-700 mb-1">
          Batch ${i} Start Roll
        </label>
        <input 
          type="number" 
          id="startRoll${i}" 
          min="1" 
          value="${defaultRoll}"
          class="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm 
          focus:outline-none focus:ring-2 focus:ring-${colorClass}-500"
        />
      `;
      container.appendChild(div);
    }
  }

  // -------------------- Generate Seating --------------------
  function generateSeatingChart() {
    const rows = parseInt(document.getElementById("rows").value);
    const cols = parseInt(document.getElementById("cols").value);
    const numBatches = parseInt(document.getElementById("num-batches").value);

    const chart = document.getElementById("seating-chart");
    chart.innerHTML = "";
    chart.style.setProperty("--cols", cols);

    if (!rows || !cols) {
      chart.innerHTML =
        '<p class="text-center text-gray-500 col-span-full">Please enter valid rows and columns.</p>';
      return;
    }

    let startRollsStr = "";
    for (let i = 1; i <= numBatches; i++) {
      const rollInput = document.getElementById(`startRoll${i}`);
      if (rollInput) startRollsStr += `${i}:${rollInput.value},`;
    }

    const payload = {
      rows,
      cols,
      num_batches: numBatches,
      block_width: parseInt(document.getElementById("block-width").value),
      batch_by_column: document.getElementById("fillByColumn").checked,
      broken_seats: document.getElementById("broken-seats").value,
      start_serials: startRollsStr
    };

    fetch("/api/generate-seating", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    })
      .then((r) => r.json())
      .then((data) => {
        if (data.error) {
          document.getElementById("validation-result").innerHTML =
            `<div class="text-red-600">${data.error}</div>`;
          return;
        }

        // Render seating
        const seating = data.seating || [];

        seating.forEach((row) => {
          row.forEach((seat) => {
            const seatDiv = document.createElement("div");
            seatDiv.className =
              "rounded-lg p-3 text-center shadow-md border border-gray-300 min-h-[96px] w-[88px] flex flex-col justify-center items-center";

            if (seat.is_broken) {
              seatDiv.style.backgroundColor = "red";
              seatDiv.innerHTML =
                `<div class="text-white font-bold">BROKEN</div>`;
            } else {
              seatDiv.innerHTML = `
                <div class="font-semibold">Batch ${seat.batch}</div>
                <div class="font-bold text-sm">${seat.roll_number}</div>
                <div class="text-xs opacity-70">${seat.position}</div>
              `;
            }
            chart.appendChild(seatDiv);
          });
        });
      });
  }

  // -------------------- JSX RETURN --------------------
  return (
    <div className="bg-gray-100 min-h-screen flex items-center justify-center p-6">
      <div className="w-full max-w-6xl mx-auto">
        <h1 className="text-3xl font-bold text-center text-gray-800 mb-8">
          Classroom Seating Arrangement
        </h1>

        {/* CONTROLS CARD */}
        <div className="bg-white rounded-xl shadow-lg p-6 mb-8">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">

            {/* ROWS */}
            <div>
              <label className="block text-sm mb-1">Total Rows</label>
              <input
                id="rows"
                type="number"
                defaultValue={8}
                className="w-full px-3 py-2 border rounded"
              />
            </div>

            {/* COLS */}
            <div>
              <label className="block text-sm mb-1">Total Columns</label>
              <input
                id="cols"
                type="number"
                defaultValue={10}
                className="w-full px-3 py-2 border rounded"
              />
            </div>

            {/* BATCHES */}
            <div>
              <label className="block text-sm mb-1">Number of Batches</label>
              <input
                id="num-batches"
                type="number"
                defaultValue={3}
                className="w-full px-3 py-2 border rounded"
              />
            </div>

            {/* BROKEN SEATS */}
            <div>
              <label className="block text-sm mb-1">Broken Seats (Row-Col)</label>
              <input
                id="broken-seats"
                placeholder="1-3,2-1"
                className="w-full px-3 py-2 border rounded"
              />
            </div>

            {/* DYNAMIC BATCH START ROLLS */}
            <div className="md:col-span-3">
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Batch Start Rolls
              </label>
              <div id="batch-rolls-inputs" className="grid grid-cols-1 md:grid-cols-3 gap-2"></div>
            </div>

            {/* BLOCK WIDTH */}
            <div>
              <label className="block text-sm mb-1">Block Width (cols)</label>
              <input
                id="block-width"
                type="number"
                defaultValue={3}
                className="w-full px-3 py-2 border rounded"
              />
            </div>

            {/* COLUMN FILL */}
            <div>
              <label className="block text-sm mb-1">Fill by Column</label>
              <input id="fillByColumn" type="checkbox" defaultChecked />
            </div>
          </div>

          {/* BUTTONS */}
          <div className="text-center mt-6 flex gap-3 justify-center">
            <button id="generateBtn" className="bg-blue-600 text-white px-6 py-2 rounded">
              Generate Chart
            </button>
          </div>
        </div>

        {/* SEATING CHART */}
        <div className="bg-white rounded-xl shadow-lg p-6">
          <div id="validation-result" className="mb-4"></div>
          <div
            id="seating-chart"
            className="grid gap-3 overflow-auto"
            style={{ gridTemplateColumns: "repeat(var(--cols, 10), 96px)" }}
          ></div>
        </div>
      </div>
    </div>
  );
}
