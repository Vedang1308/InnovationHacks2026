"""
TraceTrust — LangGraph Agent Orchestrator

Wraps the four agents (Librarian, Geospatial, Satellite, Auditor) in a
stateful LangGraph workflow graph with typed state management.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional, TypedDict

from langgraph.graph import StateGraph, END


# ---------------------------------------------------------------------------
# Graph State
# ---------------------------------------------------------------------------
class AuditState(TypedDict):
    """Typed state flowing through the LangGraph pipeline."""
    company_name: str
    pdf_path: Optional[str]
    facilities_input: Optional[list[dict]]
    facilities: list[dict]
    geocoded: list[dict]
    satellite_data: list[dict]
    results: Optional[dict]
    logs: list[dict]
    current_agent: str
    progress: int
    status: str
    error: Optional[str]


# ---------------------------------------------------------------------------
# Node functions (thin wrappers around existing agent logic)
# ---------------------------------------------------------------------------
def _log(state: AuditState, agent: str, msg: str) -> AuditState:
    state["logs"].append({
        "agent": agent,
        "message": msg,
        "timestamp": time.time(),
    })
    state["current_agent"] = agent
    return state


async def librarian_node(state: AuditState) -> AuditState:
    """Run the Librarian Agent to extract facilities from PDF or input."""
    from agents.librarian import LibrarianAgent

    state = _log(state, "librarian", "📚 Librarian Agent activated")
    state["progress"] = 10

    if state.get("facilities_input"):
        facilities = state["facilities_input"]
        state = _log(state, "librarian", f"   Using {len(facilities)} pre-supplied facilities")
    elif state.get("pdf_path"):
        state = _log(state, "librarian", f"   Parsing PDF: {state['pdf_path']}")
        agent = LibrarianAgent()
        facilities = await agent.extract_facilities(state["pdf_path"])
        state = _log(state, "librarian", f"   ✅ Extracted {len(facilities)} facilities from PDF")
    else:
        from main import DEMO_FACILITIES
        facilities = DEMO_FACILITIES
        state = _log(state, "librarian", "   Using demo facility dataset")

    for f in facilities:
        state = _log(
            state, "librarian",
            f"   📍 Found: {f['name']} — {f.get('city', 'N/A')}, {f.get('state', '')}"
        )

    state["facilities"] = facilities
    state["progress"] = 25
    return state


async def geospatial_node(state: AuditState) -> AuditState:
    """Run the Geospatial Agent to geocode all facilities."""
    from agents.geospatial import GeospatialAgent

    state = _log(state, "geospatial", "🌍 Geospatial Agent activated")
    state["progress"] = 30

    agent = GeospatialAgent()
    geocoded = await agent.geocode_facilities(
        state["facilities"],
        log_fn=lambda m: _log(state, "geospatial", m),
    )
    state["geocoded"] = geocoded
    state["progress"] = 45
    return state


async def satellite_node(state: AuditState) -> AuditState:
    """Run the Satellite Agent for dual-path verification."""
    from agents.satellite import SatelliteAgent

    state = _log(state, "satellite", "🛰️  Satellite Agent activated — querying Climate TRACE & ASDI")
    state["progress"] = 50

    agent = SatelliteAgent()
    satellite_data = await agent.fetch_emissions(
        state["geocoded"],
        log_fn=lambda m: _log(state, "satellite", m),
    )
    state["satellite_data"] = satellite_data
    state["progress"] = 75
    return state


async def auditor_node(state: AuditState) -> AuditState:
    """Run the Auditor Agent to score and generate the final report."""
    from agents.auditor import AuditorAgent

    state = _log(state, "auditor", "🔍 Auditor Agent activated — calculating Veracity Scores")
    state["progress"] = 80

    agent = AuditorAgent()
    results = agent.score(
        state["satellite_data"],
        log_fn=lambda m: _log(state, "auditor", m),
    )
    state["results"] = results
    state["progress"] = 100
    state["status"] = "completed"
    state = _log(state, "auditor", "✅ Audit complete!")
    return state


def error_handler(state: AuditState) -> AuditState:
    """Handle pipeline errors gracefully."""
    state["status"] = "error"
    state = _log(state, "system", f"❌ Pipeline error: {state.get('error', 'Unknown')}")
    return state


# ---------------------------------------------------------------------------
# Build the LangGraph
# ---------------------------------------------------------------------------
def build_audit_graph() -> StateGraph:
    """Construct and compile the TraceTrust audit pipeline graph.

    Graph topology:
        librarian → geospatial → satellite → auditor → END
    """
    builder = StateGraph(AuditState)

    # Add nodes
    builder.add_node("librarian", librarian_node)
    builder.add_node("geospatial", geospatial_node)
    builder.add_node("satellite", satellite_node)
    builder.add_node("auditor", auditor_node)

    # Add edges (linear pipeline)
    builder.set_entry_point("librarian")
    builder.add_edge("librarian", "geospatial")
    builder.add_edge("geospatial", "satellite")
    builder.add_edge("satellite", "auditor")
    builder.add_edge("auditor", END)

    return builder.compile()


def create_initial_state(
    company_name: str,
    pdf_path: Optional[str] = None,
    facilities: Optional[list[dict]] = None,
) -> AuditState:
    """Create the initial state dict for a new audit run."""
    return AuditState(
        company_name=company_name,
        pdf_path=pdf_path,
        facilities_input=facilities,
        facilities=[],
        geocoded=[],
        satellite_data=[],
        results=None,
        logs=[{
            "agent": "system",
            "message": f"🚀 TraceTrust Audit Pipeline initiated — Company: {company_name}",
            "timestamp": time.time(),
        }],
        current_agent="initializing",
        progress=0,
        status="running",
        error=None,
    )
