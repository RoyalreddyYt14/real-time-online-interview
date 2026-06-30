"""
send_email_smtp.py

Standalone script to send an email using only Python's standard library
(smtplib and email.mime). Connects to Gmail SMTP on port 587 using STARTTLS
and logs in with the provided sender email and Gmail App Password.

Requirements implemented:
 - Uses smtp.gmail.com:587
 - Enables TLS with starttls()
 - Logs in with sender email and App Password
 - Constructs email with MIMEMultipart and MIMEText
 - Handles and reports errors

Usage (interactive):
  python send_email_smtp.py

You will be prompted for:
 - Sender Email
 - App Password (input hidden)
 - Receiver Email
 - Subject
 - Message body

Note: Do NOT commit real passwords. Use a Gmail App Password (requires 2FA).
"""

import smtplib
import sys
import traceback
import argparse
import os
from getpass import getpass
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


def send_email_gmail(sender_email: str, app_password: str, receiver_email: str, subject: str, message: str,
                     smtp_server: str = "smtp.gmail.com", smtp_port: int = 587,
                     use_ssl: bool = False, use_tls: bool = True) -> bool:
    """Send an email via Gmail SMTP (smtp.gmail.com:587) using STARTTLS.

    Returns True on success, False on failure.
    """
    # smtp_server, smtp_port, use_ssl, use_tls are provided by parameters

    # Build the message
    msg = MIMEMultipart()
    msg["From"] = sender_email
    msg["To"] = receiver_email
    msg["Subject"] = subject
    msg.attach(MIMEText(message, "plain"))

    try:
        # Choose SSL vs TLS behavior
        if use_ssl:
            server = smtplib.SMTP_SSL(smtp_server, smtp_port, timeout=20)
            server.ehlo()
        else:
            server = smtplib.SMTP(smtp_server, smtp_port, timeout=20)
            server.ehlo()
            if use_tls:
                server.starttls()
                server.ehlo()

        # Login if credentials provided
        if sender_email and app_password:
            server.login(sender_email, app_password)

        # Send the email
        server.sendmail(sender_email, receiver_email, msg.as_string())

        # Clean up
        server.quit()
        print("Email sent successfully")
        return True

    except smtplib.SMTPAuthenticationError as auth_err:
        print("Authentication failed: check your email and App Password.")
        print("If using Gmail, ensure 2-Step Verification is enabled and use an App Password.")
        print("Detailed error:")
        traceback.print_exc()
    except smtplib.SMTPConnectError as conn_err:
        print("Failed to connect to the SMTP server. Check network connectivity or SMTP server/port.")
        print("Detailed error:")
        traceback.print_exc()
    except smtplib.SMTPException as smtp_err:
        print("An SMTP error occurred while sending the message.")
        print("Detailed error:")
        traceback.print_exc()
    except Exception as e:
        print("An unexpected error occurred:")
        traceback.print_exc()

    return False


