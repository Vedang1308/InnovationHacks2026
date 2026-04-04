/**
 * TraceTrust — Mission Control Dashboard v2.0
 * Enhanced: Evidence View, Multi-Company, LangGraph, PDF Testing
 */

// ─── Configuration ───────────────────────────────────────────────
const API_BASE = "http://localhost:8000";
let map = null;
let markers = [];
let currentAuditId = null;
let eventSource = null;

// ─── Initialize ──────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
    initMap();
    // Close dropdown when clicking outside
    document.addEventListener("click", (e) => {
        if (!e.target.closest("#company-dropdown")) {
            document.getElementById("dropdown-menu").classList.remove("open");
        }
    });
});

function initMap() {
    map = L.map("map-container", {
        zoomControl: false,
        attributionControl: false,
    }).setView([39.5, -98.35], 4);

    L.tileLayer(
        "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
        { maxZoom: 18, subdomains: "abcd" }
    ).addTo(map);

    L.control.zoom({ position: "bottomright" }).addTo(map);
}

// ─── Dropdown ────────────────────────────────────────────────────
function toggleDropdown() {
    document.getElementById("dropdown-menu").classList.toggle("open");
}

// ─── Marker Helpers ──────────────────────────────────────────────
function clearMarkers() {
    markers.forEach((m) => map.removeLayer(m));
    markers = [];
}

function addMarker(facility) {
    const status = facility.status || "unknown";
    let className = "marker-verified";
    if (status === "caution") className = "marker-caution";
    if (status === "discrepancy") className = "marker-discrepancy";
    if (status === "unknown") className = "marker-caution";

    const icon = L.divIcon({ className, iconSize: [18, 18], iconAnchor: [9, 9] });
    const m = L.marker([facility.lat, facility.lng], { icon }).addTo(map);

    const scoreText = facility.veracity_score != null ? `${facility.veracity_score}%` : "N/A";
    const popupHtml = `
        <div style="min-width:220px">
            <strong style="font-size:0.9rem">${facility.name}</strong>
            <div style="color:#94a3b8;font-size:0.75rem;margin:4px 0">
                ${facility.city || ""}, ${facility.state || ""}
            </div>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:8px">
                <div>
                    <div style="font-size:0.6rem;text-transform:uppercase;color:#64748b">Reported</div>
                    <div style="font-weight:700">${formatTons(facility.reported_emissions_tons)}</div>
                </div>
                <div>
                    <div style="font-size:0.6rem;text-transform:uppercase;color:#64748b">Satellite</div>
                    <div style="font-weight:700">${formatTons(facility.satellite_emissions_tons)}</div>
                </div>
            </div>
            <div style="margin-top:8px;text-align:center;padding:6px;border-radius:8px;
                        background:${status === 'verified' ? 'rgba(6,214,160,0.1)' : status === 'caution' ? 'rgba(255,209,102,0.1)' : 'rgba(239,71,111,0.1)'}">
                <span style="font-weight:800;font-size:1.1rem;
                             color:${status === 'verified' ? '#06d6a0' : status === 'caution' ? '#ffd166' : '#ef476f'}">
                    ${scoreText}
                </span>
                <span style="font-size:0.65rem;display:block;color:#94a3b8">Veracity Score</span>
            </div>
        </div>
    `;
    m.bindPopup(popupHtml, { maxWidth: 280, closeButton: true });
    markers.push(m);
}

// ─── Terminal Feed ───────────────────────────────────────────────
function addTerminalLine(agent, message) {
    const term = document.getElementById("terminal-output");
    const line = document.createElement("div");
    line.className = `terminal-line ${agent}`;
    const agentNames = {
        system: "SYSTEM", librarian: "LIBRARIAN", geospatial: "GEO",
        satellite: "SATELLITE", auditor: "AUDITOR",
    };
    line.innerHTML = `
        <span class="agent-tag">${agentNames[agent] || agent.toUpperCase()}</span>
        <span class="log-msg">${escapeHtml(message)}</span>
    `;
    term.appendChild(line);
    term.scrollTop = term.scrollHeight;

    document.querySelectorAll(".agent-dot").forEach((d) => d.classList.remove("active"));
    const dot = document.getElementById(`dot-${agent}`);
    if (dot) dot.classList.add("active");
}

function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
}

// ─── Status & Progress ──────────────────────────────────────────
function setStatus(text, state = "ready") {
    const pill = document.getElementById("pipeline-status");
    pill.className = `status-pill ${state}`;
    pill.querySelector(".status-text").textContent = text;
}

