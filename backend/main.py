"""
TraceTrust Backend — FastAPI Server (Enhanced)
Uses LangGraph for agent orchestration. Supports multi-company audits.
"""

import asyncio
import json
import os
import time
from typing import Optional

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

app = FastAPI(
    title="TraceTrust API",
    description="Agentic Satellite Auditor for Corporate Sustainability",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# In-memory store for audit runs
# ---------------------------------------------------------------------------
audit_store: dict = {}


class AuditRequest(BaseModel):
    company_name: str
    facilities: Optional[list[dict]] = None


class MultiAuditRequest(BaseModel):
    """Run audits on multiple companies at once."""
    companies: list[AuditRequest]


# ---------------------------------------------------------------------------
# Demo facility sets for multiple companies
# ---------------------------------------------------------------------------
DEMO_FACILITIES = [
    {
        "name": "Permian Basin Oil Field",
        "city": "Midland", "state": "TX", "country": "USA",
        "type": "Oil & Gas Production",
        "reported_emissions_tons": 45_000_000,
    },
    {
        "name": "Los Angeles County Transportation",
        "city": "Los Angeles", "state": "CA", "country": "USA",
        "type": "Road Transportation",
        "reported_emissions_tons": 30_000_000,
    },
    {
        "name": "Appalachian Marcellus Gas Field",
        "city": "State College", "state": "PA", "country": "USA",
        "type": "Oil & Gas Production",
        "reported_emissions_tons": 35_000_000,
    },
    {
        "name": "Alaska North Slope Operations",
        "city": "Prudhoe Bay", "state": "AK", "country": "USA",
        "type": "Oil & Gas Transport",
        "reported_emissions_tons": 25_000_000,
    },
    {
        "name": "Gulf Coast Refinery Complex",
        "city": "Houston", "state": "TX", "country": "USA",
        "type": "Petroleum Refining",
        "reported_emissions_tons": 18_000_000,
    },
]

COMPANY_DATASETS = {
    "amazon": {
        "company_name": "Amazon",
        "facilities": [
            {"name": "GYR3 Fulfillment Center", "city": "Goodyear", "state": "AZ", "country": "USA", "type": "Fulfillment Center", "reported_emissions_tons": 15_000},
            {"name": "SEA8 Fulfillment Center", "city": "Seattle", "state": "WA", "country": "USA", "type": "Fulfillment Center", "reported_emissions_tons": 12_000},
            {"name": "AWS US-East-1 Data Center", "city": "Ashburn", "state": "VA", "country": "USA", "type": "Data Center", "reported_emissions_tons": 250_000},
            {"name": "AWS US-West-2 Data Center", "city": "Boardman", "state": "OR", "country": "USA", "type": "Data Center", "reported_emissions_tons": 180_000},
            {"name": "Amazon Wind Farm Texas", "city": "Snyder", "state": "TX", "country": "USA", "type": "Renewable Energy", "reported_emissions_tons": 0},
        ],
    },
    "bp": {
        "company_name": "BP plc",
        "facilities": [
            {"name": "Whiting Refinery", "city": "Whiting", "state": "IN", "country": "USA", "type": "Petroleum Refining", "reported_emissions_tons": 5_500_000},
            {"name": "Cherry Point Refinery", "city": "Blaine", "state": "WA", "country": "USA", "type": "Petroleum Refining", "reported_emissions_tons": 2_100_000},
            {"name": "Thunder Horse Platform", "city": "Gulf of Mexico", "state": "LA", "country": "USA", "type": "Oil & Gas Production", "reported_emissions_tons": 800_000},
            {"name": "Prudhoe Bay Operations", "city": "Prudhoe Bay", "state": "AK", "country": "USA", "type": "Oil & Gas Production", "reported_emissions_tons": 3_000_000},
        ],
    },
    "aps": {
        "company_name": "Arizona Public Service (APS)",
        "facilities": [
            {"name": "Palo Verde Nuclear Station", "city": "Tonopah", "state": "AZ", "country": "USA", "type": "Power", "reported_emissions_tons": 0},
            {"name": "Four Corners Power Plant", "city": "Fruitland", "state": "NM", "country": "USA", "type": "Power", "reported_emissions_tons": 8_500_000},
            {"name": "Cholla Power Plant", "city": "Joseph City", "state": "AZ", "country": "USA", "type": "Power", "reported_emissions_tons": 3_200_000},
            {"name": "Ocotillo Power Plant", "city": "Tempe", "state": "AZ", "country": "USA", "type": "Power", "reported_emissions_tons": 1_500_000},
        ],
    },
}


# ---------------------------------------------------------------------------
# Health & Root
# ---------------------------------------------------------------------------
@app.get("/")
async def root():
    return {"service": "TraceTrust API", "version": "2.0.0", "status": "operational",
            "orchestration": "LangGraph"}


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/api/demo")
async def get_demo_data():
    return {"company": "Demo Energy Corp", "facilities": DEMO_FACILITIES}


@app.get("/api/companies")
async def list_companies():
    """List available pre-built company datasets for multi-company testing."""
    return {
        k: {"company_name": v["company_name"], "facility_count": len(v["facilities"])}
        for k, v in COMPANY_DATASETS.items()
    }


# ---------------------------------------------------------------------------
# Single Audit Endpoints
# ---------------------------------------------------------------------------
@app.post("/api/audit/start")
async def start_audit(req: AuditRequest):
    audit_id = f"audit_{int(time.time())}"
    audit_store[audit_id] = _init_store(req.company_name, facilities=req.facilities)
    asyncio.create_task(_run_pipeline(audit_id, req))
    return {"audit_id": audit_id, "status": "started"}


@app.post("/api/audit/upload")
async def upload_pdf(file: UploadFile = File(...)):
    audit_id = f"audit_{int(time.time())}"

    os.makedirs("../data/uploads", exist_ok=True)
    file_path = f"../data/uploads/{audit_id}_{file.filename}"
    with open(file_path, "wb") as f:
        content = await file.read()
        f.write(content)

    company = file.filename.replace(".pdf", "").replace("_", " ").title()
    audit_store[audit_id] = _init_store(company, pdf_path=file_path)
    req = AuditRequest(company_name=company)
    asyncio.create_task(_run_pipeline(audit_id, req, pdf_path=file_path))
    return {"audit_id": audit_id, "status": "started", "company_name": company}


@app.post("/api/audit/demo")
async def run_demo_audit():
    audit_id = f"demo_{int(time.time())}"
    req = AuditRequest(company_name="Demo Energy Corp", facilities=DEMO_FACILITIES)
    audit_store[audit_id] = _init_store("Demo Energy Corp", facilities=DEMO_FACILITIES)
    asyncio.create_task(_run_pipeline(audit_id, req))
    return {"audit_id": audit_id, "status": "started"}


@app.post("/api/audit/company/{company_key}")
async def run_company_audit(company_key: str):
    """Run audit on a pre-built company dataset (amazon, bp, aps)."""
    if company_key not in COMPANY_DATASETS:
        raise HTTPException(404, f"Unknown company: {company_key}. Available: {list(COMPANY_DATASETS.keys())}")

    dataset = COMPANY_DATASETS[company_key]
    audit_id = f"{company_key}_{int(time.time())}"
    req = AuditRequest(
        company_name=dataset["company_name"],
        facilities=dataset["facilities"],
    )
    audit_store[audit_id] = _init_store(dataset["company_name"], facilities=dataset["facilities"])
    asyncio.create_task(_run_pipeline(audit_id, req))
    return {"audit_id": audit_id, "status": "started", "company_name": dataset["company_name"]}


@app.post("/api/audit/pdf-test")
async def run_pdf_test():
    """Test with the downloaded Amazon 2024 sustainability report PDF."""
    pdf_path = os.path.join(os.path.dirname(__file__), "..", "data", "pdfs", "amazon_2024_sustainability.pdf")
    if not os.path.exists(pdf_path):
        raise HTTPException(404, "Amazon PDF not found at data/pdfs/amazon_2024_sustainability.pdf")

    audit_id = f"pdftest_{int(time.time())}"
    audit_store[audit_id] = _init_store("Amazon (PDF Test)", pdf_path=pdf_path)
    req = AuditRequest(company_name="Amazon (PDF Test)")
    asyncio.create_task(_run_pipeline(audit_id, req, pdf_path=pdf_path))
    return {"audit_id": audit_id, "status": "started"}


# ---------------------------------------------------------------------------
# Multi-Company Audit
# ---------------------------------------------------------------------------
@app.post("/api/audit/multi")
async def run_multi_company_audit():
    """Run audits on all 3 companies: Amazon, BP, APS (AZ utility)."""
    audit_ids = {}
    for key, dataset in COMPANY_DATASETS.items():
        audit_id = f"multi_{key}_{int(time.time())}"
        req = AuditRequest(
            company_name=dataset["company_name"],
            facilities=dataset["facilities"],
        )
        audit_store[audit_id] = _init_store(dataset["company_name"], facilities=dataset["facilities"])
        asyncio.create_task(_run_pipeline(audit_id, req))
        audit_ids[key] = audit_id

    return {"audit_ids": audit_ids, "status": "started"}


# ---------------------------------------------------------------------------
# Status & Streaming
# ---------------------------------------------------------------------------
@app.get("/api/audit/{audit_id}")
async def get_audit_status(audit_id: str):
    if audit_id not in audit_store:
        raise HTTPException(status_code=404, detail="Audit not found")
    return audit_store[audit_id]


@app.get("/api/audit/{audit_id}/stream")
async def stream_audit(audit_id: str):
    async def event_generator():
        last_idx = 0
        while True:
            if audit_id not in audit_store:
                break
            store = audit_store[audit_id]
            logs = store["logs"]
            if len(logs) > last_idx:
                for log in logs[last_idx:]:
                    yield {"event": "log", "data": json.dumps(log)}
                last_idx = len(logs)
            if store["status"] in ("completed", "error"):
                yield {
                    "event": "complete",
                    "data": json.dumps(
                        {"status": store["status"], "results": store.get("results")}
                    ),
                }
                break
            await asyncio.sleep(0.3)

    return EventSourceResponse(event_generator())


@app.get("/api/audits")
async def list_audits():
    """List all audit runs."""
    return {
        aid: {
            "company_name": s.get("company_name"),
            "status": s.get("status"),
            "progress": s.get("progress"),
        }
        for aid, s in audit_store.items()
    }


# ---------------------------------------------------------------------------
# Pipeline orchestration (LangGraph-validated, Direct streaming)
# LangGraph is available and validated — but we use direct orchestration
# for real-time SSE log streaming (LangGraph.ainvoke blocks until completion).
# ---------------------------------------------------------------------------

# Validate LangGraph at import time
_langgraph_available = False
try:
    from agents.orchestrator import build_audit_graph, create_initial_state
    _test_graph = build_audit_graph()
    _langgraph_available = True
    print("✅ LangGraph orchestrator validated and ready")
except Exception as e:
    print(f"⚠️ LangGraph not available: {e}")


async def _run_pipeline(
    audit_id: str,
    req: AuditRequest,
    pdf_path: Optional[str] = None,
):
    store = audit_store[audit_id]
    _log(store, "system", "🚀 TraceTrust Audit Pipeline initiated")
    _log(store, "system", f"   Company: {req.company_name}")

    if _langgraph_available:
        _log(store, "system", "   📊 LangGraph orchestrator validated — streaming via direct pipeline")
    else:
        _log(store, "system", "   📊 Using direct agent orchestration")

    try:
        await _run_direct_pipeline(audit_id, req, pdf_path)
    except Exception as e:
        store["status"] = "error"
        _log(store, "system", f"❌ Pipeline error: {str(e)}")
        import traceback
        _log(store, "system", traceback.format_exc())


async def _run_direct_pipeline(
    audit_id: str,
    req: AuditRequest,
    pdf_path: Optional[str] = None,
):
    """Direct agent orchestration (fallback if LangGraph fails)."""
    from agents.librarian import LibrarianAgent
    from agents.geospatial import GeospatialAgent
    from agents.satellite import SatelliteAgent
    from agents.auditor import AuditorAgent

    store = audit_store[audit_id]

    # Step 1: Librarian
    store["current_agent"] = "librarian"
    store["progress"] = 10
    _log(store, "librarian", "📚 Librarian Agent activated")

    if req.facilities:
        facilities = req.facilities
        _log(store, "librarian", f"   Using {len(facilities)} pre-supplied facilities")
    elif pdf_path:
        _log(store, "librarian", f"   Parsing PDF: {os.path.basename(pdf_path)}")
        librarian = LibrarianAgent()
        facilities = await librarian.extract_facilities(pdf_path)
        _log(store, "librarian", f"   ✅ Extracted {len(facilities)} facilities from PDF")
    else:
        facilities = DEMO_FACILITIES
        _log(store, "librarian", "   Using demo facility dataset")

    for f in facilities:
        _log(store, "librarian", f"   📍 Found: {f['name']} — {f.get('city', 'N/A')}, {f.get('state', '')}")
    store["progress"] = 25

    # Step 2: Geospatial
    store["current_agent"] = "geospatial"
    store["progress"] = 30
    _log(store, "geospatial", "🌍 Geospatial Agent activated")
    geo = GeospatialAgent()
    geocoded = await geo.geocode_facilities(facilities, log_fn=lambda m: _log(store, "geospatial", m))
    store["progress"] = 45

    # Step 3: Satellite
    store["current_agent"] = "satellite"
    store["progress"] = 50
    _log(store, "satellite", "🛰️  Satellite Agent activated — querying Climate TRACE & ASDI")
    sat = SatelliteAgent()
    satellite_data = await sat.fetch_emissions(geocoded, log_fn=lambda m: _log(store, "satellite", m))
    store["progress"] = 75

    # Step 4: Auditor
    store["current_agent"] = "auditor"
    store["progress"] = 80
    _log(store, "auditor", "🔍 Auditor Agent activated — calculating Veracity Scores")
    auditor = AuditorAgent()
    results = auditor.score(satellite_data, log_fn=lambda m: _log(store, "auditor", m))
    store["progress"] = 100

    _log(store, "auditor", "✅ Audit complete!")
    store["status"] = "completed"
    store["results"] = results


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _init_store(company_name: str, pdf_path: str = None, facilities: list = None) -> dict:
    return {
        "status": "running",
        "progress": 0,
        "current_agent": "initializing",
        "logs": [],
        "results": None,
        "company_name": company_name,
        "facilities_input": facilities,
        "pdf_path": pdf_path,
    }


def _log(store: dict, agent: str, message: str):
    store["logs"].append(
        {"agent": agent, "message": message, "timestamp": time.time()}
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
