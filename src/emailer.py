import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging
from src import config

logger = logging.getLogger(__name__)


def create_email_content_events(ids):
    links = ["https://www.volosports.com/d/" + id for id in ids]
    links[0] = "\n    " + links[0]
    return {
        "subject": "Volo: New Event Notification",
        "body": "\n".join([
            "New Volo event(s) found!",
            "\n\n    ".join(links)
        ])
    }


def create_email_content_job_failure(error):
    return {
        "subject": "Volo web scraper job failed",
        "body": "\n".join([
            "Volo notification job failed.",
            "",
            "Error:",
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
            server.login(config.EMAIL_SENDER, config.APP_PASSWORD)  # Use app password here
            server.sendmail(config.EMAIL_SENDER, config.EMAIL_RECIPIENT, msg.as_string())
        logger.info("Email sent successfully.")
    except Exception as e:
        logger.error(f"Failed to send email: {e}")
