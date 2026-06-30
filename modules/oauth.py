"""
OAuth integration for Google, GitHub, and Microsoft authentication.
"""

import os
import requests
from authlib.integrations.flask_client import OAuth
from flask import Flask, session, url_for, redirect

oauth = OAuth()

# ===========================
# OAUTH CONFIGURATION
# ===========================
def init_oauth(app: Flask):
    """Initialize OAuth with Flask app."""
    
    oauth.init_app(app)
    
    # ===========================
    # GOOGLE OAUTH
    # ===========================
    oauth.register(
        name='google',
        client_id=os.environ.get('GOOGLE_CLIENT_ID', ''),
        client_secret=os.environ.get('GOOGLE_CLIENT_SECRET', ''),
        server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
        client_kwargs={'scope': 'openid email profile'},
        authorize_url='https://accounts.google.com/o/oauth2/v2/auth',
        token_url='https://oauth2.googleapis.com/token',
        userinfo_endpoint='https://openidconnect.googleapis.com/v1/userinfo',
    )
    
    # ===========================
    # GITHUB OAUTH
    # ===========================
    oauth.register(
        name='github',
        client_id=os.environ.get('GITHUB_CLIENT_ID', ''),
        client_secret=os.environ.get('GITHUB_CLIENT_SECRET', ''),
        authorize_url='https://github.com/login/oauth/authorize',
        token_url='https://github.com/login/oauth/access_token',
        userinfo_endpoint='https://api.github.com/user',
        client_kwargs={'scope': 'user:email'},
    )
    
    # ===========================
    # MICROSOFT OAUTH
    # ===========================
    oauth.register(
        name='microsoft',
        client_id=os.environ.get('MICROSOFT_CLIENT_ID', ''),
        client_secret=os.environ.get('MICROSOFT_CLIENT_SECRET', ''),
        authorize_url='https://login.microsoftonline.com/common/oauth2/v2.0/authorize',
        token_url='https://login.microsoftonline.com/common/oauth2/v2.0/token',
        userinfo_endpoint='https://graph.microsoft.com/v1.0/me',
        client_kwargs={
            'scope': 'openid profile email',
        },
    )


def get_oauth_user_info(provider: str, token: dict):
    """
    Fetch user info from OAuth provider using the token.
    Returns: {'name': str, 'email': str}
    """
    
    if provider == 'google':
        headers = {'Authorization': f'Bearer {token.get("access_token")}'}
        resp = requests.get('https://openidconnect.googleapis.com/v1/userinfo', headers=headers)
        data = resp.json()
        return {
            'name': data.get('name', data.get('email', 'Unknown')),
            'email': data.get('email'),
            'avatar': data.get('picture'),
        }
    
    elif provider == 'github':
        headers = {'Authorization': f'token {token.get("access_token")}'}
        resp = requests.get('https://api.github.com/user', headers=headers)
        data = resp.json()
        
        # Get email if profile email is not set
        email = data.get('email')
        if not email:
            resp_email = requests.get('https://api.github.com/user/emails', headers=headers)
            emails = resp_email.json()
            email = next((e['email'] for e in emails if e['primary']), None)
        
        return {
            'name': data.get('name') or data.get('login', 'Unknown'),
            'email': email,
            'avatar': data.get('avatar_url'),
        }
    
    elif provider == 'microsoft':
        headers = {'Authorization': f'Bearer {token.get("access_token")}'}
        resp = requests.get('https://graph.microsoft.com/v1.0/me', headers=headers)
        data = resp.json()
        
        # Get user's email
        resp_mail = requests.get('https://graph.microsoft.com/v1.0/me/mailboxSettings', headers=headers)
        mail_data = resp_mail.json()
        
        return {
            'name': data.get('displayName', 'Unknown'),
            'email': data.get('userPrincipalName') or data.get('mail'),
            'avatar': None,
        }
    
    return {'name': 'Unknown', 'email': None}
