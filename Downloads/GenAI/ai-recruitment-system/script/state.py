"""
LangGraph State definition for the AI Recruitment Pipeline.
Shared across all agents in the graph.
"""
import operator
from typing import Annotated, Optional
from typing_extensions import TypedDict
from langgraph.graph.message import add_messages


class GapAnalysis(TypedDict):
    """Structured output produced by the Review Agent."""
    strengths: list[str]
    skill_gaps: list[str]
    score: int                       # 0–100
    recommendation: str              # "accept" or "reject"
    deciding_factor: str             # Primary reason for the recommendation
    feedback_summary: str            # Human-readable summary
    experience_level: str            # "junior" | "mid" | "senior"


class RecruitmentState(TypedDict):
    # ── Inputs ────────────────────────────────────────────────────
    resume_text: str
    job_description: str
    candidate_email: str
    candidate_name: str
    role: str                        # "ai_ml_engineer" | "backend_engineer" | "frontend_engineer"

    # ── Review Agent Output ────────────────────────────────────────
    gap_analysis: Optional[GapAnalysis]
    rag_context: Optional[str]       # Retrieved context injected into Review Agent

    # ── Recruiter Decision (human-in-the-loop) ────────────────────
    recruiter_decision: Optional[str]   # "accept" | "reject"
    recruiter_notes: Optional[str]      # Optional reasoning from recruiter

    # ── Downstream Results ─────────────────────────────────────────
    acceptance_email_sent: bool
    rejection_email_sent: bool
    calendar_event_created: bool
    calendar_event_link: Optional[str]
    interview_questions_path: Optional[str]

    # ── Error Tracking ─────────────────────────────────────────────
    # Annotated with operator.add so parallel agents can each append errors
    # without conflicting — LangGraph merges the lists automatically.
    errors: Annotated[list[str], operator.add]

    # ── Agent Messages (LangGraph message passing) ────────────────
    messages: Annotated[list, add_messages]
