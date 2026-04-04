# TraceTrust: High-Fidelity Agentic ESG Auditing

**TraceTrust** is an AI-powered sustainability auditing platform that verifies corporate ESG (Environmental, Social, and Governance) claims using real-world satellite sensor data and agentic reasoning.

By combining **LangGraph orchestration** with **AWS S3 Sentinel-5P telemetry** and **Climate TRACE** emissions data, TraceTrust provides a scientifically defensible "Veracity Score" for any corporate sustainability report.

---

## 🚀 Key Features

- **Agentic RAG Pipeline**: Uses FAISS and HuggingFace embeddings to extract facility locations and reported emissions from 100+ page PDF reports.
- **Parallel Mission Control**: Audits dozens of global facilities simultaneously via an asynchronous LangGraph execution engine.
- **Satellite Veracity Evidence**: Genuinely connects to AWS S3 (`meeo-s5p`) to process raw Sentinel-5P TROPOMI NetCDF files via `xarray`.
- **Hybrid Trust Scoring**: Combines atmospheric sensor concentrations (NO₂) with mass-based emissions registries (Climate TRACE) to detect greenwashing.
- **Real-Time Streaming**: A Next.js "Mission Control" dashboard that streams agent reasoning traces via Server-Sent Events (SSE).

---

## 🛠️ Tech Stack

- **Backend**: Python, FastAPI, LangGraph (State Machine), Boto3 (AWS S3), Xarray (Satellite Processing).
- **Frontend**: React, Next.js, Leaflet (Geospatial Mapping), Tailwind CSS.
- **Models**: Ollama (llama3.2-vision), sentence-transformers (all-MiniLM-L6-v2).

---

## 🧪 Prerequisites

- **Ollama**: Ensure Ollama is running with the `llama3.2-vision` model:
  ```bash
  ollama run llama3.2-vision
  ```
- **HuggingFace Token**: Required for embeddings (set in `backend/.env`).

---

## 🏃 Getting Started

### 1. Backend Setup
```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
export PYTHONPATH=$PYTHONPATH:.
uvicorn main:app --reload --port 8000
```

### 2. Frontend Setup
```bash
cd frontend
npm install
npm run dev
```

The Mission Control dashboard will be available at `http://localhost:3000`.

---

## 🌍 Impact
TraceTrust empowers investors, regulators, and consumers to move beyond "Net Zero" marketing by providing a hard-science audit trail for every environmental claim. Its unique sensor-proxy math catches pollutants even when corporate databases are outdated.

**Developed for Innovation Hacks 2026.**