function setProgress(pct) {
    document.getElementById("progress-container").style.display = "flex";
    document.getElementById("progress-fill").style.width = `${pct}%`;
    document.getElementById("progress-text").textContent = `${pct}%`;
}

function resetUI() {
    clearMarkers();
    document.getElementById("terminal-output").innerHTML = "";
    document.getElementById("results-section").style.display = "none";
    document.getElementById("evidence-section").style.display = "none";
    document.getElementById("dropdown-menu").classList.remove("open");
}

// ─── API: Run Demo Audit ─────────────────────────────────────────
async function runDemoAudit() {
    resetUI();
    setStatus("Initializing", "running");
    setProgress(0);
    addTerminalLine("system", "🚀 Starting TraceTrust demo audit...");

    try {
        const resp = await fetch(`${API_BASE}/api/audit/demo`, { method: "POST" });
        const data = await resp.json();
        currentAuditId = data.audit_id;
        addTerminalLine("system", `   Audit ID: ${currentAuditId}`);
        startEventStream(currentAuditId);
    } catch (err) {
        addTerminalLine("system", `⚠️ Backend offline — running offline demo...`);
        setStatus("Offline Demo", "running");
        await runOfflineDemo();
    }
}

// ─── API: Run Company Audit ──────────────────────────────────────
async function runCompanyAudit(companyKey) {
    resetUI();
    setStatus(`Auditing ${companyKey}`, "running");
    setProgress(0);
    addTerminalLine("system", `🏢 Starting audit for: ${companyKey.toUpperCase()}`);

    try {
        const resp = await fetch(`${API_BASE}/api/audit/company/${companyKey}`, { method: "POST" });
        const data = await resp.json();
        currentAuditId = data.audit_id;
        addTerminalLine("system", `   Company: ${data.company_name} | Audit ID: ${currentAuditId}`);
        startEventStream(currentAuditId);
    } catch (err) {
        addTerminalLine("system", `❌ Connection error: ${err.message}`);
        setStatus("Error", "error");
    }
}

// ─── API: Run Multi-Company Audit ────────────────────────────────
async function runMultiAudit() {
    resetUI();
    setStatus("Multi-Audit", "running");
    setProgress(0);
    addTerminalLine("system", "🔄 Starting multi-company audit: Amazon, BP, APS");

    try {
        const resp = await fetch(`${API_BASE}/api/audit/multi`, { method: "POST" });
        const data = await resp.json();
        const ids = Object.entries(data.audit_ids);
        addTerminalLine("system", `   Launched ${ids.length} parallel audits`);

        // Poll all audits and merge results
        await pollMultiAudits(ids);
    } catch (err) {
        addTerminalLine("system", `❌ Connection error: ${err.message}`);
        setStatus("Error", "error");
    }
}

async function pollMultiAudits(auditEntries) {
    const allResults = [];
    for (const [company, auditId] of auditEntries) {
        addTerminalLine("system", `   ⏳ Waiting for ${company}...`);
        const result = await waitForAudit(auditId);
        if (result) {
            addTerminalLine("system", `   ✅ ${company} complete — Score: ${result.overall_veracity_score}%`);
            allResults.push(...(result.facilities || []));
        }
    }

    if (allResults.length > 0) {
        const merged = buildMergedResults(allResults);
        renderResults(merged);
        renderEvidence(allResults);
        setStatus("Multi-Audit Complete", "ready");
        setProgress(100);
    }
}

async function waitForAudit(auditId) {
    for (let i = 0; i < 120; i++) {
        try {
            const resp = await fetch(`${API_BASE}/api/audit/${auditId}`);
            const data = await resp.json();
            if (data.status === "completed" && data.results) return data.results;
            if (data.status === "error") return null;
        } catch { /* retry */ }
        await sleep(1000);
    }
    return null;
}

function buildMergedResults(facilities) {
    const totalReported = facilities.reduce((s, f) => s + (f.reported_emissions_tons || 0), 0);
    const totalSatellite = facilities.reduce((s, f) => s + (f.satellite_emissions_tons || 0), 0);
    const disc = totalSatellite > 0 ? Math.abs(totalSatellite - totalReported) / totalSatellite * 100 : 0;
    return {
        company_name: "Multi-Company Audit",
        total_facilities_audited: facilities.length,
        flagged_facilities: facilities.filter(f => f.flagged).length,
        overall_veracity_score: Math.round((100 - disc) * 10) / 10,
        total_reported_tons: totalReported,
        total_satellite_tons: totalSatellite,
        facilities,
    };
}

