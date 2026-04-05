import argparse
import requests
import time
import json
import os

API_BASE = "http://localhost:8000"

def main():
    parser = argparse.ArgumentParser(description="Run TraceTrust Audit and export results to JSON.")
    parser.add_argument("--demo", action="store_true", help="Run the offline demo audit")
    parser.add_argument("--company", type=str, help="Run audit for a prebuilt company (e.g. amazon, bp, aps)")
    parser.add_argument("--pdf", type=str, help="Upload and audit a specific PDF file")
    parser.add_argument("--out", type=str, default="audit_results.json", help="Output JSON file name")
    args = parser.parse_args()

    audit_id = None
    
    if args.pdf:
        if not os.path.exists(args.pdf):
            print(f"Error: File '{args.pdf}' not found.")
            return
        print(f"Uploading PDF: {args.pdf}...")
        with open(args.pdf, "rb") as f:
            files = {"file": f}
            resp = requests.post(f"{API_BASE}/api/audit/upload", files=files)
            if resp.status_code != 200:
                print(f"API Error {resp.status_code}: {resp.text}")
                return
            audit_id = resp.json().get("audit_id")
            
    elif args.company:
        print(f"Starting audit for company: {args.company}...")
        resp = requests.post(f"{API_BASE}/api/audit/company/{args.company}")
        if resp.status_code != 200:
            print(f"API Error {resp.status_code}: {resp.text}")
            return
        audit_id = resp.json().get("audit_id")
        
    elif args.demo:
        print("Starting Demo audit...")
        resp = requests.post(f"{API_BASE}/api/audit/demo")
        if resp.status_code != 200:
            print(f"API Error {resp.status_code}: {resp.text}")
            return
        audit_id = resp.json().get("audit_id")
        
    else:
        print("Please specify a target: --demo, --company [name], or --pdf [path]")
        return

    if not audit_id:
        print("Failed to get audit ID.")
        return
        
    print(f"Audit started! ID: {audit_id}")
    print("Polling for completion...")
    
    while True:
        try:
            resp = requests.get(f"{API_BASE}/api/audit/{audit_id}")
            data = resp.json()
        except requests.exceptions.ConnectionError:
            print("Connection error. Ensure the backend FastAPI server is running.")
            return
            
        status = data.get("status")
        progress = data.get("progress", 0)
        print(f"   Progress: {progress}% - Audit Status: {status}")
        
        if status == "completed":
            results = data.get("results")
            with open(args.out, "w") as f:
                json.dump(results, f, indent=4)
            print(f"\n✅ Audit complete! Results successfully saved to {args.out}")
            break
        elif status == "error":
            print("\n❌ Pipeline error occurred.")
            print("Check backend terminal logs for more details.")
            break
            
        time.sleep(2)

if __name__ == "__main__":
    main()
