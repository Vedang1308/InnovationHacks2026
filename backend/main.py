from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
import os
import json
from typing import List, Dict, Any
from agents.librarian import LibrarianAgent
from agents.geospatial import GeospatialAgent
from agents.satellite import SatelliteAgent
from agents.auditor import AuditorAgent

app = FastAPI(title="TraceTrust API", version="1.1.0")

# Enable CORS for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Agents
librarian = LibrarianAgent(data_dir="data/")
geospatial = GeospatialAgent(cache_file="data/geo_cache.json")
satellite = SatelliteAgent()
auditor = AuditorAgent()

# Shared state (In-memory for prototype)
audit_history: Dict[str, Any] = {}

async def run_audit_sequence(file_path: str, audit_id: str):
    """
    Background task to run the full TraceTrust audit pipeline.
    """
    audit_history[audit_id] = {"status": "Processing", "logs": ["Audit sequence initiated."]}
    
    try:
        # 1. Librarian (Extraction)
        audit_history[audit_id]["logs"].append("Librarian Agent parsing PDF using RAG/FAISS...")
        # Since ingestion can be slow, I'm using the Librarian with RAG
        facilities = librarian.extract_facilities_from_pdf(file_path)
        audit_history[audit_id]["logs"].append(f"Successfully extracted {len(facilities)} facilities.")
        
        results = []
        for fac in facilities:
            name = fac.get("name", "Unknown Facility")
            loc_str = fac.get("location", "")
            reported = fac.get("reported_emissions", 0.0)
            
            # 2. Geospatial (Geocoding)
            audit_history[audit_id]["logs"].append(f"Geocoding {name} at {loc_str}...")
            coords = geospatial.geocode(loc_str)
            
            if coords:
                # 3. Satellite (ASDI/Climate TRACE)
                audit_history[audit_id]["logs"].append(f"Querying satellite data for {name}...")
                sat_data = satellite.get_emissions_from_climate_trace(coords["lat"], coords["lon"])
                sat_emissions = sat_data[0]["emissions_tco2e"] if sat_data else 0.0
                
                # 4. Auditor (Scoring)
                audit_history[audit_id]["logs"].append(f"Calculating Veracity Score for {name}...")
                score = auditor.calculate_veracity_score(float(reported), sat_emissions)
                
                results.append({
                    "name": name,
                    "location": loc_str,
                    "coords": coords,
                    "reported": reported,
                    "satellite": sat_emissions,
                    **score
                })
        
        # Final Summary
        summary = auditor.generate_audit_report(results)
        audit_history[audit_id].update({
            "status": "Complete",
            "results": summary,
            "logs": audit_history[audit_id]["logs"] + ["Audit complete. Reports generated."]
        })
        
    except Exception as e:
        audit_history[audit_id]["status"] = "Failed"
        audit_history[audit_id]["logs"].append(f"ERROR: {str(e)}")

@app.get("/")
async def root():
    return {"message": "TraceTrust API is online", "status": "active"}

@app.post("/audit/upload")
async def upload_report(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    """Upload an ESG report (PDF) for auditing."""
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")
    
    file_path = f"data/{file.filename}"
    with open(file_path, "wb") as f:
        f.write(await file.read())
    
    audit_id = f"audit_{os.urandom(4).hex()}"
    background_tasks.add_task(run_audit_sequence, file_path, audit_id)
    
    return {"audit_id": audit_id, "message": "Audit sequence initiated."}

@app.get("/audit/{audit_id}")
async def get_audit_status(audit_id: str):
    """Retrieve the status and results of an audit."""
    if audit_id not in audit_history:
        raise HTTPException(status_code=404, detail="Audit ID not found.")
    return audit_history[audit_id]

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
