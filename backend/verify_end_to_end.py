import requests
import time
import json
import os

BASE_URL = "http://localhost:8000"
SAMPLE_PDF = "data/amazon_2024_sustainability_report.pdf"

def run_verification():
    print("--- TraceTrust: End-to-End Verification ---")
    
    # 1. Check health
    try:
        requests.get(f"{BASE_URL}/")
    except:
        print("Backend is not running. Please start it with 'python3 main.py'")
        return

    # 2. Upload and initiate audit
    print(f"Submitting audit for: {SAMPLE_PDF}")
    with open(SAMPLE_PDF, "rb") as f:
        response = requests.post(f"{BASE_URL}/audit/upload", files={"file": f})
    
    if response.status_code != 200:
        print(f"Failed to initiate audit: {response.text}")
        return
    
    audit_id = response.json()["audit_id"]
    print(f"Audit ID: {audit_id} - Processing...")

    # 3. Poll for results
    while True:
        status_res = requests.get(f"{BASE_URL}/audit/{audit_id}")
        data = status_res.json()
        
        status = data.get("status")
        logs = data.get("logs", [])
        
        # Print only new logs
        if logs:
            last_log = logs[-1]
            print(f"[LOG] {last_log}")

        if status in ["Complete", "Failed"]:
            print(f"\n--- Audit {status} ---")
            if status == "Complete":
                print(json.dumps(data.get("results"), indent=4))
            break
        
        time.sleep(5)

if __name__ == "__main__":
    if not os.path.exists(SAMPLE_PDF):
        print(f"Sample PDF {SAMPLE_PDF} not found. Please ensure it was downloaded.")
    else:
        run_verification()
