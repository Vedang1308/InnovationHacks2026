"""
Librarian Agent — NLP Specialist (Enhanced v3)
Extracts facility information from corporate sustainability PDFs using:
  1. RAG (FAISS + HuggingFace embeddings) for semantic chunk retrieval
  2. ClimateBERT for validating climate-relevance of extracted chunks
  3. Ollama/Llama 3 for intelligent LLM extraction
  4. pypdf + unstructured for text extraction
  5. Regex heuristics as final fallback

Merges the best of both branches:
  - main: live pipeline, async, timeout handling, regex fallback
  - harshith: FAISS RAG, ClimateBERT validation, structured prompting
"""

import json
import re
from typing import Optional

import httpx


OLLAMA_BASE = "http://localhost:11434"

FACILITY_EXTRACTION_PROMPT = """You are an expert ESG data analyst. I will give you text from a corporate sustainability report.
Extract ALL physical facilities, assets, buildings, data centers, fulfillment centers, warehouses, plants, and offices mentioned.

For each facility, extract:
- name: The facility name or identifier
- city: The city where it is located
- state: The state/province (if applicable)
- country: The country
- type: The type of facility (e.g., "Fulfillment Center", "Data Center", "Wind Farm", "Solar Farm", "Office", "Warehouse", etc.)
- reported_emissions_tons: Any reported CO2/GHG emissions in metric tons (null if not specified)

Return ONLY a valid JSON array. Example:
[
  {"name": "GYR3 Fulfillment Center", "city": "Goodyear", "state": "AZ", "country": "USA", "type": "Fulfillment Center", "reported_emissions_tons": null},
  {"name": "HQ2 Office", "city": "Arlington", "state": "VA", "country": "USA", "type": "Office", "reported_emissions_tons": 5000}
]

If no facilities are found, return an empty array: []

TEXT FROM SUSTAINABILITY REPORT:
"""