// ─── API: PDF Test ───────────────────────────────────────────────
async function runPdfTest() {
    resetUI();
    setStatus("PDF Test", "running");
    setProgress(0);
    addTerminalLine("system", "📄 Running Amazon 2024 Sustainability Report PDF test...");

    try {
        const resp = await fetch(`${API_BASE}/api/audit/pdf-test`, { method: "POST" });
        const data = await resp.json();
        currentAuditId = data.audit_id;
        addTerminalLine("system", `   Audit ID: ${currentAuditId}`);
        startEventStream(currentAuditId);
    } catch (err) {
        addTerminalLine("system", `❌ Error: ${err.message}`);
        setStatus("Error", "error");
    }
}

async function uploadPDF(input) {
    if (!input.files.length) return;
    const file = input.files[0];
    resetUI();
    setStatus("Uploading PDF", "running");
    setProgress(5);
    addTerminalLine("system", `📄 Uploading: ${file.name}`);

    try {
        const formData = new FormData();
        formData.append("file", file);
        const resp = await fetch(`${API_BASE}/api/audit/upload`, { method: "POST", body: formData });
        const data = await resp.json();
        currentAuditId = data.audit_id;
        startEventStream(currentAuditId);
    } catch (err) {
        addTerminalLine("system", `❌ Upload failed: ${err.message}`);
        setStatus("Error", "error");
    }
}

// ─── SSE Stream ──────────────────────────────────────────────────
function startEventStream(auditId) {
    if (eventSource) eventSource.close();
    eventSource = new EventSource(`${API_BASE}/api/audit/${auditId}/stream`);

    eventSource.addEventListener("log", (e) => {
        const log = JSON.parse(e.data);
        addTerminalLine(log.agent, log.message);
    });

    eventSource.addEventListener("complete", (e) => {
        const data = JSON.parse(e.data);
        eventSource.close();
        if (data.status === "completed" && data.results) {
            renderResults(data.results);
            renderEvidence(data.results.facilities || []);
            setStatus("Audit Complete", "ready");
            setProgress(100);
        } else {
            setStatus("Error", "error");
        }
    });

    eventSource.onerror = () => {
        eventSource.close();
        pollAuditStatus(auditId);
    };
}

async function pollAuditStatus(auditId) {
    const poll = async () => {
        try {
            const resp = await fetch(`${API_BASE}/api/audit/${auditId}`);
            const data = await resp.json();
            setProgress(data.progress || 0);
            if (data.status === "completed" && data.results) {
                renderResults(data.results);
                renderEvidence(data.results.facilities || []);
                setStatus("Audit Complete", "ready");
                return;
            }
            if (data.status === "error") { setStatus("Error", "error"); return; }
            setTimeout(poll, 1000);
        } catch { setTimeout(poll, 2000); }
    };
    poll();
}

