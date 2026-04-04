from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse
import os
import uuid
import time
import asyncio
import json
from typing import List, Dict, Any
from agents.orchestrator import TraceTrustOrchestrator

app = FastAPI(title="TraceTrust Agentic API", version="2.0.0")

# Enable CORS for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # For hackathon accessibility
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global state for audit monitoring
audit_db: Dict[str, Any] = {}
event_queues: Dict[str, asyncio.Queue] = {}

async def audit_event_callback(audit_id: str, agent: str, message: str, data: Any = None):
    """
    Callback passed to the Orchestrator to stream events.
    """
    if audit_id in event_queues:
        payload = {
            "agent": agent,
            "message": message,
            "data": data,
            "timestamp": time.time()
        }
        await event_queues[audit_id].put(payload)
        
        # Also update the persistent log
        if audit_id in audit_db:
            audit_db[audit_id]["logs"].append(payload)

async def execute_audit_graph(audit_id: str, pdf_path: str):
    """
    Background worker to invoke the LangGraph state machine with event streaming.
    """
    # Create the orchestrator with the streaming callback
    orc = TraceTrustOrchestrator(
        event_callback=lambda agent, msg, data: audit_event_callback(audit_id, agent, msg, data)
    )
    
    try:
        final_state = await orc.run_audit(pdf_path, audit_id)
        audit_db[audit_id].update({
            "status": "Complete",
            "results": final_state.get("audit_results"),
            "end_time": time.time()
        })
        # Signal end of stream
        await audit_event_callback(audit_id, "system", "FINALIZE", {"status": "Complete"})
    except Exception as e:
        audit_db[audit_id].update({
            "status": "Failed",
            "error": str(e)
        })
        await audit_event_callback(audit_id, "system", f"ERROR: {str(e)}", {"status": "Failed"})

@app.get("/")
async def health_check():
    return {"service": "TraceTrust 2.0", "engine": "LangGraph", "status": "online"}

@app.post("/audit/upload")
async def start_audit(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Audit requires a valid PDF report.")
    
    file_path = f"data/{file.filename}"
    with open(file_path, "wb") as f:
        f.write(await file.read())
    
    audit_id = f"aud_{uuid.uuid4().hex[:8]}"
    audit_db[audit_id] = {
        "id": audit_id,
        "status": "Initializing",
        "logs": [],
        "results": None,
        "start_time": time.time()
    }
    event_queues[audit_id] = asyncio.Queue()
    
    background_tasks.add_task(execute_audit_graph, audit_id, file_path)
    
    return {"audit_id": audit_id, "status": "initiated"}

@app.get("/audit/events/{audit_id}")
async def audit_events(audit_id: str):
    """
    SSE Endpoint for real-time audit streaming.
    """
    if audit_id not in event_queues:
        raise HTTPException(status_code=404, detail="Audit stream not found.")

    async def event_generator():
        queue = event_queues[audit_id]
        try:
            while True:
                event = await queue.get()
                yield {"data": json.dumps(event)}
                if event["agent"] == "system" and event["data"].get("status") in ("Complete", "Failed"):
                    break
        except asyncio.CancelledError:
            pass

    return EventSourceResponse(event_generator())

@app.get("/audit/{audit_id}")
async def get_audit(audit_id: str):
    if audit_id not in audit_db:
        raise HTTPException(status_code=404, detail="Audit ID not found.")
    return audit_db[audit_id]

@app.get("/history")
async def get_history():
    return sorted(
        [v for v in audit_db.values()],
        key=lambda x: x.get("start_time", 0),
        reverse=True
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
