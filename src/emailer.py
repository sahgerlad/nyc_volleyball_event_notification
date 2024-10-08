import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging
from src import config

logger = logging.getLogger(__name__)


def create_email_body(ids):
    header = "New Volo event(s) found!"
    links = ["https://www.volosports.com/d/" + id for id in ids]
    body = header + "\n    " + "\n\n    ".join(links)
    return body


def send_email(ids):
    logger.info("Sending email notification...")
    msg = MIMEMultipart()
    msg['From'] = config.EMAIL_SENDER
    msg['To'] = config.EMAIL_RECIPIENT
    msg['Subject'] = 'Volo: New Event Notification'

    body = create_email_body(ids)
    msg.attach(MIMEText(body, 'plain'))

    try:
        with smtplib.SMTP("smtp.gmail.com", config.SMTP_PORT) as server:
            server.starttls()
            server.login(config.EMAIL_SENDER, config.APP_PASSWORD)  # Use app password here
            server.sendmail(config.EMAIL_SENDER, config.EMAIL_RECIPIENT, msg.as_string())
        logger.info("Email sent successfully.")
    except Exception as e:
        logger.error(f"Failed to send email: {e}")