def interactive_mode():
    """Interactive mode: prompt the user for inputs and send the email."""
    try:
        print("Send email via SMTP (interactive mode).")

        sender = input("Sender Email: ").strip()
        if not sender:
            print("Sender email is required.")
            sys.exit(1)

        # Use getpass to hide the password
        app_password = getpass("Password (input hidden): ")
        if not app_password:
            print("Password is required.")
            sys.exit(1)

        receiver = input("Receiver Email: ").strip()
        if not receiver:
            print("Receiver email is required.")
            sys.exit(1)

        subject = input("Subject: ").strip()
        print("Enter message body. End with an empty line on its own.")
        # Read multi-line message until blank line
        lines = []
        while True:
            try:
                line = input()
            except EOFError:
                break
            if line == "":
                break
            lines.append(line)
        message = "\n".join(lines).strip()
        if not message:
            message = "(No message body)"

        # Ask for SMTP options interactively
        use_custom = input("Use custom SMTP server? (y/N): ").strip().lower() == "y"
        if use_custom:
            smtp_server = input("SMTP server (e.g. smtp.example.com): ").strip() or "smtp.gmail.com"
            try:
                smtp_port = int(input("SMTP port (e.g. 587 or 465): ").strip())
            except Exception:
                smtp_port = 587
            ssl_choice = input("Use SSL? (port 465) (y/N): ").strip().lower() == "y"
            tls_choice = input("Use STARTTLS? (port 587) (y/N): ").strip().lower() == "y"
        else:
            smtp_server = os.environ.get("SMTP_SERVER", "smtp.gmail.com")
            smtp_port = int(os.environ.get("SMTP_PORT", "587"))
            ssl_choice = os.environ.get("SMTP_USE_SSL", "False").lower() in ("1", "true", "yes")
            tls_choice = os.environ.get("SMTP_USE_TLS", "True").lower() in ("1", "true", "yes")

        # Send the message
        success = send_email_gmail(
            sender,
            app_password,
            receiver,
            subject,
            message,
            smtp_server=smtp_server,
            smtp_port=smtp_port,
            use_ssl=ssl_choice,
            use_tls=tls_choice,
        )
        if not success:
            sys.exit(2)

    except KeyboardInterrupt:
        print("\nOperation cancelled by user.")
        sys.exit(1)


def cli_mode(args):
    """Non-interactive CLI mode using argparse args and environment variables as fallbacks."""
    smtp_server = args.smtp or os.environ.get("SMTP_SERVER", "smtp.gmail.com")
    smtp_port = args.port or int(os.environ.get("SMTP_PORT", "587"))
    use_ssl = args.ssl or os.environ.get("SMTP_USE_SSL", "False").lower() in ("1", "true", "yes")
    use_tls = args.tls or os.environ.get("SMTP_USE_TLS", "True").lower() in ("1", "true", "yes")

    sender = args.sender or os.environ.get("MAIL_USERNAME")
    password = args.password or os.environ.get("MAIL_PASSWORD")
    receiver = args.receiver or os.environ.get("MAIL_RECEIVER")
    subject = args.subject or os.environ.get("MAIL_SUBJECT", "(No subject)")

    if args.message_file:
        try:
            with open(args.message_file, "r", encoding="utf-8") as f:
                message = f.read()
        except Exception as e:
            print("Failed to read message file:", e)
            sys.exit(3)
    else:
        message = args.message or os.environ.get("MAIL_MESSAGE", "(No message body)")

    if not sender or not password or not receiver:
        print("For non-interactive mode, --sender, --password and --receiver (or corresponding environment variables) are required.")
        sys.exit(4)

    success = send_email_gmail(
        sender,
        password,
        receiver,
        subject,
        message,
        smtp_server=smtp_server,
        smtp_port=smtp_port,
        use_ssl=use_ssl,
        use_tls=use_tls,
    )
    if not success:
        sys.exit(2)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Send email via SMTP (supports interactive and CLI modes).")
    parser.add_argument("--smtp", help="SMTP server host (env: SMTP_SERVER)")
    parser.add_argument("--port", type=int, help="SMTP server port (env: SMTP_PORT)")
    parser.add_argument("--ssl", action="store_true", help="Use SSL (SMTP_SSL, typically port 465)")
    parser.add_argument("--tls", action="store_true", help="Use STARTTLS (typically port 587)")
    parser.add_argument("--sender", help="Sender email (env: MAIL_USERNAME)")
    parser.add_argument("--password", help="Password (env: MAIL_PASSWORD)")
    parser.add_argument("--receiver", help="Receiver email")
    parser.add_argument("--subject", help="Email subject")
    parser.add_argument("--message", help="Email message body")
    parser.add_argument("--message-file", help="Read message body from file")

    args = parser.parse_args()

    # If CLI args are provided, run non-interactive; otherwise run interactive
    if args.sender or args.receiver or args.message or args.message_file:
        cli_mode(args)
    else:
        interactive_mode()
