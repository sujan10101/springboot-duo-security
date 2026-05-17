"""
Agent 4 — Preparation Pack Agent
===================================
Responsibilities (accept path only, runs in PARALLEL with Communication Agent):
  - Generates a tailored interview question set for the hiring manager
  - Questions are focused on gap areas and probing claimed strengths
  - Saves the prep pack to a Markdown file using the File I/O tool

Uses LangChain + LangGraph create_react_agent — swap models in .env.
"""
from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage, AIMessage
from langgraph.prebuilt import create_react_agent
from config import get_llm, MODEL, LLM_PROVIDER, ROLES, COMPANY_NAME
from logger import get_logger
from state import RecruitmentState
from tools.file_io_tool import write_interview_prep_pack

logger = get_logger(__name__)


def _extract_ai_text(messages: list) -> str:
    """Return the last non-empty AI message content from an agent result."""
    for msg in reversed(messages):
        if isinstance(msg, AIMessage) and msg.content:
            return msg.content if isinstance(msg.content, str) else str(msg.content)
    return ""


SYSTEM_PROMPT = f"""You are a senior technical interview designer at {COMPANY_NAME}.
Your role is to generate tailored interview question sets for the hiring manager
based on a specific candidate's profile — their strengths, skill gaps, and experience level.

QUESTION DESIGN PRINCIPLES:
1. Gap-targeted questions: Generate probing questions for each identified skill gap to verify
   actual depth (not just surface knowledge) — these are the most important questions
2. Strength-verification questions: Questions to confirm the strengths are genuine, not overstated
3. Role-critical questions: Questions that must be asked for this role regardless of candidate profile
4. Behavioral questions: At least 2 that reveal problem-solving approach and learning mindset
5. Each question should include: the question itself, what a STRONG answer looks like, and what a WEAK answer looks like

FORMAT YOUR OUTPUT IN MARKDOWN:
# Technical Interview Questions — [Candidate Name] — [Role]

## ⚠️ Gap-Verification Questions (PRIORITY — ask these first)
[Questions targeting identified skill gaps]

## ✅ Strength-Verification Questions
[Questions to probe claimed strengths]

## 🔑 Role-Critical Questions
[Must-ask questions for this role]

## 🧠 Behavioral & Problem-Solving
[Questions revealing thinking process and growth mindset]

## 💡 Evaluation Guide
[Brief notes on red flags to watch for during this specific interview]

Generate 12–16 questions total. Be specific to the candidate's actual profile.
After generating the questions, call write_interview_prep_pack to save the prep pack."""


def run_preparation_pack_agent(state: RecruitmentState) -> dict:
    """
    Preparation Pack Agent node for LangGraph.
    Generates tailored interview questions and saves to file.
    """
    gap_analysis = state.get("gap_analysis", {})
    candidate_name = state["candidate_name"]
    candidate_email = state["candidate_email"]
    role = state["role"]
    role_display = ROLES.get(role, role)

    strengths = gap_analysis.get("strengths", [])
    skill_gaps = gap_analysis.get("skill_gaps", [])
    score = gap_analysis.get("score", 0)
    experience_level = gap_analysis.get("experience_level", "mid")
    feedback_summary = gap_analysis.get("feedback_summary", "")
    deciding_factor = gap_analysis.get("deciding_factor", "")

    logger.info("Generating interview questions for %s via %s/%s...", candidate_name, LLM_PROVIDER, MODEL)

    gap_analysis_summary = (
        f"Score: {score}/100 | Experience Level: {experience_level}\n"
        f"Key Strengths: {', '.join(strengths)}\n"
        f"Skill Gaps: {', '.join(skill_gaps)}\n"
        f"Summary: {feedback_summary}\n"
        f"Deciding Factor for Acceptance: {deciding_factor}"
    )

    user_message = f"""
Generate a tailored interview preparation pack for the following candidate:

Candidate Name: {candidate_name}
Candidate Email: {candidate_email}
Role: {role_display}
Experience Level: {experience_level}
Interview Score: {score}/100

Key Strengths Identified:
{chr(10).join(f"• {s}" for s in strengths)}

Skill Gaps Identified (these need the deepest probing):
{chr(10).join(f"• {g}" for g in skill_gaps)}

Overall Assessment: {feedback_summary}

Generate 12–16 questions following the format in your instructions.
After generating the questions, call write_interview_prep_pack to save the prep pack.
""".strip()

    llm = get_llm()
    agent = create_react_agent(llm, tools=[write_interview_prep_pack])

    result = agent.invoke({
        "messages": [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=user_message),
        ]
    })

    interview_questions_path = None
    errors = list(state.get("errors", []))

    for msg in result["messages"]:
        if isinstance(msg, ToolMessage):
            content = msg.content
            lower = content.lower()
            logger.debug("Tool result [%s]: %s", msg.name, content[:200])
            if "saved to:" in lower:
                after = content.split("saved to:")[-1]
                interview_questions_path = after.split("\n")[0].strip()
                logger.info("Prep pack file: %s", interview_questions_path)
            if "failed" in lower or ("error" in lower and "saved to:" not in lower):
                logger.error("Tool error [%s]: %s", msg.name, content)
                errors.append(content)

    # Fallback: if LLM generated questions but skipped the tool call, save directly
    if interview_questions_path is None:
        logger.warning("LLM did not call write_interview_prep_pack — saving generated content directly.")
        generated_text = _extract_ai_text(result["messages"])
        if generated_text:
            tool_result = write_interview_prep_pack.invoke({
                "candidate_name": candidate_name,
                "role": role_display,
                "candidate_email": candidate_email,
                "interview_questions": generated_text,
                "gap_analysis_summary": gap_analysis_summary,
            })
            logger.debug("Fallback tool result: %s", tool_result[:200])
            if "saved to:" in tool_result.lower():
                after = tool_result.split("saved to:")[-1]
                interview_questions_path = after.split("\n")[0].strip()
                logger.info("Prep pack file (fallback): %s", interview_questions_path)
            else:
                errors.append(tool_result)
        else:
            logger.error("No generated content found in agent messages — prep pack skipped.")

    logger.info("Done. Prep pack saved to: %s", interview_questions_path)

    return {
        "interview_questions_path": interview_questions_path,
        "errors": errors,
    }
