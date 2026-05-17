"""
Agent 3 — Communication Agent
================================
Responsibilities (accept path only):
  - Sends a personalized acceptance email via the Gmail tool
  - Schedules a technical interview via the Google Calendar tool
  - Both tools are called dynamically by the LLM based on reasoning

Uses LangChain + LangGraph create_react_agent — swap models in .env.
Runs in PARALLEL with the Preparation Pack Agent after the Orchestrator routes accept.
"""
from datetime import date, timedelta
from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage
from langgraph.prebuilt import create_react_agent
from config import get_llm, MODEL, LLM_PROVIDER, ROLES, COMPANY_NAME
from logger import get_logger
from state import RecruitmentState
from tools.gmail_tool import send_email
from tools.calendar_tool import create_calendar_event

logger = get_logger(__name__)


SYSTEM_PROMPT = f"""You are a professional recruitment coordinator at {COMPANY_NAME}.
Your job is to handle all communications with accepted candidates.

You have two tools available:
1. send_email — sends a personalized acceptance email to the candidate
2. create_calendar_event — schedules a technical interview on Google Calendar

WORKFLOW:
Step 1: Call send_email with a warm, personalized acceptance email. The email should:
  - Congratulate the candidate specifically (reference their score or a strength)
  - Explain the next steps clearly
  - Mention that an interview invitation will follow shortly
  - Use professional but human tone (not corporate/stiff)
  - Sign off as "{COMPANY_NAME} Recruiting Team"

Step 2: Call create_calendar_event to schedule the interview:
  - Schedule for business hours (9 AM – 5 PM EST), next business day at 10:00 AM
  - Duration: 60 minutes
  - Include a helpful description about what to expect

Always call BOTH tools. Do not skip either one."""


def run_communication_agent(state: RecruitmentState) -> dict:
    """
    Communication Agent node for LangGraph.
    Sends acceptance email and schedules interview calendar event.
    """
    gap_analysis = state.get("gap_analysis", {})
    candidate_email = state["candidate_email"]
    candidate_name = state["candidate_name"]
    role = state["role"]
    role_display = ROLES.get(role, role)
    score = gap_analysis.get("score", 0)
    strengths = gap_analysis.get("strengths", [])
    recruiter_notes = state.get("recruiter_notes", "")

    logger.info("Preparing acceptance communication for %s via %s/%s...", candidate_name, LLM_PROVIDER, MODEL)

    # Compute next business day from today to guarantee a future date
    interview_date = date.today() + timedelta(days=1)
    while interview_date.weekday() >= 5:   # skip Saturday(5) and Sunday(6)
        interview_date += timedelta(days=1)
    interview_iso = f"{interview_date.isoformat()}T10:00:00"

    user_message = f"""
Please send an acceptance email and schedule an interview for the following candidate:

Candidate Name: {candidate_name}
Candidate Email: {candidate_email}
Role: {role_display}
Interview Score: {score}/100
Key Strengths: {', '.join(strengths[:3]) if strengths else 'strong technical background'}
Recruiter Notes: {recruiter_notes or 'N/A'}

Step 1: Call send_email with a warm acceptance email.
Step 2: Call create_calendar_event using this exact datetime: {interview_iso}
        (candidate_name="{candidate_name}", role="{role_display}", candidate_email="{candidate_email}")
You MUST call both tools.
""".strip()

    llm = get_llm()
    agent = create_react_agent(llm, tools=[send_email, create_calendar_event])

    result = agent.invoke({
        "messages": [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=user_message),
        ]
    })

    acceptance_email_sent = False
    calendar_event_created = False
    calendar_event_link = None
    errors = list(state.get("errors", []))

    for msg in result["messages"]:
        if isinstance(msg, ToolMessage):
            content = msg.content
            lower = content.lower()
            logger.debug("Tool result [%s]: %s", msg.name, content[:200])
            if "successfully sent" in lower:
                acceptance_email_sent = True
            if "interview scheduled successfully" in lower:
                calendar_event_created = True
                for line in content.split("\n"):
                    if "Calendar link:" in line:
                        calendar_event_link = line.split("Calendar link:")[-1].strip()
            if "not sent" in lower or ("calendar event not created" in lower):
                logger.error("Tool error [%s]: %s", msg.name, content)
                errors.append(content)

    logger.info("Done. Email sent: %s | Calendar created: %s", acceptance_email_sent, calendar_event_created)

    return {
        "acceptance_email_sent": acceptance_email_sent,
        "calendar_event_created": calendar_event_created,
        "calendar_event_link": calendar_event_link,
        "errors": errors,
    }
