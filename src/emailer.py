import sys
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging

from src import config

logger = logging.getLogger(__name__)


def event_info_string(event_info, indent=4):
    indent = " " * indent
    if sys.platform.startswith("win"):
        strftime_modifier = "#"
    else:
        strftime_modifier = "-"
    string = (
        f"{indent}Date: {event_info['start_time'].strftime(f'%{strftime_modifier}m/%{strftime_modifier}d (%A)')} from "
        f"{event_info['start_time'].strftime(f'%{strftime_modifier}I:%M %p')} to "
        f"{event_info['end_time'].strftime(f'%{strftime_modifier}I:%M %p')}"
    )
    string += f"\n{indent}Location: {event_info['location']}"
    if event_info["level"]:
        string += f"\n{indent}Level: {event_info['level']}"
    if event_info.get("registered"):
        string += f"\n{indent}Registered: {event_info['registered']}"
    if event_info.get("status"):
        string += f"\n{indent}Status: {event_info['status']}"
    if event_info.get("registration_date"):
        string += (
            f"\n{indent}Registration Open Date: "
            f"{event_info['registration_date'].strftime(
                f'%{strftime_modifier}m/%{strftime_modifier}d (%A) %{strftime_modifier}I:%M %p'
            )}"
        )
    string += f"\n{indent}Link: {event_info['url']}"
    return string


def create_email_content_events(event_lists, retry_counter):
    event_infos = []
    num_events_found = sum(len(events) for events in event_lists)
    for event_list in event_lists:
        if event_list:
            event_infos.append(f"{len(event_list)} new {event_list[0]['organization'].title()} event(s) found!")
            event_infos.extend(event_info_string(event) for event in event_list)
    num_jobs_failed = sum(1 for value in retry_counter.values() if value != 0)
    if num_jobs_failed:
        for org in retry_counter:
            if retry_counter[org]:
                event_infos.append(f"{org.replace("_", " ").title()} job has failed {retry_counter[org]} consecutive times.")
    subject = "Volleyball Event Notification: "
    if num_events_found and num_jobs_failed:
        subject += f"{num_events_found} New Events, {num_jobs_failed} Jobs Failed"
    elif num_events_found:
        subject += f"{num_events_found} New Events"
    elif num_jobs_failed:
        subject += f"{num_jobs_failed} Jobs Failed"
    return {
        "subject": subject,
        "body": "\n\n".join(event_infos)
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
