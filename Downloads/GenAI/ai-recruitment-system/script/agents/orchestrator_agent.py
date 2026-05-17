"""
Agent 2 — Orchestrator Agent
==============================
Responsibilities:
  - Receives the gap analysis from the Review Agent AND the recruiter's accept/reject decision
  - Reasons about which downstream agents to invoke
  - Routes to the accept path (Communication + Preparation Pack agents, running in parallel)
    or the reject path (Rejection Agent)

This is the central routing intelligence of the pipeline. It does NOT execute downstream
tasks itself — it decides and delegates.
"""
from logger import get_logger
from state import RecruitmentState

logger = get_logger(__name__)


def run_orchestrator_agent(state: RecruitmentState) -> dict:
    """
    Orchestrator Agent node for LangGraph.

    Reads the recruiter_decision and gap_analysis, logs the routing decision,
    and returns state unchanged (routing is handled by the conditional edge).
    """
    decision = state.get("recruiter_decision", "reject")
    gap = state.get("gap_analysis", {})
    role = state.get("role", "unknown")
    candidate_name = state.get("candidate_name", "Candidate")
    score = gap.get("score", 0)
    deciding_factor = gap.get("deciding_factor", "N/A")

    logger.info(
        "Candidate: %s | Role: %s | Score: %s/100 | Decision: %s",
        candidate_name, role, score, decision.upper(),
    )
    logger.info("Deciding factor: %s", deciding_factor)

    if decision == "accept":
        logger.info("Routing → Communication Agent + Preparation Pack Agent (parallel)")
    else:
        logger.info("Routing → Rejection Agent")

    return {}


def route_from_orchestrator(state: RecruitmentState) -> list | str:
    """
    Conditional edge function: determines which agent(s) to invoke next.

    On the accept path, returns a list of Send() calls to fan out in parallel
    to the Communication Agent and Preparation Pack Agent.
    On the reject path, routes to the Rejection Agent.
    """
    from langgraph.types import Send

    decision = state.get("recruiter_decision", "reject")

    if decision == "accept":
        return [
            Send("communication_agent", state),
            Send("preparation_pack_agent", state),
        ]
    else:
        return "rejection_agent"
