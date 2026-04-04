import requests
import os
from dotenv import load_dotenv
from typing import Dict, List, Optional

load_dotenv()

class ClimateAuditorAgent:
    def __init__(self, token: str = os.getenv("HF_TOKEN"), model_id: str = "climatebert/distilroberta-base-climate-detector"):
        self.api_url = f"https://api-inference.huggingface.co/models/{model_id}"
        self.headers = {"Authorization": f"Bearer {token}"}

    def query_model(self, payload: Dict) -> List:
        """
        Query the Hugging Face Inference API.
        """
        try:
            response = requests.post(self.api_url, headers=self.headers, json=payload)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Error querying ClimateBERT: {e}")
            return []

    def validate_climate_disclosure(self, text: str) -> Dict:
        """
        Determine if the text contains a relevant climate disclosure.
        """
        output = self.query_model({"inputs": text})
        
        # Output format: [[{'label': 'LABEL_X', 'score': 0.99}, ...]]
        if output and isinstance(output, list) and isinstance(output[0], list):
            top_prediction = sorted(output[0], key=lambda x: x['score'], reverse=True)[0]
            return {
                "is_climate_relevant": top_prediction["label"] == "yes", # Assuming 'yes'/'no' labels
                "confidence": round(top_prediction["score"], 4),
                "original_label": top_prediction["label"]
            }
        
        return {"is_climate_relevant": False, "confidence": 0.0}

if __name__ == "__main__":
    # Test stub
    auditor = ClimateAuditorAgent()
    sample_text = "The facility in Goodyear, Arizona emitted 4,500 tons of CO2 in 2023."
    print(auditor.validate_climate_disclosure(sample_text))
