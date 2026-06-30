@echo off
REM startup_app.bat - Set environment variables and start Flask app

echo Setting Gmail SMTP credentials...
set GMAIL_OAUTH2_ENABLED=False
set MAIL_USERNAME=chennakesavareddy909@gmail.com
set MAIL_PASSWORD=mmxyazvbcydznnlh
set SMTP_SERVER=smtp.gmail.com
set SMTP_PORT=587
set SMTP_USE_TLS=True
set ADMIN_EMAIL=chennakesavareddy909@gmail.com

echo.
echo Environment variables set:
echo MAIL_USERNAME=%MAIL_USERNAME%
echo SMTP_SERVER=%SMTP_SERVER%
echo SMTP_PORT=%SMTP_PORT%
echo.

echo Starting Flask app...
call .venv-1\Scripts\activate.bat
python app.py

pause
