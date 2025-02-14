import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging

from src import config

logger = logging.getLogger(__name__)


def event_info_string(event_info, indent=4):
    indent = " " * indent
    string = (
        f"{indent}Date: {event_info['start_time'].strftime('%-m/%-d (%A)')} from "
        f"{event_info['start_time'].strftime('%-I:%M %p')} to {event_info['end_time'].strftime('%-I:%M %p')}"
    )
    string += f"\n{indent}Location: {event_info['location']}"
    if event_info["level"]:
        string += f"\n{indent}Level: {event_info['level']}"
    if event_info['registered']:
        string += f"\n{indent}Registered: {event_info['registered']}"
    string += f"\n{indent}Link: https://www.volosports.com/d/{event_info['event_id']}"
    return string


def create_email_content_events(events):
    event_infos = [event_info_string(event) for event in events]
    event_infos = [f"{len(event_infos)} new Volo event(s) found!"] + event_infos
    return {
        "subject": "Volo: New Event Notification",
        "body": "\n\n".join(event_infos)
    }


def create_email_content_job_failure(error):
    return {
        "subject": "Volo web scraper job failed",
        "body": "\n".join([
            "Volo notification job failed.",
            "\nError:",
            f"    {error}"
        ])
    }


def send_email(subject, body):
    logger.info("Sending email notification...")
    msg = MIMEMultipart()
    msg['From'] = config.EMAIL_SENDER
    msg['To'] = config.EMAIL_RECIPIENT
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))

    try:
        with smtplib.SMTP("smtp.gmail.com", config.SMTP_PORT) as server:
            server.starttls()
            server.login(config.EMAIL_SENDER, config.APP_PASSWORD)
            server.sendmail(config.EMAIL_SENDER, config.EMAIL_RECIPIENT, msg.as_string())
        logger.info("Email sent successfully.")
    except Exception as e:
        logger.exception(f"Failed to send email: {e}")
