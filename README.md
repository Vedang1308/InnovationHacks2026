# TraceTrust: High-Fidelity Agentic ESG Auditing

**TraceTrust** is a production-grade, Agentic AI platform designed to verify corporate sustainability claims using real-world science. Instead of relying on simulated data, TraceTrust connects directly to orbital atmospheric sensors and global emissions registries to fact-check ESG reports in real-time.

---

## 🚀 Key Innovations (V3.1 - Platinum Release)

- **Zero-Mock Architecture**: 100% of the audit evidence is pulled from real-world telemetry and APIs. 
    - **Live S3 Satellite Feed**: Genuinely connects to the **Amazon Sustainability Data Initiative (ASDI)** to process raw **Sentinel-5P TROPOMI** NetCDF files (`meeo-s5p`).
    - **Asset-Level Ground Truth**: Performs live REST API calls to the **Climate TRACE** world emissions registry.
- **Async Parallel Orchestration**: Uses a high-performance **LangGraph state machine** to audit massive reports. 
    - **46-Second Audit**: Successfully processes 114-page PDF reports (e.g., Amazon 2024 ESG) with multiple global facility audits in parallel.
- **Scientific Veracity Scoring**: Implements a hybrid math model that flags "Greenwashing" by comparing reported corporate mass to real atmospheric NO₂ concentrations.
- **Mission Control 2.0 Dashboard**: 
    - **SSE Agent Streaming**: Live "Reasoning Trace" of the Librarian, Geospatial, and Satellite agents.
    - **Hydration-Safe LiveMap**: High-performance, Leaflet-powered geospatial visualization with real-time facility marker plotting.

---

## 🛠️ Tech Stack

- **Core Engine**: Python, FastAPI, LangGraph, Boto3 (AWS S3), Xarray (Satellite Imaging).
- **Intelligent RAG**: Phidata Agentic Framework, FAISS (Vector DB), HuggingFace Embeddings.
- **Inference**: Ollama (`llama3.2-vision`) for structured PDF extraction.
- **Frontend**: Next.js 14, Leaflet (React-Leaflet), Tailwind CSS, Lucide-React.

---

## 🏃 Getting Started

### 1. Prerequisites
- **Ollama**: Must be running with `llama3.2-vision`.
- **HuggingFace Token**: Required for embeddings (in `backend/.env`).

### 2. Backend Installation & Launch
```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
export PYTHONPATH=$PYTHONPATH:.
uvicorn main:app --reload --port 8000
```

### 3. Frontend Installation & Launch
```bash
cd frontend
npm install
npm run dev
```
Navigate to **[http://localhost:3000](http://localhost:3000)** to launch your first orbital audit.

---

## 🌍 Sustainability Impact
TraceTrust empowers investors, NGOs, and regulators to move beyond "Net Zero" marketing by providing a hard-science audit trail. Its **Sensor-Proxy Logic** ensures that atmospheric pollutants are tracked even when corporate databases are outdated or missing data.

**Developed for Innovation Hacks 2026.**
