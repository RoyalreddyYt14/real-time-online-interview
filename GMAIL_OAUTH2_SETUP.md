# Gmail OAuth2 (XOAUTH2) Setup Guide

This guide explains how to set up Gmail OAuth2 authentication for the interview system so admins can send result emails to candidates without needing an App Password.

## Why OAuth2?

- **No App Password needed** — authenticate using your normal Gmail account
- **Better security** — uses industry-standard OAuth2 instead of storing passwords
- **Automatic token refresh** — tokens are refreshed automatically when expired
- **Audit trail** — Google logs OAuth2 authentication separately

## Prerequisites

- A Google account (personal or Google Workspace)
- Access to Google Cloud Console
- Python installed locally (to run the token generation script)

## Step-by-Step Setup

### Step 1: Create a Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Click the project dropdown at the top and select "New Project"
3. Enter a project name (e.g., "Interview System Email") and click "Create"
4. Wait for the project to be created

### Step 2: Enable Gmail API

1. In Google Cloud Console, go to **APIs & Services** > **Library**
2. Search for "Gmail API"
3. Click on "Gmail API" and then click "Enable"
4. Wait a moment for the API to be enabled

### Step 3: Create OAuth2 Credentials

1. Go to **APIs & Services** > **Credentials**
2. Click "Create Credentials" at the top
3. Select "OAuth client ID"
4. If prompted, click "Configure Consent Screen":
   - Choose "External" as User Type
   - Fill in basic app info:
     - App name: "Interview System"
     - User support email: your email
     - Developer contact: your email
   - Click "Save and Continue"
   - On "Scopes" page, skip (not required for this flow) and click "Save and Continue"
   - Review and click "Back to Dashboard"
5. Back on Credentials page, click "Create Credentials" > "OAuth client ID" again
6. Select application type: **"Desktop application"**
7. Click "Create"
8. A popup appears with your credentials. Click "Download JSON" or copy the values.

You should now have:

- Client ID (looks like `xxxxx.apps.googleusercontent.com`)
- Client Secret (long string)

### Step 4: Set Environment Variables

Set the following environment variables on your server:

**On Windows (PowerShell):**

```powershell
# Replace with your actual values
setx GMAIL_OAUTH2_ENABLED "True"
setx GMAIL_OAUTH2_CLIENT_ID "your-client-id.apps.googleusercontent.com"
setx GMAIL_OAUTH2_CLIENT_SECRET "your-client-secret"
setx GMAIL_OAUTH2_REDIRECT_URI "http://localhost:8080"
setx GMAIL_OAUTH2_TOKEN_FILE "C:\path\to\gmail_token.json"
setx MAIL_USERNAME "your-gmail@gmail.com"  # The Gmail account sending emails
```

**On Linux/Mac (bash):**

```bash
export GMAIL_OAUTH2_ENABLED="True"
export GMAIL_OAUTH2_CLIENT_ID="your-client-id.apps.googleusercontent.com"
export GMAIL_OAUTH2_CLIENT_SECRET="your-client-secret"
export GMAIL_OAUTH2_REDIRECT_URI="http://localhost:8080"
export GMAIL_OAUTH2_TOKEN_FILE="/path/to/gmail_token.json"
export MAIL_USERNAME="your-gmail@gmail.com"
```

**On Heroku/Railway/etc.:**

Use the platform's environment variable settings to add the same vars.

### Step 5: Generate the Initial OAuth2 Token

Run the token generation script locally (on your development machine):

```bash
python gmail_oauth2_generate_token.py
```

What happens:

1. A browser window opens
2. You're prompted to authorize the app
3. Click "Allow" to grant permission to send emails
4. The token is saved to the file specified in `GMAIL_OAUTH2_TOKEN_FILE`

The token will be automatically refreshed whenever it expires.

### Step 6: Copy Token to Server

1. Copy the `gmail_token.json` file (generated in step 5) to your server
2. Update `GMAIL_OAUTH2_TOKEN_FILE` env var to point to the file location on the server
3. Restart the Flask app

### Step 7: Test Email Sending

1. Open the admin dashboard
2. Go to a candidate's detail page
3. Fill in the "Send Result Email" form and submit
4. Check if the email was sent successfully

## Troubleshooting

### "Credentials not set" error

Make sure all env vars are set and the app was restarted after setting them:

```powershell
# Check if vars are set
echo $env:GMAIL_OAUTH2_CLIENT_ID
echo $env:MAIL_USERNAME
```

If empty, set them again and restart the app.

### "Invalid token" error

The token file is expired or corrupted. Regenerate it:

```bash
python gmail_oauth2_generate_token.py
```

This will open your browser to re-authorize and save a new token.

### "Token file not found" error

The `GMAIL_OAUTH2_TOKEN_FILE` path is wrong or the file doesn't exist. Run:

```bash
python gmail_oauth2_generate_token.py
```

to create it, or check that the file path is correct and the directory exists.

### Email still not sending

1. Check server logs for detailed error messages (look for "Failed to send email" lines)
2. Verify that `MAIL_USERNAME` matches the Gmail account used to create the OAuth2 credentials
3. Ensure the Gmail account hasn't changed its security settings
4. Re-authorize by running `python gmail_oauth2_generate_token.py` again

## Switching Between Authentication Methods

- **To use OAuth2:** Set `GMAIL_OAUTH2_ENABLED=True` and provide OAuth2 env vars
- **To use password-based (App Password):** Set `GMAIL_OAUTH2_ENABLED=False` (or unset) and set `MAIL_USERNAME` and `MAIL_PASSWORD`

The app automatically chooses the correct method based on `GMAIL_OAUTH2_ENABLED`.

## Security Notes

- Never commit `gmail_token.json` to version control (add to `.gitignore`)
- Never commit `GMAIL_OAUTH2_CLIENT_SECRET` to version control (use env vars only)
- Store credentials securely on your server (use platform secrets if available)
- The token file should have restricted file permissions (read-only for app user)

## Production Deployment

### For Heroku:

```bash
# Set env vars in Heroku
heroku config:set GMAIL_OAUTH2_ENABLED=True
heroku config:set GMAIL_OAUTH2_CLIENT_ID="your-id"
heroku config:set GMAIL_OAUTH2_CLIENT_SECRET="your-secret"
heroku config:set MAIL_USERNAME="your-gmail@gmail.com"

# Generate token locally and upload to Heroku (or use persistent storage add-on)
heroku config:set GMAIL_OAUTH2_TOKEN_FILE="/app/gmail_token.json"
```

### For Railway / Render / etc.:

Use the platform's dashboard to set environment variables, same as above.

### For Docker:

Add env vars to `.env` file (don't commit) or pass via `docker run -e` flags:

```bash
docker run -e GMAIL_OAUTH2_ENABLED=True \
           -e GMAIL_OAUTH2_CLIENT_ID="..." \
           -e MAIL_USERNAME="your-gmail@gmail.com" \
           your-image
```

## References

- [Google OAuth2 Documentation](https://developers.google.com/identity/protocols/oauth2)
- [Gmail API Documentation](https://developers.google.com/gmail/api/guides)
- [XOAUTH2 Protocol](https://developers.google.com/gmail/xoauth2_protocol)
