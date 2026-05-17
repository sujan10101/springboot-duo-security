"""
LangGraph Recruitment Pipeline Graph
=======================================
Architecture: Hierarchical Multi-Agent (non-serial)

Nodes:
  1. review_agent          — RAG-grounded resume scoring → GapAnalysis
  2. orchestrator_agent    — Routes based on recruiter decision (accept/reject)
  3. communication_agent   — [ACCEPT PATH] Sends email + schedules calendar (parallel)
  4. preparation_pack_agent— [ACCEPT PATH] Generates interview questions + saves file (parallel)
  5. rejection_agent       — [REJECT PATH] Sends specific, feedback-rich rejection email

Flow:
  START → review_agent → [human decision] → orchestrator_agent
    ├── accept → communication_agent ─┐
    │            preparation_pack_agent ─┤→ END
    └── reject → rejection_agent ──────┘
"""
from langgraph.graph import StateGraph, START, END

from state import RecruitmentState
from agents.review_agent import run_review_agent
from agents.orchestrator_agent import run_orchestrator_agent, route_from_orchestrator
from agents.communication_agent import run_communication_agent
from agents.preparation_pack_agent import run_preparation_pack_agent
from agents.rejection_agent import run_rejection_agent


def build_graph() -> StateGraph:
    """Construct and compile the recruitment pipeline graph."""
    builder = StateGraph(RecruitmentState)

    builder.add_node("review_agent", run_review_agent)
    builder.add_node("orchestrator_agent", run_orchestrator_agent)
    builder.add_node("communication_agent", run_communication_agent)
    builder.add_node("preparation_pack_agent", run_preparation_pack_agent)
    builder.add_node("rejection_agent", run_rejection_agent)

    builder.add_edge(START, "review_agent")
    builder.add_edge("review_agent", END)

    return builder.compile()


def build_downstream_graph() -> StateGraph:
    """
    Build the downstream graph that runs AFTER the recruiter makes their decision.
    This graph starts at the orchestrator and fans out to the accept or reject path.
    """
    builder = StateGraph(RecruitmentState)

    builder.add_node("orchestrator_agent", run_orchestrator_agent)
    builder.add_node("communication_agent", run_communication_agent)
    builder.add_node("preparation_pack_agent", run_preparation_pack_agent)
    builder.add_node("rejection_agent", run_rejection_agent)

    builder.add_edge(START, "orchestrator_agent")

    builder.add_conditional_edges(
        "orchestrator_agent",
        route_from_orchestrator,
        {
            "communication_agent": "communication_agent",
            "preparation_pack_agent": "preparation_pack_agent",
            "rejection_agent": "rejection_agent",
        }
    )

    builder.add_edge("communication_agent", END)
    builder.add_edge("preparation_pack_agent", END)
    builder.add_edge("rejection_agent", END)

    return builder.compile()


_review_graph = None
_downstream_graph = None


def get_review_graph():
    """Get (or build) the review-only graph."""
    global _review_graph
    if _review_graph is None:
        _review_graph = build_graph()
    return _review_graph


def get_downstream_graph():
    """Get (or build) the downstream graph (orchestrator + accept/reject paths)."""
    global _downstream_graph
    if _downstream_graph is None:
        _downstream_graph = build_downstream_graph()
    return _downstream_graph


def run_review_phase(
    resume_text: str,
    job_description: str,
    candidate_email: str,
    candidate_name: str,
    role: str,
) -> RecruitmentState:
    """
    Phase 1: Run the Review Agent to produce a gap analysis.
    Returns the state after the Review Agent completes.
    """
    initial_state: RecruitmentState = {
        "resume_text": resume_text,
        "job_description": job_description,
        "candidate_email": candidate_email,
        "candidate_name": candidate_name,
        "role": role,
        "gap_analysis": None,
        "rag_context": None,
        "recruiter_decision": None,
        "recruiter_notes": None,
        "acceptance_email_sent": False,
        "rejection_email_sent": False,
        "calendar_event_created": False,
        "calendar_event_link": None,
        "interview_questions_path": None,
        "errors": [],
        "messages": [],
    }

    graph = get_review_graph()
    result = graph.invoke(initial_state)
    return result


def run_downstream_phase(
    state: RecruitmentState,
    recruiter_decision: str,
    recruiter_notes: str = "",
) -> RecruitmentState:
    """
    Phase 2: Run the orchestrator and downstream agents (Communication + Prep Pack OR Rejection).

    Args:
        state: The state produced by the Review Agent (Phase 1).
        recruiter_decision: "accept" or "reject"
        recruiter_notes: Optional notes from the recruiter.

    Returns:
        Final state after all downstream agents complete.
    """
    updated_state = dict(state)
    updated_state["recruiter_decision"] = recruiter_decision
    updated_state["recruiter_notes"] = recruiter_notes

    graph = get_downstream_graph()
    result = graph.invoke(updated_state)
    return result
