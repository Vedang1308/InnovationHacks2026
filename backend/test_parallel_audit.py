import asyncio
import os
import sys
from datetime import datetime

# Add the current directory to sys.path for absolute imports
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from agents.orchestrator import TraceTrustOrchestrator

async def mock_event_callback(agent, message, data=None):
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] [{agent.upper()}] {message}")
    if data and "veracity_score" in str(data):
        print(f"      -> Veracity Result: {data.get('veracity_score')}% ({data.get('status')})")

async def test_parallel_audit():
    print("🚀 Initializing TraceTrust 3.1 Parallel Audit Verification...")
    
    # Initialize Orchestrator with our mock callback
    orch = TraceTrustOrchestrator(event_callback=mock_event_callback)
    
    # We'll use the sample PDF but mock the Librarian response if needed
    # (Optional: If Ollama isn't running, we might need a fallback test)
    
    pdf_path = "data/amazon_2024_sustainability_report.pdf"
    if not os.path.exists(pdf_path):
        print(f"❌ Error: {pdf_path} not found. Please ensure the sample report exists.")
        return

    print(f"📂 Starting audit for {pdf_path}...")
    start_time = asyncio.get_event_loop().time()
    
    # run_audit is now async
    result = await orch.run_audit(pdf_path, "test_project_parallel")
    
    end_time = asyncio.get_event_loop().time()
    duration = end_time - start_time
    
    print("\n" + "="*50)
    print(f"✅ Audit Complete in {duration:.2f} seconds.")
    print(f"📊 Overall Veracity Score: {result.get('overall_veracity', 0)}%")
    print(f"🌍 Total Social Cost of Discrepancies: ${result.get('total_social_cost_impact', 0)}")
    print("="*50)

if __name__ == "__main__":
    try:
        asyncio.run(test_parallel_audit())
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"❌ Verification failed: {e}")