// ─── Evidence View Renderer ──────────────────────────────────────
function renderEvidence(facilities) {
    const section = document.getElementById("evidence-section");
    const container = document.getElementById("evidence-container");

    if (!facilities || facilities.length === 0) return;

    section.style.display = "block";
    container.innerHTML = "";

    // Find max emissions for relative bar sizing
    const maxEmissions = Math.max(
        ...facilities.map(f => Math.max(f.reported_emissions_tons || 0, f.satellite_emissions_tons || 0))
    );

    facilities.forEach((f) => {
        const reported = f.reported_emissions_tons || 0;
        const satellite = f.satellite_emissions_tons || 0;
        const reportedPct = maxEmissions > 0 ? (reported / maxEmissions) * 100 : 0;
        const satellitePct = maxEmissions > 0 ? (satellite / maxEmissions) * 100 : 0;
        const scoreColor = f.veracity_score >= 80 ? "#06d6a0" : f.veracity_score >= 50 ? "#ffd166" : "#ef476f";
        const statusClass = f.flagged ? "flagged" : "verified";
        const statusLabel = f.flagged ? "⚠ Flagged" : "✓ Verified";

        const ctName = f.climate_trace?.asset_name || "—";
        const ctConf = f.climate_trace?.confidence || "—";
        const asdiAvail = f.asdi?.available ? "✅ Available" : "—";
        const no2 = f.asdi?.concentration_data?.NO2;

        const card = document.createElement("div");
        card.className = "evidence-card";
        card.innerHTML = `
            <div class="evidence-card-header">
                <h3>${f.name}</h3>
                <span class="ev-status ${statusClass}">${statusLabel}</span>
            </div>
            <div class="evidence-card-body">
                <div class="evidence-side">
                    <div class="evidence-side-label report">📄 Corporate Report (Claimed)</div>
                    <div class="evidence-data-row">
                        <span class="label">Facility Type</span>
                        <span class="value">${f.type || "—"}</span>
                    </div>
                    <div class="evidence-data-row">
                        <span class="label">Location</span>
                        <span class="value">${f.city || ""}, ${f.state || ""}</span>
                    </div>
                    <div class="evidence-data-row">
                        <span class="label">Reported CO₂e</span>
                        <span class="value">${formatTons(reported)}</span>
                    </div>
                    <div class="evidence-bar-container">
                        <div class="evidence-bar-label">Reported emissions</div>
                        <div class="evidence-bar">
                            <div class="evidence-bar-fill report" style="width:${reportedPct}%"></div>
                        </div>
                    </div>
                </div>
                <div class="evidence-side">
                    <div class="evidence-side-label satellite">🛰️ Satellite Evidence (Observed)</div>
                    <div class="evidence-data-row">
                        <span class="label">Climate TRACE</span>
                        <span class="value" style="font-size:0.6rem">${ctName}</span>
                    </div>
                    <div class="evidence-data-row">
                        <span class="label">Confidence</span>
                        <span class="value">${ctConf}</span>
                    </div>
                    <div class="evidence-data-row">
                        <span class="label">Satellite CO₂e</span>
                        <span class="value">${formatTons(satellite)}</span>
                    </div>
                    <div class="evidence-data-row">
                        <span class="label">ASDI S5P</span>
                        <span class="value">${asdiAvail}</span>
                    </div>
                    ${no2 ? `<div class="evidence-data-row"><span class="label">NO₂</span><span class="value">${Number(no2).toExponential(2)} mol/m²</span></div>` : ""}
                    <div class="evidence-bar-container">
                        <div class="evidence-bar-label">Satellite observed</div>
                        <div class="evidence-bar">
                            <div class="evidence-bar-fill satellite" style="width:${satellitePct}%"></div>
                        </div>
                    </div>
                </div>
            </div>
            <div class="evidence-card-footer">
                <div>
                    <span class="source-tag ct">Climate TRACE</span>
                    <span class="source-tag asdi">ASDI</span>
                    ${f.direction ? `<span style="margin-left:8px;color:${f.direction === 'under-reported' ? '#ef476f' : '#ffd166'}">${f.direction === 'under-reported' ? '↓' : '↑'} ${f.direction}</span>` : ""}
                </div>
                <span class="evidence-score" style="color:${scoreColor}">
                    V = ${f.veracity_score != null ? f.veracity_score + "%" : "N/A"}
                </span>
            </div>
        `;
        container.appendChild(card);
    });
}

