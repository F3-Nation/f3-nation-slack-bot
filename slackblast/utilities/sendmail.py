import smtplib
from email.message import EmailMessage
from typing import List, Dict, Any
from pathlib import Path


def send(
    subject: str,
    body: str,
    email_server: str,
    email_server_port: int,
    email_user: str,
    email_password: str,
    email_to: str,
    attachments: List[Dict[str, Any]],
):
    """Construct and sends an email.

    Args:
        subject (str): email subject
        body (str): email body
        email_server (str): email server
        email_server_port (str): email server port
        email_user (str): email user address
        email_password (str): email password
        email_to (str): email recipient address
        attachments (List[Dict[str, Any]]): list of attachments, each attachment is a dict with keys "filepath" and "meta", where meta includes filename, maintype, and subtype
    """
    msg = EmailMessage()
    msg.set_content(body)

    msg["Subject"] = subject
    msg["From"] = email_user
    msg["To"] = email_to

    for file in attachments:
        with Path(file["filepath"]).open("rb") as f:
            msg.add_attachment(f.read(), **file["meta"])

    if email_server and email_server_port and email_user and email_password and email_to:
        server = smtplib.SMTP(email_server, email_server_port)
        server.starttls()
        server.login(email_user, email_password)
        server.send_message(msg)
        server.close()
