# OAuth Setup Guide

This document provides instructions on how to set up OAuth authentication with Google, GitHub, and Microsoft for the Real-Time Online Interview system.

## Overview

The login and register pages now support OAuth authentication with:

- **Google** - Social login with Google accounts
- **GitHub** - Social login with GitHub accounts
- **Microsoft** - Social login with Microsoft accounts

## Setup Instructions

### 1. Google OAuth Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Enable the "Google+ API"
4. Go to "Credentials" → Create OAuth 2.0 Client ID
5. Select "Web Application"
6. Add authorized redirect URIs:
   - `http://localhost:5000/auth/callback/google` (for local development)
   - `https://yourdomain.com/auth/callback/google` (for production)
7. Copy the **Client ID** and **Client Secret**

### 2. GitHub OAuth Setup

1. Go to GitHub Settings → [Developer settings](https://github.com/settings/developers)
2. Click "OAuth Apps" → "New OAuth App"
3. Fill in the application details:
   - Application name: `Real-Time Online Interview`
   - Homepage URL: `http://localhost:5000` (or your domain)
   - Authorization callback URL: `http://localhost:5000/auth/callback/github`
4. Copy the **Client ID** and **Client Secret**

### 3. Microsoft OAuth Setup

1. Go to [Azure Portal](https://portal.azure.com/)
2. Navigate to "Azure Active Directory" → "App registrations"
3. Click "New registration"
4. Fill in the application details:
   - Name: `Real-Time Online Interview`
   - Supported account types: "Accounts in any organizational directory and personal Microsoft accounts"
5. Go to "Certificates & secrets" → "New client secret"
6. Go to "Authentication" → Add Redirect URI:
   - `http://localhost:5000/auth/callback/microsoft` (for local development)
   - `https://yourdomain.com/auth/callback/microsoft` (for production)
7. Copy the **Application (client) ID** and **Client Secret Value**

## Environment Variables

Set the following environment variables in your deployment platform or `.env` file:

```bash
# Google OAuth
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret

# GitHub OAuth
GITHUB_CLIENT_ID=your-github-client-id
GITHUB_CLIENT_SECRET=your-github-client-secret

# Microsoft OAuth
MICROSOFT_CLIENT_ID=your-microsoft-client-id
MICROSOFT_CLIENT_SECRET=your-microsoft-client-secret

# Application URL (for OAuth redirects)
APP_URL=http://localhost:5000  # or your production domain
```

### For Local Development

1. Create a `.env` file in the project root
2. Add the environment variables above
3. Install python-dotenv: `pip install python-dotenv`
4. At the beginning of `app.py`, add:
   ```python
   from dotenv import load_dotenv
   load_dotenv()
   ```

### For Railway/Render Deployment

1. Go to your deployment platform's environment variables settings
2. Add all the OAuth credentials there
3. Deploy your application

## Testing OAuth Locally

1. Install requirements: `pip install -r requirements.txt`
2. Set up environment variables (see above)
3. Run the app: `python app.py`
4. Go to `http://localhost:5000/login` or `/register`
5. Click on the OAuth provider buttons (Google, GitHub, Microsoft)
6. You should be redirected to the provider's login page
7. After successful authentication, you'll be logged in

## Features

- ✅ **One-Click Login** - Users can login with a single click
- ✅ **Auto-Registration** - New users are automatically registered with OAuth providers
- ✅ **Account Linking** - If a user already exists with the same email, they're logged in
- ✅ **Profile Information** - User's name and email are automatically fetched from the provider
- ✅ **Multiple Providers** - Users can use any of the three providers

## Security Notes

- OAuth credentials should never be committed to version control
- Always use environment variables for sensitive data
- Keep Client Secrets secure and never expose them
- Use HTTPS in production
- Regularly rotate your OAuth credentials

## Troubleshooting

### "Invalid redirect URI"

- Make sure the redirect URI in your OAuth app settings matches the one in the code
- Include the trailing slash if needed

### "Missing CORS headers"

- Ensure your OAuth credentials are correct
- Check that your app URL matches the registered redirect URL

### "User email not available"

- Some OAuth providers don't expose email by default
- Check the provider's API documentation for required scopes

## Support

For issues with specific OAuth providers:

- [Google OAuth Documentation](https://developers.google.com/identity/protocols/oauth2)
- [GitHub OAuth Documentation](https://docs.github.com/en/developers/apps/building-oauth-apps)
- [Microsoft OAuth Documentation](https://docs.microsoft.com/en-us/azure/active-directory/develop/)