// ─── Results Renderer ────────────────────────────────────────────
function renderResults(results) {
    const section = document.getElementById("results-section");
    section.style.display = "block";

    const score = results.overall_veracity_score;
    const scoreClass = score >= 80 ? "verified" : score >= 50 ? "caution" : "discrepancy";
    const scoreBadge = document.getElementById("overall-score");
    scoreBadge.className = `overall-score-badge ${scoreClass}`;
    scoreBadge.textContent = `Overall: ${score != null ? score + "%" : "N/A"}`;

    document.getElementById("summary-cards").innerHTML = `
        <div class="stat-card">
            <div class="stat-label">Facilities Audited</div>
            <div class="stat-value cyan">${results.total_facilities_audited}</div>
        </div>
        <div class="stat-card">
            <div class="stat-label">Flagged</div>
            <div class="stat-value red">${results.flagged_facilities}</div>
        </div>
        <div class="stat-card">
            <div class="stat-label">Total Reported</div>
            <div class="stat-value blue">${formatTons(results.total_reported_tons)}</div>
        </div>
        <div class="stat-card">
            <div class="stat-label">Total Satellite</div>
            <div class="stat-value yellow">${formatTons(results.total_satellite_tons)}</div>
        </div>
    `;

    const facilDiv = document.getElementById("facility-cards");
    facilDiv.innerHTML = "";
    clearMarkers();
    const bounds = [];

    results.facilities.forEach((f) => {
        if (f.lat && f.lng) { addMarker(f); bounds.push([f.lat, f.lng]); }

        const scoreColor = f.veracity_score == null ? "#94a3b8"
            : f.veracity_score >= 80 ? "#06d6a0"
            : f.veracity_score >= 50 ? "#ffd166" : "#ef476f";

        const card = document.createElement("div");
        card.className = `facility-card ${f.flagged ? "flagged" : ""}`;
        card.innerHTML = `
            <div class="fc-top">
                <div>
                    <div class="fc-name">${f.name}</div>
                    <div class="fc-location">${f.city || ""}, ${f.state || ""} • ${f.type || ""}</div>
                </div>
                <div class="fc-score" style="color:${scoreColor}">
                    ${f.veracity_score != null ? f.veracity_score + "%" : "N/A"}
                </div>
            </div>
            <div class="fc-body">
                <div class="fc-metric">
                    <span class="fc-metric-label">Reported Emissions</span>
                    <span class="fc-metric-value">${formatTons(f.reported_emissions_tons)}</span>
                </div>
                <div class="fc-metric">
                    <span class="fc-metric-label">Satellite Observed</span>
                    <span class="fc-metric-value">${formatTons(f.satellite_emissions_tons)}</span>
                </div>
                <div class="fc-metric">
                    <span class="fc-metric-label">Discrepancy</span>
                    <span class="fc-metric-value" style="color:${f.discrepancy_pct > 20 ? '#ef476f' : '#06d6a0'}">
                        ${f.discrepancy_pct != null ? f.discrepancy_pct + "%" : "N/A"}
                    </span>
                </div>
                <div class="fc-metric">
                    <span class="fc-metric-label">Climate TRACE</span>
                    <span class="fc-metric-value" style="font-size:0.75rem">
                        ${f.climate_trace?.asset_name || (f.climate_trace?.found ? "✅ Matched" : "—")}
                    </span>
                </div>
            </div>
            <div class="fc-footer">
                <div class="fc-direction ${f.direction === "under-reported" ? "under" : "over"}">
                    ${f.direction === "under-reported" ? "↓" : "↑"} ${f.direction || "—"}
                </div>
                <div class="fc-sources">
                    <span class="source-tag ct">Climate TRACE</span>
                    <span class="source-tag asdi">ASDI</span>
                </div>
            </div>
        `;
        facilDiv.appendChild(card);
    });

    if (bounds.length > 0) map.fitBounds(bounds, { padding: [50, 50], maxZoom: 6 });
}

