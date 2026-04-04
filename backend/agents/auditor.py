from typing import List, Dict, Any

class AuditorAgent:
    def __init__(self, tolerance: float = 0.20, scc_per_ton: float = 51.0):
        self.tolerance = tolerance # 20% discrepancy threshold
        self.scc_per_ton = scc_per_ton # Social Cost of Carbon (USD)
        self.no2_baseline = 0.0001 # Standard background NO2 concentration (mol/m^2)

    def calculate_veracity_score(self, facility: Dict[str, Any]) -> Dict:
        """
        Calculate the Veracity Score (V) using a hybrid sensor-mass model.
        """
        reported = facility.get("reported_emissions", 0.0)
        evidence = facility.get("satellite_evidence", {})
        sensor_val = evidence.get("sensor", {}).get("value", 0.0)
        
        # Ground Truth from Climate TRACE
        gt_list = evidence.get("ground_truth", [])
        api_val = gt_list[0].get("emissions_tco2e", 0.0) if gt_list else 0.0
        
        # 🧪 HYBRID VERACITY LOGIC 🧪
        # 1. Primary Baseline: Climate TRACE (Scientific Gold Standard)
        # 2. Secondary Baseline: Raw Sensor Proxy (Atmospheric Integrity)
        
        observed = api_val
        is_proxy = False
        
        if observed == 0:
            # Fallback: If no database record, but high NO2 plume detected (> 2x baseline)
            if sensor_val > self.no2_baseline * 2:
                # Approximate emissions based on NO2 concentration proxy (Heuristic for Demo)
                # In a real model, this would be a complex inversion (Hestia/ODIAC style)
                observed = (sensor_val / self.no2_baseline) * 500 
                is_proxy = True
            else:
                return {"score": 0.0, "status": "Inconclusive: No Evidence", "metrics": {}}

        # Calculate Discrepancy
        discrepancy_ratio = abs(observed - reported) / max(observed, 1.0)
        
        # Sensor Correlation Check (Does the plume match the reported change?)
        # If report says "Reduced by 50%" but sensor shows NO2 > Baseline, we penalize trust.
        sensor_penalty = 0.0
        if sensor_val > self.no2_baseline * 1.5 and reported < 100:
            sensor_penalty = 15.0 # 15% Trust deduction for unexplained atmospheric plumes
            
        score = max(0.0, 100.0 - (discrepancy_ratio * 100) - sensor_penalty)
        
        status = "Verified"
        if discrepancy_ratio > self.tolerance or sensor_penalty > 0:
            status = "Flagged: Veracity Warning"
            if is_proxy: status += " (Sensor Proxy)"
        
        # Environmental Impact Calculation
        excess_emissions = max(0.0, observed - reported)
        scc_impact = excess_emissions * self.scc_per_ton
        
        # Metric: Reforestation offset (1 tree ~22kg/year)
        trees_needed = (excess_emissions * 1000) / 22
        
        return {
            "score": round(score, 2),
            "status": status,
            "metrics": {
                "discrepancy_pct": round(discrepancy_ratio * 100, 2),
                "social_cost_usd": round(scc_impact, 2),
                "reforestation_offset_trees": round(trees_needed, 0),
                "is_proxy_calculation": is_proxy,
                "atmospheric_plume_detected": sensor_val > self.no2_baseline * 1.5
            }
        }

    def generate_audit_report(self, facility_results: List[Dict]) -> Dict:
        """
        Synthesize individual facility checks into a corporate-level audit.
        """
        total_score = 0.0
        total_scc = 0.0
        
        valid_facilities = [f for f in facility_results if f.get("veracity_score", 0.0) > 0]
        
        for f in valid_facilities:
            total_score += f.get("veracity_score", 0.0)
            total_scc += f.get("metrics", {}).get("social_cost_usd", 0.0)
            
        avg_score = total_score / len(valid_facilities) if valid_facilities else 0.0
        
        return {
            "overall_veracity": round(avg_score, 2),
            "total_social_cost_impact": round(total_scc, 2),
            "facilities": facility_results,
            "recommendation": "Urgent Review" if avg_score < 70 else "Standard Compliance"
        }

if __name__ == "__main__":
    auditor = AuditorAgent()
    # Test case: Missing Climate TRACE but high NO2 plume detected
    sample = {
        "name": "Unnamed Power Plant",
        "reported_emissions": 50,
        "satellite_evidence": {
            "sensor": {"value": 0.00055}, # 5.5x baseline
            "ground_truth": [] # Empty registry
        }
    }
    print(f"Sensor-Proxy Audit: {auditor.calculate_veracity_score(sample)}")
