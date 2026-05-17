"""
Agent 1 — Review Agent
========================
Responsibilities:
  - Retrieves relevant context from the RAG knowledge base (past hires, rubrics, rejection history)
  - Scores the resume against the job description using RAG-grounded criteria
  - Produces a structured GapAnalysis object with strengths, skill gaps, score, and deciding factor

Uses LangChain — swap models by changing LLM_PROVIDER + MODEL in .env.
"""
import json
from langchain_core.messages import SystemMessage, HumanMessage
from config import get_llm, MODEL, LLM_PROVIDER, ROLE_CORE_SKILLS, ROLES
from logger import get_logger
from rag.retriever import retrieve_and_format
from state import GapAnalysis, RecruitmentState

logger = get_logger(__name__)


SYSTEM_PROMPT = """You are a senior technical recruiter and hiring specialist with 10+ years of experience.
Your role is to evaluate candidate resumes against job requirements with precision and fairness.

You have access to a knowledge base containing:
- Profiles of past successful hires (what made them successful)
- Role-specific scoring rubrics (what strong looks like for each skill)
- Historical rejection summaries (why past candidates were rejected and at what score levels)
- Job description templates (exact requirements for each role)
- Onboarding outcome notes (which candidate characteristics predicted strong performance)

EVALUATION PRINCIPLES:
1. Use the retrieved knowledge base context to ground your assessment in company-specific standards
2. Credit transferable skills with a small discount (e.g., TensorFlow experience counts for PyTorch role at 80%)
3. Side projects, open-source, and research count as valid experience when depth is evident
4. Do NOT assume missing skills — only score what is explicitly demonstrated in the resume
5. Be specific: your skill_gaps must name the exact gap, not generic statements
6. The deciding_factor must be the single most important reason for your recommendation
7. Your score must reflect the role rubric (use the rubric in your retrieved context)

OUTPUT FORMAT:
Return a valid JSON object matching this schema exactly:
{
  "strengths": ["specific strength 1", "specific strength 2", ...],
  "skill_gaps": ["specific gap 1", "specific gap 2", ...],
  "score": <integer 0-100>,
  "recommendation": "accept" or "reject",
  "deciding_factor": "One clear sentence stating the PRIMARY reason for the recommendation",
  "feedback_summary": "2-3 sentences summarizing the overall assessment for the recruiter",
  "experience_level": "junior" or "mid" or "senior"
}

Scoring thresholds (from rubric):
- 90+: Strong hire, senior-level consideration
- 75-89: Confident hire, mid-level
- 60-74: Borderline, requires recruiter judgment
- Below 60: Reject

Return ONLY the JSON object — no markdown, no backticks, no explanation outside the JSON."""


def run_review_agent(state: RecruitmentState) -> dict:
    """
    Review Agent node for LangGraph.
    Retrieves RAG context and scores the resume, returning updated state fields.
    """
    resume_text = state["resume_text"]
    job_description = state["job_description"]
    role = state["role"]
    role_display = ROLES.get(role, role)
    core_skills = ROLE_CORE_SKILLS.get(role, [])

    rag_query = f"Role: {role_display}\nJob Description: {job_description}\nCandidate Resume:\n{resume_text}"

    logger.info("Retrieving RAG context...")
    rag_context = retrieve_and_format(rag_query, top_k=6)

    user_message = f"""
Please evaluate this candidate's resume for the {role_display} role.

== ROLE CORE REQUIREMENTS ==
{chr(10).join(f"- {skill}" for skill in core_skills)}

== JOB DESCRIPTION ==
{job_description}

== CANDIDATE RESUME ==
{resume_text}

== KNOWLEDGE BASE CONTEXT (use this to ground your assessment) ==
{rag_context}

Analyze the resume against the role requirements and the knowledge base context.
Return your structured gap analysis as a JSON object.
""".strip()

    logger.info("Calling %s via %s...", MODEL, LLM_PROVIDER)
    llm = get_llm()
    response = llm.invoke([
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=user_message),
    ])

    raw_content = response.content.strip()

    # Strip markdown code fences if the model wraps JSON in them
    if raw_content.startswith("```"):
        raw_content = raw_content.split("```")[1]
        if raw_content.startswith("json"):
            raw_content = raw_content[4:]
        raw_content = raw_content.strip()

    try:
        gap_analysis: GapAnalysis = json.loads(raw_content)
        required_keys = {"strengths", "skill_gaps", "score", "recommendation", "deciding_factor", "feedback_summary", "experience_level"}
        if not required_keys.issubset(gap_analysis.keys()):
            raise ValueError(f"Missing keys: {required_keys - gap_analysis.keys()}")
    except (json.JSONDecodeError, ValueError) as e:
        logger.error("JSON parse error: %s | Raw response: %s", e, raw_content[:300])
        gap_analysis = {
            "strengths": ["Unable to parse response — check model output"],
            "skill_gaps": ["Unable to parse response — check model output"],
            "score": 0,
            "recommendation": "reject",
            "deciding_factor": f"Error parsing Review Agent response: {str(e)}",
            "feedback_summary": raw_content[:500],
            "experience_level": "unknown",
        }

    logger.info("Score: %s/100 | Recommendation: %s", gap_analysis["score"], gap_analysis["recommendation"])

    return {
        "gap_analysis": gap_analysis,
        "rag_context": rag_context,
    }
