"""
Gmail MCP Tool — sends emails via Gmail SMTP.
Wrapped as a LangChain tool so agents can invoke it dynamically based on reasoning.
"""
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from langchain_core.tools import tool
from dotenv import load_dotenv

load_dotenv()


@tool
def send_email(to_email: str, subject: str, body: str) -> str:
    """
    Send an email to a candidate via Gmail SMTP.

    Use this tool to send acceptance or rejection emails. The body should be
    fully composed before calling this tool. Always use a professional but
    human tone in the email body.

    Args:
        to_email: Recipient's email address.
        subject: Email subject line.
        body: Full email body (plain text, no HTML).

    Returns:
        Confirmation string if successful, or an error message.
    """
    sender = os.getenv("GMAIL_SENDER", "")
    password = os.getenv("GMAIL_APP_PASSWORD", "")
    company = os.getenv("COMPANY_NAME", "Recruiting Team")

    if not sender or not password:
        return (
            "Email not sent: GMAIL_SENDER or GMAIL_APP_PASSWORD environment variables are not set. "
            "Please configure them in your .env file."
        )

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{company} <{sender}>"
    msg["To"] = to_email

    msg.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender, password)
            server.sendmail(sender, to_email, msg.as_string())
        return f"Email successfully sent to {to_email} with subject: '{subject}'"
    except smtplib.SMTPAuthenticationError:
        return (
            "Email not sent: Gmail authentication failed. "
            "Ensure you are using a Gmail App Password (not your regular password). "
            "Enable 2FA and generate an App Password at myaccount.google.com/apppasswords."
        )
    except smtplib.SMTPException as e:
        return f"Email not sent: SMTP error — {str(e)}"
    except Exception as e:
        return f"Email not sent: Unexpected error — {str(e)}"
