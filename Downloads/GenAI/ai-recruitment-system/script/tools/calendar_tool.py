"""
Calendar Invite Tool — generates an iCalendar (.ics) file and emails it to
the candidate as a Gmail attachment. No Google Calendar API or OAuth required.

Every major email client (Gmail, Outlook, Apple Mail) renders .ics files as
native calendar invites with Accept / Decline buttons.
"""
import os
import smtplib
import uuid
from datetime import datetime, timedelta
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from langchain_core.tools import tool
from dotenv import load_dotenv

load_dotenv()


def _build_ics(
    candidate_name: str,
    candidate_email: str,
    organizer_email: str,
    role: str,
    start_dt: datetime,
    duration_minutes: int,
    description: str,
) -> str:
    """Return a valid iCalendar string for the interview event."""
    end_dt = start_dt + timedelta(minutes=duration_minutes)
    now = datetime.utcnow()
    uid = str(uuid.uuid4())
    company = os.getenv("COMPANY_NAME", "Recruiting Team")

    def fmt(dt: datetime) -> str:
        return dt.strftime("%Y%m%dT%H%M%S")

    safe_description = description.replace("\n", "\\n").replace(",", "\\,")

    return (
        "BEGIN:VCALENDAR\r\n"
        "VERSION:2.0\r\n"
        "PRODID:-//AI Recruitment Pipeline//EN\r\n"
        "CALSCALE:GREGORIAN\r\n"
        "METHOD:REQUEST\r\n"
        "BEGIN:VEVENT\r\n"
        f"UID:{uid}\r\n"
        f"DTSTAMP:{fmt(now)}Z\r\n"
        f"DTSTART:{fmt(start_dt)}\r\n"
        f"DTEND:{fmt(end_dt)}\r\n"
        f"SUMMARY:{role} Technical Interview — {candidate_name}\r\n"
        f"DESCRIPTION:{safe_description}\r\n"
        f"ORGANIZER;CN={company}:MAILTO:{organizer_email}\r\n"
        f"ATTENDEE;CN={candidate_name};ROLE=REQ-PARTICIPANT;"
        f"PARTSTAT=NEEDS-ACTION;RSVP=TRUE:MAILTO:{candidate_email}\r\n"
        "STATUS:CONFIRMED\r\n"
        "SEQUENCE:0\r\n"
        "BEGIN:VALARM\r\n"
        "TRIGGER:-PT30M\r\n"
        "ACTION:DISPLAY\r\n"
        "DESCRIPTION:Interview in 30 minutes\r\n"
        "END:VALARM\r\n"
        "END:VEVENT\r\n"
        "END:VCALENDAR\r\n"
    )


@tool
def create_calendar_event(
    candidate_email: str,
    candidate_name: str,
    role: str,
    interview_date_iso: str,
    duration_minutes: int = 60,
    description: str = "",
) -> str:
    """
    Send a calendar invite (.ics) to the candidate via Gmail.

    Call this tool after the candidate is accepted to schedule their technical
    interview. A proper iCalendar invite is attached to an email so the candidate
    can Accept / Decline directly from their inbox (works in Gmail, Outlook, Apple Mail).

    Args:
        candidate_email: Candidate's email address (receives the invite).
        candidate_name: Candidate's full name (used in event title).
        role: The role being interviewed for (e.g., "AI/ML Engineer").
        interview_date_iso: Interview start datetime in ISO 8601 format
                           (e.g., "2026-05-01T10:00:00"). Use a future date.
        duration_minutes: Duration in minutes (default: 60).
        description: Optional agenda or prep notes for the candidate.

    Returns:
        Confirmation string on success, or an error message.
    """
    sender = os.getenv("GMAIL_SENDER", "")
    password = os.getenv("GMAIL_APP_PASSWORD", "")
    company = os.getenv("COMPANY_NAME", "Recruiting Team")

    if not sender or not password:
        return (
            "Calendar invite not sent: GMAIL_SENDER or GMAIL_APP_PASSWORD not set. "
            "Configure them in your .env file."
        )

    try:
        start_dt = datetime.fromisoformat(interview_date_iso)
    except ValueError:
        return (
            f"Calendar invite not sent: invalid date '{interview_date_iso}'. "
            "Use ISO 8601 format: YYYY-MM-DDTHH:MM:SS"
        )

    if not description:
        description = (
            f"Technical interview for {candidate_name} applying for {role}.\n\n"
            "Please join 5 minutes early. The interview will cover technical skills, "
            "problem-solving, and role-specific questions. Feel free to reply to this "
            "email if you have any questions beforehand."
        )

    ics_content = _build_ics(
        candidate_name=candidate_name,
        candidate_email=candidate_email,
        organizer_email=sender,
        role=role,
        start_dt=start_dt,
        duration_minutes=duration_minutes,
        description=description,
    )

    interview_date_display = start_dt.strftime("%A, %B %d, %Y at %I:%M %p")
    subject = f"Interview Invitation — {role} at {company}"
    body = (
        f"Hi {candidate_name},\n\n"
        f"We're excited to invite you to a technical interview for the {role} position at {company}.\n\n"
        f"  Date & Time: {interview_date_display}\n"
        f"  Duration:    {duration_minutes} minutes\n\n"
        f"A calendar invite is attached to this email. Please accept it to confirm your attendance.\n\n"
        f"If the time doesn't work for you, please reply to this email and we'll find a better slot.\n\n"
        f"Best,\n{company} Recruiting Team"
    )

    msg = MIMEMultipart("mixed")
    msg["Subject"] = subject
    msg["From"] = f"{company} <{sender}>"
    msg["To"] = f"{candidate_name} <{candidate_email}>"

    msg.attach(MIMEText(body, "plain"))

    ics_part = MIMEBase("text", "calendar", method="REQUEST", charset="UTF-8")
    ics_part.set_payload(ics_content.encode("utf-8"))
    encoders.encode_base64(ics_part)
    ics_part.add_header("Content-Disposition", 'attachment; filename="interview_invite.ics"')
    msg.attach(ics_part)

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender, password)
            server.sendmail(sender, candidate_email, msg.as_string())
        return (
            f"Interview scheduled successfully!\n"
            f"Event: {role} Technical Interview — {candidate_name}\n"
            f"Date: {interview_date_display}\n"
            f"Duration: {duration_minutes} minutes\n"
            f"Candidate: {candidate_name} ({candidate_email})\n"
            f"Calendar invite sent via email (.ics attached)"
        )
    except smtplib.SMTPAuthenticationError:
        return (
            "Calendar invite not sent: Gmail authentication failed. "
            "Check GMAIL_APP_PASSWORD in .env."
        )
    except smtplib.SMTPException as e:
        return f"Calendar invite not sent: SMTP error — {str(e)}"
    except Exception as e:
        return f"Calendar invite not sent: {str(e)}"
