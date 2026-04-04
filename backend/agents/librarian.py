from phi.agent import Agent
from phi.model.ollama import Ollama
from .rag_processor import RAGProcessor
from .climate_auditor import ClimateAuditorAgent
import os
import json
from typing import List, Dict

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

    def extract_facilities_from_pdf(self, pdf_path: str) -> List[Dict]:
        """
        Use RAG to find relevant sections, validate with ClimateBERT, and extract with LLM.
        """
        # 1. Ingest into FAISS (only if not already indexed)
        self.rag.ingest_report(pdf_path)
        
        # 2. Query for facility disclosures
        query = "Detailed list of physical facilities, manufacturing sites, data centers, fulfillment centers, locations, and their Scope 1 or Scope 2 CO2 emissions"
        print(f"DEBUG: Librarian querying RAG with: {query}")
        chunks = self.rag.query_report(query, k=10)
        
        print(f"DEBUG: RAG found {len(chunks)} relevant chunks.")
        
        # 3. Combine context
        verified_context = ""
        for i, chunk in enumerate(chunks):
            text = chunk["content"]
            print(f"DEBUG: Chunk {i} snippet: {text[:200]}...")
            verified_context += f"\n--- Section {i} ---\n{text}"
        
        if not verified_context:
            print("DEBUG: Librarian found NO context from RAG.")
            return []

        # 4. Extract structured data with LLM
        response = self.agent.run(f"Extract facility data from these validated report sections:\n{verified_context}")
        
        try:
            content = response.content
            print(f"DEBUG: Librarian Agent Raw Response: {content}")
            
            # Extract JSON from potential markdown tags
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            # Final attempt to find any JSON-like list structure if parsing fails
            content = content.strip()
            if not content.startswith("["):
                # Look for the first '[' and last ']'
                start = content.find("[")
                end = content.rfind("]")
                if start != -1 and end != -1:
                    content = content[start:end+1]
            
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                # Fallback: model might have used single quotes (valid Python, not JSON)
                import ast
                try:
                    return ast.literal_eval(content)
                except Exception as e2:
                    print(f"Fallback parsing failed: {e2}")
                    raise e
        except Exception as e:
            print(f"Error parsing Librarian Agent response: {e}")
            print(f"Content that failed: {content}")
            return []

if __name__ == "__main__":
    # Test stub
    librarian = LibrarianAgent()
    # Sample path (if exists)
    # results = librarian.extract_facilities_from_pdf("data/amazon_2024_sustainability_report.pdf")
    # print(results)
