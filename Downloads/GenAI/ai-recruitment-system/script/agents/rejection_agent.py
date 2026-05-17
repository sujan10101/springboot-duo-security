"""
Agent 5 — Rejection Agent
===========================
Responsibilities (reject path only):
  - Reads the gap analysis from the Review Agent
  - Writes a specific, honest rejection email explaining the ACTUAL deciding factor
  - Sends the email via the Gmail tool

Uses LangChain + LangGraph create_react_agent — swap models in .env.
"""
from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage
from langgraph.prebuilt import create_react_agent
from config import get_llm, MODEL, LLM_PROVIDER, ROLES, COMPANY_NAME
from logger import get_logger
from state import RecruitmentState
from tools.gmail_tool import send_email

logger = get_logger(__name__)


SYSTEM_PROMPT = f"""You are a thoughtful, human recruiter at {COMPANY_NAME} writing rejection emails.

Your CORE RESPONSIBILITY: Write rejection emails that are SPECIFIC and HONEST.
- NEVER write a generic "we've decided to move forward with other candidates" message
- ALWAYS cite the actual deciding factor from the gap analysis
- ALWAYS name the specific skill gaps that led to the decision
- ALWAYS provide concrete, actionable learning recommendations

TONE GUIDELINES:
- Write like a human being, not a corporate bot
- Be direct but kind — rejection stings, but vague rejection stings MORE
- Use clear, simple language (no HR jargon)
- Acknowledge what the candidate did well before explaining the gap
- End with genuine encouragement and specific next steps
- Sign off: "best,\\nthe {COMPANY_NAME} recruiting team"

EMAIL STRUCTURE:
1. Brief acknowledgment (1-2 sentences)
2. What genuinely impressed us (specific strengths from the gap analysis)
3. The deciding factor — be SPECIFIC (name exactly what was missing)
4. Concrete recommendations (2-3 specific resources or actions)
5. Encouragement to reapply when the gap is addressed

EXAMPLE of good vs bad:
BAD: "After careful consideration, we have decided to move forward with other candidates."
GOOD: "The deciding factor was the gap in LLM fine-tuning experience. The role requires
       hands-on LoRA/QLoRA experience, and your profile shows strong LLM API usage
       but no fine-tuning work yet."

Call send_email once the email is composed."""


def run_rejection_agent(state: RecruitmentState) -> dict:
    """
    Rejection Agent node for LangGraph.
    Composes and sends a specific, feedback-rich rejection email.
    """
    gap_analysis = state.get("gap_analysis", {})
    candidate_name = state["candidate_name"]
    candidate_email = state["candidate_email"]
    role = state["role"]
    role_display = ROLES.get(role, role)
    recruiter_notes = state.get("recruiter_notes", "")

    strengths = gap_analysis.get("strengths", [])
    skill_gaps = gap_analysis.get("skill_gaps", [])
    score = gap_analysis.get("score", 0)
    deciding_factor = gap_analysis.get("deciding_factor", "Insufficient match with role requirements")
    feedback_summary = gap_analysis.get("feedback_summary", "")
    experience_level = gap_analysis.get("experience_level", "unknown")

    logger.info("Composing rejection email for %s via %s/%s...", candidate_name, LLM_PROVIDER, MODEL)

    user_message = f"""
Write and send a specific, honest rejection email to the following candidate:

Candidate Name: {candidate_name}
Candidate Email: {candidate_email}
Role Applied For: {role_display}
Interview Score: {score}/100
Experience Level: {experience_level}

Genuine Strengths (acknowledge these):
{chr(10).join(f"• {s}" for s in strengths)}

Specific Skill Gaps (cite these as the reason):
{chr(10).join(f"• {g}" for g in skill_gaps)}

PRIMARY Deciding Factor (the main reason for rejection — be specific about this):
{deciding_factor}

Overall Assessment: {feedback_summary}

Recruiter Notes: {recruiter_notes or 'None'}

Write a compassionate but honest rejection email that explains the ACTUAL reason,
acknowledges what the candidate did well, and gives specific improvement steps.
Then call send_email to send it.
""".strip()

    llm = get_llm()
    agent = create_react_agent(llm, tools=[send_email])

    result = agent.invoke({
        "messages": [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=user_message),
        ]
    })

    rejection_email_sent = False
    errors = list(state.get("errors", []))

    for msg in result["messages"]:
        if isinstance(msg, ToolMessage):
            if "successfully sent" in msg.content.lower():
                rejection_email_sent = True
            elif "not sent" in msg.content.lower() or "error" in msg.content.lower():
                errors.append(msg.content)

    logger.info("Done. Rejection email sent: %s", rejection_email_sent)

    return {
        "rejection_email_sent": rejection_email_sent,
        "errors": errors,
    }
