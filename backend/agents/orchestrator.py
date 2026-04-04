import asyncio
from typing import TypedDict, List, Dict, Any, Annotated, Callable, Optional
import operator
from langgraph.graph import StateGraph, END
from agents.librarian import LibrarianAgent
from agents.geospatial import GeospatialAgent
from agents.satellite import SatelliteAgent
from agents.auditor import AuditorAgent

# Define the state of the audit pipeline
class AuditState(TypedDict):
    project_id: str
    pdf_path: str
    company_name: str
    facilities: List[Dict[str, Any]]
    audit_results: List[Dict[str, Any]]
    logs: Annotated[List[str], operator.add]
    status: str
    error: str

class TraceTrustOrchestrator:
    def __init__(self, event_callback: Optional[Callable] = None):
        self.librarian = LibrarianAgent()
        self.geospatial = GeospatialAgent()
        self.satellite = SatelliteAgent()
        self.auditor = AuditorAgent()
        self.event_callback = event_callback
        self.workflow = self._build_graph()

    def _build_graph(self):
        graph = StateGraph(AuditState)

        # Define Nodes (LangGraph supports async nodes)
        graph.add_node("extract_claims", self._node_librarian)
        graph.add_node("geocode_locations", self._node_geospatial)
        graph.add_node("verify_evidence", self._node_satellite)
        graph.add_node("calculate_veracity", self._node_auditor)

        # Define Edges
        graph.set_entry_point("extract_claims")
        graph.add_edge("extract_claims", "geocode_locations")
        graph.add_edge("geocode_locations", "verify_evidence")
        graph.add_edge("verify_evidence", "calculate_veracity")
        graph.add_edge("calculate_veracity", END)

        return graph.compile()

    def _emit(self, agent: str, message: str, data: Any = None):
        """
        Helper to emit events for real-time monitoring.
        """
        if self.event_callback:
            # Check if event_callback is a coroutine OR a standard function
            if asyncio.iscoroutinefunction(self.event_callback):
                asyncio.create_task(self.event_callback(agent, message, data))
            else:
                try:
                    # In some async contexts, standard functions might be called from an event loop
                    self.event_callback(agent, message, data)
                except Exception as e:
                    print(f"Emission Error: {e}")

    async def _node_librarian(self, state: AuditState):
        self._emit("librarian", "Starting RAG extraction from ESG report...")
        try:
            # Librarian extraction is typically the slowest part and is usually done once per doc
            facilities = self.librarian.extract_facilities_from_pdf(state["pdf_path"])
            msg = f"Extracted {len(facilities)} facility claims."
            self._emit("librarian", msg, {"count": len(facilities)})
            return {
                "facilities": facilities,
                "logs": [f"Librarian Agent: {msg}"]
            }
        except Exception as e:
            self._emit("librarian", f"Error: {str(e)}")
            return {"error": str(e), "logs": [f"Librarian Agent Error: {e}"]}

    async def _node_geospatial(self, state: AuditState):
        self._emit("geospatial", "Mapping facilities to GPS coordinates (Parallel Mode)...")
        
        async def geocode_task(f):
            try:
                coords = self.geospatial.get_coordinates(f.get("location", ""))
                f["coordinates"] = coords
                self._emit("geospatial", f"Geocoded: {f.get('name')} -> {coords}", coords)
                return f
            except Exception as e:
                self._emit("geospatial", f"Failed to geocode {f.get('name')}: {e}")
                return f

        # Run all geocoding tasks in parallel
        tasks = [geocode_task(f) for f in state["facilities"]]
        updated_facilities = await asyncio.gather(*tasks)
        
        self._emit("geospatial", "Mapping complete.")
        return {
            "facilities": updated_facilities,
            "logs": ["Geospatial Agent: Parallel mapping complete."]
        }

    async def _node_satellite(self, state: AuditState):
        self._emit("satellite", "Acquiring real-world sensor data (Parallel S3/API Stream)...")
        
        async def verify_task(f):
            coords = f.get("coordinates", {})
            if not coords:
                return f
            
            lat, lon = coords.get("lat"), coords.get("lng")
            try:
                self._emit("satellite", f"Analyzing Sentinel-5P sensor feed for {f.get('name')}...")
                # Wrap sync methods in run_in_executor to avoid blocking the loop
                loop = asyncio.get_event_loop()
                sensor_data = await loop.run_in_executor(None, self.satellite.fetch_sentinel_5p_data, lat, lon)
                
                self._emit("satellite", f"Querying Climate TRACE for Ground Truth near {f.get('name')}...")
                api_data = await loop.run_in_executor(None, self.satellite.get_emissions_from_climate_trace, lat, lon)
                
                f["satellite_evidence"] = {
                    "sensor": sensor_data,
                    "ground_truth": api_data
                }
                return f
            except Exception as e:
                self._emit("satellite", f"Satellite verification failed for {f.get('name')}: {e}")
                return f

        tasks = [verify_task(f) for f in state["facilities"]]
        updated_facilities = await asyncio.gather(*tasks)
        
        self._emit("satellite", "Satellite evidence verification complete.")
        return {
            "facilities": updated_facilities,
            "logs": ["Satellite Agent: Data acquisition complete."]
        }

    async def _node_auditor(self, state: AuditState):
        self._emit("auditor", "Calculating final veracity scores and impact metrics...")
        
        async def audit_task(f):
            try:
                score_data = self.auditor.calculate_veracity_score(f)
                res = {
                    "name": f.get("name"),
                    "location": f.get("location"),
                    "reported": f.get("reported_emissions"),
                    "satellite_raw_sensor": f.get("satellite_evidence", {}).get("sensor", {}).get("value", 0.0),
                    "satellite_ground_truth": f.get("satellite_evidence", {}).get("ground_truth", [{}])[0].get("emissions_tco2e", 0.0),
                    "veracity_score": score_data.get("score"),
                    "status": score_data.get("status"),
                    "metrics": score_data.get("metrics")
                }
                self._emit("auditor", f"Verified {f.get('name')}: {score_data.get('score')}% Trust", res)
                return res
            except Exception as e:
                self._emit("auditor", f"Audit failed for {f.get('name')}: {e}")
                return None

        # Run all auditing tasks in parallel
        tasks = [audit_task(f) for f in state["facilities"]]
        results = await asyncio.gather(*tasks)
        
        # Filter out failed tasks
        valid_results = [r for r in results if r is not None]
        
        self._emit("orchestrator", "Audit session finalized. All evidence locked.")
        return {
            "audit_results": valid_results,
            "status": "completed",
            "logs": ["Auditor Agent: Audit finalized."]
        }

    async def run_audit(self, pdf_path: str, project_id: str):
        initial_state = {
            "project_id": project_id,
            "pdf_path": pdf_path,
            "company_name": "Audit Target",
            "facilities": [],
            "audit_results": [],
            "logs": ["Orchestrator: Initializing TraceTrust Graph..."],
            "status": "processing",
            "error": ""
        }
        return await self.workflow.ainvoke(initial_state)

if __name__ == "__main__":
    import asyncio
    orch = TraceTrustOrchestrator()
    print("Orchestrator Graph initialized with Parallel Async capability.")
