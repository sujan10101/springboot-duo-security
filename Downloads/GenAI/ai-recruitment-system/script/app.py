"""
AI Recruitment Pipeline — Streamlit Application
================================================
A recruiter-facing UI for the agentic AI recruitment pipeline.

Workflow:
  1. Recruiter uploads a resume PDF and provides job description
  2. Review Agent (RAG-grounded) scores the resume → gap analysis displayed
  3. Recruiter reviews the gap analysis and makes Accept/Reject decision
  4. Orchestrator routes to:
       - ACCEPT: Communication Agent (email + calendar) + Prep Pack Agent (questions → file) in parallel
       - REJECT: Rejection Agent (specific, feedback-rich rejection email)
"""
import os
import sys
import json
import tempfile
from pathlib import Path

import streamlit as st
import PyPDF2
from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, str(Path(__file__).parent))

from config import ROLES, ROLE_CORE_SKILLS, COMPANY_NAME
from graph.recruitment_graph import run_review_phase, run_downstream_phase

st.set_page_config(
    page_title="AI Recruitment Pipeline",
    page_icon="🤝",
    layout="wide",
    initial_sidebar_state="expanded",
)

ROLE_OPTIONS = {
    "ai_ml_engineer": "AI/ML Engineer",
    "backend_engineer": "Backend Engineer",
    "frontend_engineer": "Frontend Engineer",
}

DEFAULT_JD = {
    "ai_ml_engineer": (
        "We are hiring a mid-level AI/ML Engineer to join our team. "
        "The role involves building RAG pipelines, fine-tuning LLMs using LoRA/QLoRA, "
        "and deploying models to production. Required: Python, PyTorch or TensorFlow, "
        "LLM experience (fine-tuning preferred), MLOps/deployment skills, strong ML fundamentals."
    ),
    "backend_engineer": (
        "We are hiring a mid-level Backend Engineer. The role involves designing scalable "
        "APIs, owning microservices, and working with cloud infrastructure on AWS. "
        "Required: Python (Django/FastAPI), PostgreSQL, AWS, Docker, CI/CD, system design."
    ),
    "frontend_engineer": (
        "We are hiring a mid-level Frontend Engineer. The role involves building accessible, "
        "performant React/TypeScript UIs, maintaining our component library, and collaborating "
        "with designers in Figma. Required: React, TypeScript, CSS3, testing, Tailwind, accessibility."
    ),
}


