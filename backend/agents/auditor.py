from typing import List, Dict

class AuditorAgent:
    def __init__(self, tolerance: float = 0.20):
        self.tolerance = tolerance # 20% discrepancy threshold

    def calculate_veracity_score(self, reported_emissions: float, satellite_emissions: float) -> Dict:
        """
        Calculate the Veracity Score (V) and determine if there is a discrepancy.
        Formula: V = 100 - (|Sat - Reported| / Sat * 100)
        """
        if satellite_emissions == 0:
            return {"veracity_score": 0.0, "status": "Inconclusive", "discrepancy": 0.0}

        discrepancy = abs(satellite_emissions - reported_emissions) / satellite_emissions
        veracity_score = max(0.0, 100.0 - (discrepancy * 100))
        
        status = "Verified"
        if discrepancy > self.tolerance:
            status = "Discrepancy Detected"
        
        return {
            "veracity_score": round(veracity_score, 2),
            "status": status,
            "discrepancy_percentage": round(discrepancy * 100, 2),
            "reported": reported_emissions,
            "satellite": satellite_emissions
        }

    def generate_audit_report(self, facility_data: List[Dict]) -> Dict:
        """
        Summarize the audit results for a list of facilities.
        """
        audited_facilities = []
        total_veracity = 0.0
        
        for facility in facility_data:
            score_data = self.calculate_veracity_score(
                facility.get("reported_emissions", 0.0),
                facility.get("satellite_emissions", 0.0)
            )
            facility.update(score_data)
            audited_facilities.append(facility)
            total_veracity += score_data["veracity_score"]
        
        average_veracity = total_veracity / len(audited_facilities) if audited_facilities else 0.0
        
        return {
            "summary": {
                "overall_veracity": round(average_veracity, 2),
                "total_audited": len(audited_facilities),
                "discrepancies_flagged": len([f for f in audited_facilities if f["status"] == "Discrepancy Detected"])
            },
            "facilities": audited_facilities
        }

if __name__ == "__main__":
    # Test stub
    auditor = AuditorAgent()
    sample_data = [{
        "name": "GYR3 Fulfillment Center",
        "reported_emissions": 4500,
        "satellite_emissions": 5400
    }]
    print(auditor.generate_audit_report(sample_data))
