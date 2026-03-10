import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders

from gcp_util.secrets import get_photo_email_address, get_photo_email_password
from util.logging_util import setup_logger

logger = setup_logger(__name__)

FRAME_EMAIL = "avondaletowers@ourskylight.com"


def send_photo_email(image_bytes: bytes, filename: str) -> None:
    address = get_photo_email_address()
    password = get_photo_email_password()

    msg = MIMEMultipart()
    msg["From"] = address
    msg["To"] = FRAME_EMAIL
    msg["Subject"] = "Photo"

    part = MIMEBase("image", "jpeg")
    part.set_payload(image_bytes)
    encoders.encode_base64(part)
    part.add_header("Content-Disposition", f'attachment; filename="{filename}"')
    msg.attach(part)

    with smtplib.SMTP("smtp.gmail.com", 587) as smtp:
        smtp.starttls()
        smtp.login(address, password)
        smtp.send_message(msg)

    logger.info(f"Sent photo {filename} to {FRAME_EMAIL}")