def init_session_state() -> None:
    defaults = {
        "phase": "input",
        "review_state": None,
        "final_state": None,
        "resume_text": "",
        "candidate_name": "",
        "candidate_email": "sujankhadka@u.boisestate.edu",
        "role": "ai_ml_engineer",
        "job_description": "",
        "recruiter_notes": "",
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def extract_pdf_text(pdf_file) -> str:
    try:
        reader = PyPDF2.PdfReader(pdf_file)
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    except Exception as e:
        st.error(f"Failed to extract text from PDF: {e}")
        return ""


def render_sidebar() -> None:
    with st.sidebar:
        st.image("https://img.icons8.com/fluency/96/handshake.png", width=60)
        st.title("AI Recruitment Pipeline")
        st.caption(f"Powered by Claude Sonnet 4.5 + LangGraph")
        st.divider()

        st.subheader("Pipeline Configuration")
        st.markdown(
            f"**Company:** {COMPANY_NAME or 'TechCorp'}\n\n"
            "**Architecture:** Hierarchical Multi-Agent\n\n"
            "**LLM:** Ollama (local)\n\n"
            "**Embeddings:** text-embedding-3-small\n\n"
            "**Vector Store:** ChromaDB (local)\n\n"
            "**Tools:** Gmail MCP · Google Calendar MCP · File I/O"
        )
        st.divider()

        st.subheader("Environment Status")
        ollama_ok = bool(os.getenv("OLLAMA_BASE_URL") or os.getenv("API_KEY"))
        openai_ok = bool(os.getenv("OPENAI_API_KEY"))
        gmail_ok = bool(os.getenv("GMAIL_SENDER")) and bool(os.getenv("GMAIL_APP_PASSWORD"))
        calendar_ok = Path(os.getenv("GOOGLE_CREDENTIALS_FILE", "credentials.json")).exists()

        st.markdown(
            f"{'✅' if ollama_ok else '❌'} Ollama Running\n\n"
            f"{'✅' if openai_ok else '❌'} OpenAI API Key (embeddings)\n\n"
            f"{'✅' if gmail_ok else '⚠️'} Gmail SMTP\n\n"
            f"{'✅' if calendar_ok else '⚠️'} Google Calendar credentials\n\n"
        )

        if not ollama_ok or not openai_ok:
            st.warning("⚠️ Missing required API keys. See .env.example for setup instructions.")

        st.divider()

        if st.button("🔄 Reset Application", use_container_width=True):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()


def render_input_phase() -> None:
    st.header("📋 Step 1: Candidate & Role Information")

    col1, col2 = st.columns([1, 1])

    with col1:
        st.subheader("Candidate Details")
        candidate_name = st.text_input(
            "Candidate Full Name *",
            value=st.session_state.candidate_name,
            placeholder="e.g. Jane Smith",
        )
        candidate_email = st.text_input(
            "Candidate Email Address *",
            value=st.session_state.candidate_email,
            placeholder="jane.smith@example.com",
        )
        role = st.selectbox(
            "Role Applying For *",
            options=list(ROLE_OPTIONS.keys()),
            format_func=lambda x: ROLE_OPTIONS[x],
            index=list(ROLE_OPTIONS.keys()).index(st.session_state.role),
        )

    with col2:
        st.subheader("Core Requirements Preview")
        skills = ROLE_CORE_SKILLS.get(role, [])
        for skill in skills:
            st.markdown(f"• {skill}")

    st.subheader("Job Description")
    job_description = st.text_area(
        "Paste or edit the job description *",
        value=st.session_state.job_description or DEFAULT_JD.get(role, ""),
        height=150,
        placeholder="Describe the role, responsibilities, and requirements...",
    )

    st.subheader("Resume Upload")
    resume_file = st.file_uploader(
        "Upload candidate resume (PDF) *",
        type=["pdf"],
        help="The Review Agent will extract and analyze the text content."
    )

    resume_text = ""
    if resume_file:
        with st.spinner("Extracting text from PDF..."):
            resume_text = extract_pdf_text(resume_file)
        if resume_text:
            with st.expander("📄 Extracted Resume Text (preview)", expanded=False):
                st.text(resume_text[:2000] + ("..." if len(resume_text) > 2000 else ""))
            st.success(f"✅ Resume extracted ({len(resume_text)} characters)")
        else:
            st.error("Could not extract text from the PDF. Please check the file.")

    st.divider()

    can_proceed = all([candidate_name, candidate_email, role, job_description, resume_text])

    if not can_proceed:
        missing = []
        if not candidate_name: missing.append("Candidate Name")
        if not candidate_email: missing.append("Candidate Email")
        if not job_description: missing.append("Job Description")
        if not resume_text: missing.append("Resume (PDF)")
        st.info(f"Please complete: {', '.join(missing)}")

    if st.button("🔍 Analyze Resume with AI", type="primary", disabled=not can_proceed, use_container_width=True):
        st.session_state.candidate_name = candidate_name
        st.session_state.candidate_email = candidate_email
        st.session_state.role = role
        st.session_state.job_description = job_description
        st.session_state.resume_text = resume_text
        st.session_state.phase = "reviewing"
        st.rerun()


def render_reviewing_phase() -> None:
    st.header("🔍 Step 2: AI Review in Progress")

    st.info(
        "The **Review Agent** is analyzing the resume using our RAG knowledge base "
        "(past hires, scoring rubrics, rejection history). This may take 15–30 seconds."
    )

    with st.spinner("Running Review Agent (RAG-grounded analysis)..."):
        try:
            result = run_review_phase(
                resume_text=st.session_state.resume_text,
                job_description=st.session_state.job_description,
                candidate_email=st.session_state.candidate_email,
                candidate_name=st.session_state.candidate_name,
                role=st.session_state.role,
            )
            st.session_state.review_state = result
            st.session_state.phase = "decision"
            st.rerun()
        except Exception as e:
            st.error(f"Review Agent error: {str(e)}")
            st.exception(e)
            if st.button("← Back to Input"):
                st.session_state.phase = "input"
                st.rerun()


def render_decision_phase() -> None:
    st.header("📊 Step 3: Review Agent Analysis — Recruiter Decision")

    review_state = st.session_state.review_state
    gap = review_state.get("gap_analysis", {})

    if not gap:
        st.error("No gap analysis found. Please re-run the review.")
        if st.button("← Back"):
            st.session_state.phase = "input"
            st.rerun()
        return

    score = gap.get("score", 0)
    recommendation = gap.get("recommendation", "reject")
    experience_level = gap.get("experience_level", "unknown")
    deciding_factor = gap.get("deciding_factor", "")
    feedback_summary = gap.get("feedback_summary", "")
    strengths = gap.get("strengths", [])
    skill_gaps = gap.get("skill_gaps", [])

    col1, col2, col3 = st.columns(3)
    with col1:
        color = "green" if score >= 75 else "orange" if score >= 60 else "red"
        st.metric("AI Score", f"{score}/100")
    with col2:
        st.metric("AI Recommendation", recommendation.upper())
    with col3:
        st.metric("Experience Level", experience_level.capitalize())

    st.divider()

    col_left, col_right = st.columns(2)

    with col_left:
        st.subheader("✅ Identified Strengths")
        for s in strengths:
            st.markdown(f"• {s}")

    with col_right:
        st.subheader("⚠️ Skill Gaps")
        for g in skill_gaps:
            st.markdown(f"• {g}")

    st.divider()
    st.subheader("🎯 Primary Deciding Factor")
    st.info(deciding_factor)

    st.subheader("📝 AI Summary")
    st.write(feedback_summary)

    with st.expander("🔍 View RAG Context Retrieved", expanded=False):
        st.text(review_state.get("rag_context", "No context retrieved."))

    st.divider()
    st.header("⚖️ Recruiter Decision")
    st.markdown(
        "The AI recommendation is advisory. **You make the final call.** "
        "Your decision determines which downstream agents are invoked."
    )

    recruiter_notes = st.text_area(
        "Optional: Add notes (will be included in downstream agent context)",
        value=st.session_state.recruiter_notes,
        placeholder="e.g. 'Strong culture fit from the interview call' or 'Gap is a dealbreaker for this sprint'",
        height=80,
    )
    st.session_state.recruiter_notes = recruiter_notes

    col_accept, col_reject = st.columns(2)

    with col_accept:
        if st.button("✅ Accept Candidate", type="primary", use_container_width=True):
            st.session_state.recruiter_decision = "accept"
            st.session_state.phase = "processing"
            st.rerun()

    with col_reject:
        if st.button("❌ Reject Candidate", type="secondary", use_container_width=True):
            st.session_state.recruiter_decision = "reject"
            st.session_state.phase = "processing"
            st.rerun()


def render_processing_phase() -> None:
    decision = st.session_state.recruiter_decision
    candidate_name = st.session_state.candidate_name

    st.header(f"⚙️ Step 4: Processing {'Acceptance' if decision == 'accept' else 'Rejection'}")

    if decision == "accept":
        st.info(
            f"**Orchestrator** routed to the **accept path**.\n\n"
            f"Running in parallel:\n"
            f"- 📧 **Communication Agent** — sending acceptance email + scheduling Google Calendar interview\n"
            f"- 📋 **Preparation Pack Agent** — generating tailored interview questions + saving to file"
        )
    else:
        st.info(
            f"**Orchestrator** routed to the **reject path**.\n\n"
            f"- ✉️ **Rejection Agent** — composing specific, feedback-rich rejection email based on gap analysis"
        )

    with st.spinner(f"Running downstream agents for {candidate_name}..."):
        try:
            final_state = run_downstream_phase(
                state=st.session_state.review_state,
                recruiter_decision=decision,
                recruiter_notes=st.session_state.recruiter_notes,
            )
            st.session_state.final_state = final_state
            st.session_state.phase = "complete"
            st.rerun()
        except Exception as e:
            st.error(f"Pipeline error: {str(e)}")
            st.exception(e)
            if st.button("← Back to Decision"):
                st.session_state.phase = "decision"
                st.rerun()


def render_complete_phase() -> None:
    final_state = st.session_state.final_state
    decision = st.session_state.recruiter_decision
    candidate_name = st.session_state.candidate_name

    if decision == "accept":
        st.success(f"🎉 Application for **{candidate_name}** successfully processed!")
        st.header("✅ Acceptance Pipeline Complete")

        col1, col2, col3 = st.columns(3)
        with col1:
            email_sent = final_state.get("acceptance_email_sent", False)
            st.metric("Acceptance Email", "✅ Sent" if email_sent else "❌ Failed")
        with col2:
            cal_created = final_state.get("calendar_event_created", False)
            st.metric("Calendar Event", "✅ Created" if cal_created else "❌ Failed")
        with col3:
            prep_path = final_state.get("interview_questions_path")
            st.metric("Prep Pack", "✅ Saved" if prep_path else "❌ Failed")

        if final_state.get("calendar_event_link"):
            st.markdown(f"📅 **Calendar Event:** [Open in Google Calendar]({final_state['calendar_event_link']})")

        if prep_path:
            st.info(f"📋 Interview prep pack saved to: `{prep_path}`")
            try:
                pack_content = Path(prep_path).read_text(encoding="utf-8")
                with st.expander("📄 View Interview Prep Pack", expanded=True):
                    st.markdown(pack_content)
            except Exception:
                pass

    else:
        st.warning(f"Application for **{candidate_name}** has been rejected.")
        st.header("✉️ Rejection Pipeline Complete")

        email_sent = final_state.get("rejection_email_sent", False)
        st.metric(
            "Rejection Email",
            "✅ Sent with specific feedback" if email_sent else "❌ Failed to send"
        )

        if email_sent:
            st.success(
                f"A specific, feedback-rich rejection email was sent to "
                f"{st.session_state.candidate_email}. "
                "It included the actual deciding factor and actionable improvement recommendations — "
                "not a generic form letter."
            )

    errors = final_state.get("errors", [])
    if errors:
        with st.expander("⚠️ Errors / Warnings", expanded=False):
            for err in errors:
                st.warning(err)

    st.divider()

    col1, col2 = st.columns(2)
    with col1:
        if st.button("📝 Process Another Candidate", type="primary", use_container_width=True):
            keys_to_clear = [
                "phase", "review_state", "final_state", "resume_text",
                "candidate_name", "candidate_email", "recruiter_notes",
                "recruiter_decision"
            ]
            for k in keys_to_clear:
                if k in st.session_state:
                    del st.session_state[k]
            st.rerun()

    with col2:
        if st.button("🔁 Re-run Decision", use_container_width=True):
            st.session_state.phase = "decision"
            st.rerun()


def main() -> None:
    init_session_state()
    render_sidebar()

    phase = st.session_state.phase

    if phase == "input":
        render_input_phase()
    elif phase == "reviewing":
        render_reviewing_phase()
    elif phase == "decision":
        render_decision_phase()
    elif phase == "processing":
        render_processing_phase()
    elif phase == "complete":
        render_complete_phase()
    else:
        st.error(f"Unknown phase: {phase}")
        st.session_state.phase = "input"
        st.rerun()


if __name__ == "__main__":
    main()