class LibrarianAgent:
    """Parses sustainability PDFs and extracts facility/asset data.

    Pipeline order:
      1. Extract text from PDF (pypdf → unstructured fallback)
      2. RAG ingest → semantic search for facility-relevant chunks
      3. ClimateBERT filter: keep only climate-relevant chunks
      4. LLM extraction (Ollama) on filtered context
      5. Regex heuristic fallback if LLM/RAG unavailable
    """

    def __init__(self):
        # Lazy-init RAG and ClimateBERT (may not be available)
        self._rag = None
        self._climate_bert = None
        self._rag_initialized = False
        self._cb_initialized = False

    def _get_rag(self):
        if not self._rag_initialized:
            self._rag_initialized = True
            try:
                from agents.rag_processor import RAGProcessor
                self._rag = RAGProcessor()
                if not self._rag.available:
                    print(f"⚠️  RAG unavailable: {self._rag.import_error}")
                    self._rag = None
                else:
                    print("✅ RAG Processor (FAISS + HuggingFace) ready")
            except Exception as e:
                print(f"⚠️  RAG import error: {e}")
                self._rag = None
        return self._rag

    def _get_climate_bert(self):
        if not self._cb_initialized:
            self._cb_initialized = True
            try:
                from agents.climate_auditor import ClimateAuditorAgent
                self._climate_bert = ClimateAuditorAgent()
                if self._climate_bert.available:
                    print("✅ ClimateBERT validator ready")
                else:
                    print("ℹ️  ClimateBERT skipped (no HF_TOKEN)")
            except Exception as e:
                print(f"⚠️  ClimateBERT import error: {e}")
                self._climate_bert = None
        return self._climate_bert

    async def extract_facilities(self, pdf_path: str, log_fn=None) -> list[dict]:
        """Extract facility information from a sustainability PDF.

        Enhanced pipeline:
          1. Extract raw text from PDF
          2. Try RAG path: ingest → semantic query → ClimateBERT filter → LLM
          3. If RAG unavailable: keyword-scored sections → LLM
          4. Fallback: regex heuristics
        """
        def _log(msg):
            if log_fn:
                log_fn(msg)

        # Step 1: Extract text
        text = await self._extract_text(pdf_path)
        if not text or len(text) < 100:
            _log("   ⚠️  PDF text too short, using demo facilities")
            return self._demo_facilities()

        _log(f"   📄 Extracted {len(text):,} characters from PDF")

        # Step 2: Try RAG path (FAISS semantic search)
        rag = self._get_rag()
        rag_context = None

        if rag is not None:
            _log("   🔍 RAG: Ingesting PDF into FAISS vector index...")
            chunk_count = await rag.ingest_report(pdf_path)
            if chunk_count > 0:
                _log(f"   📊 RAG: Indexed {chunk_count} chunks with all-MiniLM-L6-v2 embeddings")

                # Semantic query for facility data
                query = (
                    "Detailed list of physical facilities, manufacturing sites, "
                    "data centers, fulfillment centers, locations, and their "
                    "Scope 1 or Scope 2 CO2 emissions"
                )
                chunks = await rag.query_report(query, k=10)
                _log(f"   🎯 RAG: Found {len(chunks)} relevant chunks via similarity search")

                # Step 2b: ClimateBERT filtering
                cb = self._get_climate_bert()
                if cb is not None and cb.available:
                    _log("   🧠 ClimateBERT: Validating climate-relevance of chunks...")
                    filtered = await cb.filter_relevant_chunks(chunks)
                    removed = len(chunks) - len(filtered)
                    if removed > 0:
                        _log(f"   ✂️  ClimateBERT: Filtered out {removed} non-climate chunks")
                    chunks = filtered

                # Build context from RAG chunks
                if chunks:
                    rag_context = "\n--- Section ---\n".join(
                        c["content"] for c in chunks
                    )

        # Step 3: LLM extraction
        context_for_llm = rag_context or self._find_relevant_sections(text)
        if not context_for_llm:
            context_for_llm = text[:8000]

        source_label = "RAG+ClimateBERT" if rag_context else "keyword-scored"
        _log(f"   🤖 Sending {source_label} context to LLM...")
        facilities = await self._llm_extract(context_for_llm)
        if facilities:
            _log(f"   ✅ LLM extracted {len(facilities)} facilities")
            return facilities

        # Step 4: Fallback to regex
        _log("   🔧 LLM unavailable, using regex heuristics...")
        facilities = self._parse_facilities_from_text(text)
        if facilities:
            _log(f"   ✅ Regex extracted {len(facilities)} facilities")
            return facilities

        return self._demo_facilities()

    async def _extract_text(self, pdf_path: str) -> str:
        """Extract text using pypdf (fast) with unstructured as enrichment."""
        import asyncio

        text = ""

        # Try pypdf first (fastest, ~2s even for large PDFs)
        try:
            from pypdf import PdfReader
            reader = PdfReader(pdf_path)
            pages_text = []
            for page in reader.pages[:50]:  # Cap at 50 pages for speed
                t = page.extract_text()
                if t:
                    pages_text.append(t)
            text = "\n".join(pages_text)
        except Exception:
            pass

        # If pypdf got enough text, return it
        if text and len(text) > 500:
            return text

        # Fallback: try unstructured with timeout
        try:
            from unstructured.partition.pdf import partition_pdf

            loop = asyncio.get_event_loop()
            elements = await asyncio.wait_for(
                loop.run_in_executor(None, lambda: partition_pdf(pdf_path)),
                timeout=30.0,  # 30s timeout
            )
            unstructured_text = "\n".join([str(el) for el in elements])
            if unstructured_text and len(unstructured_text) > len(text):
                return unstructured_text
        except (asyncio.TimeoutError, Exception):
            pass

        return text

    async def _llm_extract(self, text: str) -> list[dict]:
        """Use Ollama (Llama 3) to intelligently extract facilities."""
        prompt = FACILITY_EXTRACTION_PROMPT + text[:10000]  # Cap context size

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                resp = await client.post(
                    f"{OLLAMA_BASE}/api/generate",
                    json={
                        "model": "llama3",
                        "prompt": prompt,
                        "stream": False,
                        "options": {
                            "temperature": 0.1,
                            "num_predict": 4096,
                        },
                    },
                )
                if resp.status_code == 200:
                    result = resp.json()
                    response_text = result.get("response", "")
                    return self._parse_llm_response(response_text)
        except Exception:
            pass

        return []

    def _find_relevant_sections(self, text: str, max_chars: int = 8000) -> str:
        """Find sections of the PDF most likely to contain facility data."""
        keywords = [
            "facility", "facilities", "data center", "fulfillment",
            "warehouse", "office", "plant", "wind farm", "solar farm",
            "location", "asset", "operations", "renewable", "energy",
            "emissions", "carbon", "scope 1", "scope 2", "ghg",
        ]

        lines = text.split("\n")
        scored_sections = []

        # Score each 20-line window
        window_size = 20
        for i in range(0, len(lines), window_size // 2):
            window = lines[i : i + window_size]
            window_text = "\n".join(window)
            score = sum(
                window_text.lower().count(kw) for kw in keywords
            )
            if score > 0:
                scored_sections.append((score, window_text))

        scored_sections.sort(key=lambda x: x[0], reverse=True)

        # Take the top sections up to max_chars
        result = []
        total = 0
        for score, section in scored_sections:
            if total + len(section) > max_chars:
                break
            result.append(section)
            total += len(section)

        return "\n---\n".join(result)

    @staticmethod
    def _parse_llm_response(response: str) -> list[dict]:
        """Parse JSON from LLM response, handling markdown code blocks."""
        # Handle ```json ... ``` blocks
        json_match = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", response, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass

        # Try raw JSON
        array_match = re.search(r"\[.*\]", response, re.DOTALL)
        if array_match:
            try:
                return json.loads(array_match.group(0))
            except json.JSONDecodeError:
                pass

        # ast.literal_eval fallback (from harshith branch)
        import ast
        if array_match:
            try:
                return ast.literal_eval(array_match.group(0))
            except Exception:
                pass

        return []

    # ------------------------------------------------------------------
    # Regex-based heuristic parser (fallback)
    # ------------------------------------------------------------------
    def _parse_facilities_from_text(self, text: str) -> list[dict]:
        """Pull structured facility data from raw PDF text using patterns."""
        facilities: list[dict] = []

        # Pattern 1: "Facility Name — City, ST"
        pattern = re.compile(
            r"(?P<name>[A-Z][\w\s&\-]+?)\s*[-–—]\s*"
            r"(?P<city>[A-Z][\w\s]+),\s*(?P<state>[A-Z]{2})",
            re.MULTILINE,
        )
        for m in pattern.finditer(text):
            facilities.append(
                {
                    "name": m.group("name").strip(),
                    "city": m.group("city").strip(),
                    "state": m.group("state").strip(),
                    "country": "USA",
                    "type": "Unknown",
                    "reported_emissions_tons": self._extract_nearby_number(text, m.start()),
                }
            )

        # Pattern 2: "Fulfillment Center", "Data Center" etc.
        fc_pattern = re.compile(
            r"(?P<name>\w[\w\d]+\s+(?:Fulfillment|Data|Distribution|Logistics)\s+Center)"
            r"[\s,]*(?P<city>[A-Z][\w\s]+),?\s*(?P<state>[A-Z]{2})?",
            re.IGNORECASE,
        )
        for m in fc_pattern.finditer(text):
            name = m.group("name").strip()
            if not any(f["name"] == name for f in facilities):
                facilities.append(
                    {
                        "name": name,
                        "city": m.group("city").strip() if m.group("city") else "",
                        "state": m.group("state") or "",
                        "country": "USA",
                        "type": "Logistics",
                        "reported_emissions_tons": self._extract_nearby_number(text, m.start()),
                    }
                )

        # Pattern 3: "wind farm", "solar farm" with location
        energy_pattern = re.compile(
            r"(?P<name>[\w\s]+(?:Wind|Solar|Wind\s+Farm|Solar\s+Farm)[\w\s]*)"
            r"[\s,in]+(?P<city>[A-Z][\w\s]+),?\s*(?P<state>[A-Z]{2})?",
            re.IGNORECASE,
        )
        for m in energy_pattern.finditer(text):
            name = m.group("name").strip()
            if len(name) > 5 and not any(f["name"] == name for f in facilities):
                facilities.append(
                    {
                        "name": name,
                        "city": m.group("city").strip() if m.group("city") else "",
                        "state": m.group("state") or "",
                        "country": "USA",
                        "type": "Renewable Energy",
                        "reported_emissions_tons": None,
                    }
                )

        # Deduplicate
        seen = set()
        unique = []
        for f in facilities:
            key = f["name"].lower().strip()
            if key not in seen and len(key) > 3:
                seen.add(key)
                unique.append(f)

        return unique[:20]  # Cap at 20 facilities for demo

    @staticmethod
    def _extract_nearby_number(text: str, pos: int, window: int = 200) -> Optional[float]:
        """Look for a number near *pos* in *text*."""
        snippet = text[max(0, pos - window) : pos + window]
        nums = re.findall(r"[\d,]+\.?\d*", snippet)
        for n in reversed(nums):
            val = float(n.replace(",", ""))
            if val > 1000:
                return val
        return None

    @staticmethod
    def _demo_facilities() -> list[dict]:
        return [
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
        ]
