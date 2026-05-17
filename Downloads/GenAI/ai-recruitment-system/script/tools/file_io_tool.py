"""
File I/O Tool — writes the interview preparation pack to a Markdown file
and emails it to the hiring manager automatically.
"""
import os
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from pathlib import Path
from langchain_core.tools import tool
from dotenv import load_dotenv

load_dotenv()


def _email_prep_pack(filepath: Path, candidate_name: str, role: str) -> str:
    """
    Internal helper: emails the saved prep pack file to the hiring manager.
    Returns a status string (not raised as exception so the agent always gets a result).
    """
    sender = os.getenv("GMAIL_SENDER", "")
    password = os.getenv("GMAIL_APP_PASSWORD", "")
    hiring_manager_email = os.getenv("HIRING_MANAGER_EMAIL", "")
    hiring_manager_name = os.getenv("HIRING_MANAGER_NAME", "Hiring Manager")
    company = os.getenv("COMPANY_NAME", "Recruiting Team")

    if not sender or not password:
        return "Prep pack email not sent: GMAIL_SENDER or GMAIL_APP_PASSWORD not configured."
    if not hiring_manager_email:
        return "Prep pack email not sent: HIRING_MANAGER_EMAIL not set in .env."

    subject = f"[Interview Prep Pack] {candidate_name} — {role}"
    body = (
        f"Hi {hiring_manager_name},\n\n"
        f"The interview preparation pack for {candidate_name} ({role}) has been generated "
        f"and is attached to this email.\n\n"
        f"The pack includes:\n"
        f"  • Gap-verification questions targeting identified skill gaps\n"
        f"  • Strength-verification questions to probe claimed experience\n"
        f"  • Role-critical and behavioral questions\n"
        f"  • An evaluation guide with red flags to watch for\n\n"
        f"Please review before the interview.\n\n"
        f"Best,\n{company} AI Pipeline"
    )

    msg = MIMEMultipart()
    msg["Subject"] = subject
    msg["From"] = f"{company} <{sender}>"
    msg["To"] = f"{hiring_manager_name} <{hiring_manager_email}>"
    msg.attach(MIMEText(body, "plain"))

    # Attach the Markdown file
    with open(filepath, "rb") as f:
        part = MIMEBase("application", "octet-stream")
        part.set_payload(f.read())
    encoders.encode_base64(part)
    part.add_header(
        "Content-Disposition",
        f'attachment; filename="{filepath.name}"',
    )
    msg.attach(part)

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender, password)
            server.sendmail(sender, hiring_manager_email, msg.as_string())
        return f"Prep pack emailed to {hiring_manager_name} <{hiring_manager_email}>"
    except smtplib.SMTPAuthenticationError:
        return "Prep pack email not sent: Gmail authentication failed. Check GMAIL_APP_PASSWORD."
    except smtplib.SMTPException as e:
        return f"Prep pack email not sent: SMTP error — {str(e)}"
    except Exception as e:
        return f"Prep pack email not sent: {str(e)}"


@tool
def write_interview_prep_pack(
    candidate_name: str,
    role: str,
    candidate_email: str,
    interview_questions: str,
    gap_analysis_summary: str,
) -> str:
    """
    Write a tailored interview preparation pack to a Markdown file and email it
    to the hiring manager.

    Call this tool after generating the interview question set for the hiring manager.
    The output file is saved to the interview_prep_packs/ directory and automatically
    emailed to the configured HIRING_MANAGER_EMAIL.

    Args:
        candidate_name: Full name of the candidate.
        role: The role being interviewed for (e.g., "AI/ML Engineer").
        candidate_email: Candidate's email (used for file naming and reference).
        interview_questions: The fully generated interview question set (Markdown formatted).
        gap_analysis_summary: Brief summary of the candidate's strengths and gaps
                              to give the hiring manager context.

    Returns:
        A status message including the file path and email delivery result.
    """
    output_dir = Path(os.getenv("PREP_PACK_OUTPUT_DIR", "interview_prep_packs"))
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = candidate_name.replace(" ", "_").replace("/", "_").lower()
    filename = f"prep_pack_{safe_name}_{timestamp}.md"
    filepath = output_dir / filename

    content = f"""# Interview Preparation Pack
## {role} — {candidate_name}

**Generated:** {datetime.now().strftime("%B %d, %Y at %I:%M %p")}
**Candidate Email:** {candidate_email}
**Role:** {role}

---

## Candidate Overview

{gap_analysis_summary}

---

## Tailored Interview Questions

> These questions were generated based on this candidate's specific profile —
> their demonstrated strengths, identified skill gaps, and the core role requirements.
> Focus particularly on the gap areas to verify depth of knowledge.

{interview_questions}

---

## Interview Guidelines

- **Duration:** 60 minutes recommended
- **Format:** Begin with a brief intro (5 min), then technical questions (40 min), then candidate Q&A (15 min)
- **Scoring:** Rate each answer 1–5. A score of 3.5+ average indicates a strong pass.
- **Probing:** If the candidate gives a surface-level answer, use "Can you explain why?" or "Walk me through a specific example."
- **Red flags:** Watch for: memorized answers without practical understanding, inability to adapt when probed, overstating experience.

---

*This document was auto-generated by the AI Recruitment Pipeline. Review and adjust before the interview.*
"""

    try:
        filepath.write_text(content, encoding="utf-8")
        file_result = f"Interview prep pack saved to: {filepath.resolve()}"
    except OSError as e:
        return f"Failed to write prep pack: {str(e)}"

    email_result = _email_prep_pack(filepath, candidate_name, role)
    return f"{file_result}\n{email_result}"
