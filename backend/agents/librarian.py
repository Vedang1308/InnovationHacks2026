import os
import json
import requests
from typing import List, Dict
from phi.agent import Agent
from phi.model.ollama import Ollama
from .rag_processor import RAGProcessor
from .climate_auditor import ClimateAuditorAgent

class LibrarianAgent:
    def __init__(self, model_id: str = "llama3.2-vision", data_dir: str = "data/"):
        self.agent = Agent(
            model=Ollama(id=model_id),
            description="You are the TraceTrust Librarian. Your job is to extract facility names and locations from corporate sustainability reports.",
            instructions=[
                "Analyze the provided text carefully.",
                "Extract a list of facilities (fulfillment centers, data centers, manufacturing plants).",
                "For each, identify Name, Location (City/Country), and Reported Emissions (numeric value in tons).",
                "Only extract verifiable facility data. Do not hallucinate.",
                "STRICT REQUIREMENT: Your entire response must be a single JSON list of objects.",
                "NO MarkDown tables. NO explanations. NO conversational text.",
                "Example Format: [{'name': '...', 'location': '...', 'reported_emissions': 123.45}]"
            ],
            markdown=True
        )
        self.rag = RAGProcessor(data_dir=data_dir)
        self.auditor = ClimateAuditorAgent()

    def _check_ollama(self) -> bool:
        """Check if local Ollama server is responsive."""
        try:
            requests.get("http://localhost:11434/api/tags", timeout=2)
            return True
        except:
            return False

    def extract_facilities_from_pdf(self, pdf_path: str) -> List[Dict]:
        """
        Use RAG to find relevant sections and extract with LLM (with robust parsing).
        """
        if not self._check_ollama():
            print("❌ Librarian: Ollama server not found at localhost:11434. Aborting.")
            return []

        # 1. Ingest into FAISS (only if not already indexed)
        self.rag.ingest_report(pdf_path)
        
        # 2. Query for facility disclosures
        query = "Detailed list of physical facilities, manufacturing sites, data centers, fulfillment centers, locations, and their Scope 1 or Scope 2 CO2 emissions"
        chunks = self.rag.query_report(query, k=10)
        
        # 3. Combine context
        verified_context = ""
        for i, chunk in enumerate(chunks):
            text = chunk["content"]
            verified_context += f"\n--- Section {i} ---\n{text}"
        
        if not verified_context:
            return []

        # 4. Extract structured data with LLM
        response = self.agent.run(f"Extract facility data from these validated report sections:\n{verified_context}")
        
        try:
            content = response.content
            
            # 🛡️ ROBUST JSON EXTRACTION 🛡️
            # Handle cases where the model includes conversational text before/after JSON
            import re
            json_match = re.search(r'\[\s*{.*}\s*\]', content, re.DOTALL)
            if json_match:
                content = json_match.group(0)
            
            # Clean common markdown/formatting artifacts
            content = content.replace("```json", "").replace("```", "").strip()
            
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                # Fallback to ast.literal_eval for single-quoted Python-style lists
                import ast
                try:
                    return ast.literal_eval(content)
                except Exception as e2:
                    print(f"Librarian: Failed to decode LLM response. Raw: {content[:200]}")
                    return []
        except Exception as e:
            print(f"Error in Librarian Agent node: {e}")
            return []

if __name__ == "__main__":
    librarian = LibrarianAgent()
    # Sample path (if exists)
    # results = librarian.extract_facilities_from_pdf("data/amazon_2024_sustainability_report.pdf")
    # print(results)
