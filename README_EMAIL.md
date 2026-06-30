README — send_email_smtp.py

This repository includes `send_email_smtp.py`, a standalone script that sends email using only Python's standard library (`smtplib` and `email.mime`). It supports both interactive prompts and non-interactive CLI usage, and it can read configuration from environment variables.

Quick usage — interactive:

```bash
python send_email_smtp.py
```

Quick usage — non-interactive (CLI):

```bash
python send_email_smtp.py --sender you@example.com --password yourpassword --receiver dest@example.com --subject "Test" --message "Hello from CLI"
```

Environment variables (optional):
- `SMTP_SERVER` — SMTP host (default: smtp.gmail.com)
- `SMTP_PORT` — SMTP port (default: 587)
- `SMTP_USE_SSL` — "1"/"true" to enable SSL (SMTP_SSL)
- `SMTP_USE_TLS` — "1"/"true" to enable STARTTLS
- `MAIL_USERNAME` — default sender email
- `MAIL_PASSWORD` — default sender password
- `MAIL_RECEIVER` — default receiver email
- `MAIL_SUBJECT` — default subject
- `MAIL_MESSAGE` — default message body

Examples for common providers:
- Gmail (App Password recommended): server `smtp.gmail.com`, port `587`, STARTTLS
- Office365: server `smtp.office365.com`, port `587`, STARTTLS
- Yahoo: server `smtp.mail.yahoo.com`, port `465`, SSL

Security notes:
- Do not commit passwords to source control.
- Prefer provider-specific app passwords or per-service SMTP credentials when available.
- For automated usage, set environment variables in your CI/CD or deployment environment rather than embedding passwords in scripts.