// ─── Offline Demo ────────────────────────────────────────────────
async function runOfflineDemo() {
    const facilities = [
        { name: "Permian Basin Oil Field", city: "Midland", state: "TX", lat: 31.9973, lng: -102.0779,
          type: "Oil & Gas Production", reported_emissions_tons: 45000000, satellite_emissions_tons: 68817666,
          veracity_score: 34.6, discrepancy_pct: 65.4, direction: "under-reported", flagged: true, status: "discrepancy",
          climate_trace: { found: true, asset_name: "Permian Midland Spraberry Oil TX", confidence: "low" },
          asdi: { available: true, concentration_data: { NO2: 8.5e-5 } } },
        { name: "Los Angeles County Transportation", city: "Los Angeles", state: "CA", lat: 34.0522, lng: -118.2437,
          type: "Road Transportation", reported_emissions_tons: 30000000, satellite_emissions_tons: 38700675,
          veracity_score: 77.5, discrepancy_pct: 22.5, direction: "under-reported", flagged: true, status: "caution",
          climate_trace: { found: true, asset_name: "Los Angeles County", confidence: "low" },
          asdi: { available: true, concentration_data: { NO2: 1.2e-4 } } },
        { name: "Appalachian Marcellus Gas Field", city: "State College", state: "PA", lat: 40.7934, lng: -77.86,
          type: "Oil & Gas Production", reported_emissions_tons: 35000000, satellite_emissions_tons: 45249905,
          veracity_score: 77.4, discrepancy_pct: 22.6, direction: "under-reported", flagged: true, status: "caution",
          climate_trace: { found: true, asset_name: "Appalachian Marcellus Dry Gas PA", confidence: "low" },
          asdi: { available: true, concentration_data: { NO2: 6.1e-5 } } },
        { name: "Alaska North Slope Operations", city: "Prudhoe Bay", state: "AK", lat: 70.2553, lng: -148.3372,
          type: "Oil & Gas Transport", reported_emissions_tons: 25000000, satellite_emissions_tons: 38156015,
          veracity_score: 65.5, discrepancy_pct: 34.5, direction: "under-reported", flagged: true, status: "discrepancy",
          climate_trace: { found: true, asset_name: "Alaska North Slope Gas AK", confidence: "low" },
          asdi: { available: true, concentration_data: { NO2: 3.2e-5 } } },
        { name: "Gulf Coast Refinery Complex", city: "Houston", state: "TX", lat: 29.7604, lng: -95.3698,
          type: "Petroleum Refining", reported_emissions_tons: 18000000, satellite_emissions_tons: 19500000,
          veracity_score: 92.3, discrepancy_pct: 7.7, direction: "under-reported", flagged: false, status: "verified",
          climate_trace: { found: true, asset_name: "Houston Ship Channel Refineries", confidence: "low" },
          asdi: { available: true, concentration_data: { NO2: 9.8e-5 } } },
    ];

    const logs = [
        ["system", "📊 Using LangGraph orchestrator (offline simulation)"],
        ["librarian", "📚 Librarian Agent activated"],
        ["librarian", "   Using demo facility dataset"],
        ...facilities.map(f => ["librarian", `   📍 Found: ${f.name} — ${f.city}, ${f.state}`]),
        ["geospatial", "🌍 Geospatial Agent activated"],
        ...facilities.map(f => ["geospatial", `   ✅ Located: ${f.name} → (${f.lat.toFixed(4)}, ${f.lng.toFixed(4)})`]),
        ["satellite", "🛰️  Satellite Agent activated — querying Climate TRACE & ASDI"],
        ...facilities.flatMap(f => [
            ["satellite", `   🛰️  Querying data for: ${f.name}`],
            ["satellite", `   📊 Climate TRACE match: "${f.climate_trace.asset_name}" — ${formatTons(f.satellite_emissions_tons)} CO₂e`],
            ["satellite", `   🌐 ASDI Sentinel-5P data available for (${f.lat.toFixed(2)}, ${f.lng.toFixed(2)})`],
            ["satellite", `   📡 S3: s3://meeo-s5p/OFFL/ | NO₂ concentration: ${f.asdi.concentration_data.NO2.toExponential(2)} mol/m²`],
        ]),
        ["auditor", "🔍 Auditor Agent activated — calculating Veracity Scores"],
        ...facilities.map(f => {
            const emoji = f.flagged ? "🔴" : "🟢";
            return ["auditor", `   ${emoji} ${f.name}: V=${f.veracity_score}% | Reported=${formatTons(f.reported_emissions_tons)} | Satellite=${formatTons(f.satellite_emissions_tons)} | ${f.direction}`];
        }),
        ["auditor", "   📋 Overall Veracity Score: 63.2%"],
        ["auditor", "   🚩 4/5 facilities flagged (>20% discrepancy)"],
        ["auditor", "✅ Audit complete!"],
    ];

    for (const [agent, msg] of logs) {
        addTerminalLine(agent, msg);
        setProgress(Math.round(((logs.indexOf([agent, msg]) + 1) / logs.length) * 100));
        await sleep(60 + Math.random() * 80);
    }

    const totalR = facilities.reduce((s, f) => s + f.reported_emissions_tons, 0);
    const totalS = facilities.reduce((s, f) => s + f.satellite_emissions_tons, 0);
    const results = {
        company_name: "Demo Energy Corp",
        total_facilities_audited: facilities.length,
        flagged_facilities: facilities.filter(f => f.flagged).length,
        overall_veracity_score: Math.round((100 - Math.abs(totalS - totalR) / totalS * 100) * 10) / 10,
        total_reported_tons: totalR,
        total_satellite_tons: totalS,
        facilities,
    };

    renderResults(results);
    renderEvidence(facilities);
    setStatus("Audit Complete", "ready");
    setProgress(100);
}

// ─── Utilities ───────────────────────────────────────────────────
function formatTons(tons) {
    if (tons == null) return "N/A";
    if (tons >= 1_000_000) return `${(tons / 1_000_000).toFixed(1)}M tons`;
    if (tons >= 1_000) return `${(tons / 1_000).toFixed(0)}K tons`;
    return `${tons} tons`;
}

function sleep(ms) {
    return new Promise(r => setTimeout(r, ms));
}
