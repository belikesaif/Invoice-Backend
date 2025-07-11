from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
import httpx
from typing import Dict, Any
from urllib.parse import urlencode

from ..database import get_db
from ..services.auth_service import auth_service
from ..config import settings

router = APIRouter()

# OAuth2 configuration
class SimpleOAuth2Client:
    def __init__(self, client_id: str, client_secret: str, authorize_url: str, token_url: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self.authorize_url = authorize_url
        self.token_url = token_url
    
    def create_authorization_url(self, redirect_uri: str, scope: str) -> str:
        params = {
            'client_id': self.client_id,
            'redirect_uri': redirect_uri,
            'scope': scope,
            'response_type': 'code',
            'access_type': 'offline'
        }
        return f"{self.authorize_url}?{urlencode(params)}"
    
    async def fetch_access_token(self, http_client: httpx.AsyncClient, code: str, redirect_uri: str) -> dict:
        data = {
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'code': code,
            'grant_type': 'authorization_code',
            'redirect_uri': redirect_uri
        }
        response = await http_client.post(self.token_url, data=data)
        response.raise_for_status()
        return response.json()

def create_google_oauth_client():
    return SimpleOAuth2Client(
        client_id=settings.GOOGLE_CLIENT_ID,
        client_secret=settings.GOOGLE_CLIENT_SECRET,
        authorize_url="https://accounts.google.com/o/oauth2/auth",
        token_url="https://oauth2.googleapis.com/token"
    )

def create_linkedin_oauth_client():
    return SimpleOAuth2Client(
        client_id=settings.LINKEDIN_CLIENT_ID,
        client_secret=settings.LINKEDIN_CLIENT_SECRET,
        authorize_url="https://www.linkedin.com/oauth/v2/authorization",
        token_url="https://www.linkedin.com/oauth/v2/accessToken"
    )

@router.get("/google")
async def google_login(request: Request):
    """Initiate Google OAuth flow"""
    if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Google OAuth not configured"
        )
    
    client = create_google_oauth_client()
    redirect_uri = f"{request.url.scheme}://{request.url.netloc}/api/v1/oauth/google/callback"
    
    authorization_url = client.create_authorization_url(
        redirect_uri=redirect_uri,
        scope="openid email profile"
    )
    
    return RedirectResponse(url=authorization_url)

@router.get("/google/callback")
async def google_callback(request: Request, code: str = None, error: str = None, db: Session = Depends(get_db)):
    """Handle Google OAuth callback"""
    if error:
        return RedirectResponse(url=f"{settings.FRONTEND_URLS[0]}?error=oauth_error&message={error}")
    
    if not code:
        return RedirectResponse(url=f"{settings.FRONTEND_URLS[0]}?error=oauth_error&message=No authorization code received")
    
    try:
        client = create_google_oauth_client()
        redirect_uri = f"{request.url.scheme}://{request.url.netloc}/api/v1/oauth/google/callback"
        
        # Exchange code for access token
        async with httpx.AsyncClient() as http_client:
            token_response = await client.fetch_access_token(
                http_client,
                code=code,
                redirect_uri=redirect_uri
            )
        
        # Get user info from Google
        async with httpx.AsyncClient() as http_client:
            user_info_response = await http_client.get(
                "https://www.googleapis.com/oauth2/v2/userinfo",
                headers={"Authorization": f"Bearer {token_response['access_token']}"}
            )
            user_info = user_info_response.json()
        
        # Create or get user
        user = auth_service.get_or_create_oauth_user(
            db=db,
            email=user_info["email"],
            name=user_info["name"],
            provider="google",
            provider_id=user_info["id"]
        )
        
        # Generate tokens
        tokens = auth_service.create_user_tokens(user)
        
        # Redirect to frontend with tokens
        return RedirectResponse(
            url=f"https://invoice-frontend-five.vercel.app/auth/callback?access_token={tokens['access_token']}&refresh_token={tokens['refresh_token']}"
        )
    
    except Exception as e:
        return RedirectResponse(url=f"https://invoice-frontend-five.vercel.app?error=oauth_error&message=Authentication failed")

@router.get("/linkedin")
async def linkedin_login(request: Request):
    """Initiate LinkedIn OAuth flow"""
    if not settings.LINKEDIN_CLIENT_ID or not settings.LINKEDIN_CLIENT_SECRET:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="LinkedIn OAuth not configured"
        )
    
    client = create_linkedin_oauth_client()
    redirect_uri = f"{request.url.scheme}://{request.url.netloc}/api/v1/oauth/linkedin/callback"
    
    authorization_url = client.create_authorization_url(
        redirect_uri=redirect_uri,
        scope="r_liteprofile r_emailaddress"
    )
    
    return RedirectResponse(url=authorization_url)

@router.get("/linkedin/callback")
async def linkedin_callback(request: Request, code: str = None, error: str = None, db: Session = Depends(get_db)):
    """Handle LinkedIn OAuth callback"""
    if error:
        return RedirectResponse(url=f"{settings.FRONTEND_URLS[0]}?error=oauth_error&message={error}")
    
    if not code:
        return RedirectResponse(url=f"{settings.FRONTEND_URLS[0]}?error=oauth_error&message=No authorization code received")
    
    try:
        client = create_linkedin_oauth_client()
        redirect_uri = f"{request.url.scheme}://{request.url.netloc}/api/v1/oauth/linkedin/callback"
        
        # Exchange code for access token
        async with httpx.AsyncClient() as http_client:
            token_response = await client.fetch_access_token(
                http_client,
                code=code,
                redirect_uri=redirect_uri
            )
        
        # Get user profile from LinkedIn
        async with httpx.AsyncClient() as http_client:
            profile_response = await http_client.get(
                "https://api.linkedin.com/v2/people/~:(id,firstName,lastName)",
                headers={"Authorization": f"Bearer {token_response['access_token']}"}
            )
            profile_data = profile_response.json()
            
            # Get email address separately
            email_response = await http_client.get(
                "https://api.linkedin.com/v2/emailAddress?q=members&projection=(elements*(handle~))",
                headers={"Authorization": f"Bearer {token_response['access_token']}"}
            )
            email_data = email_response.json()
        
        # Extract user information
        first_name = profile_data.get("firstName", {}).get("localized", {}).get("en_US", "")
        last_name = profile_data.get("lastName", {}).get("localized", {}).get("en_US", "")
        full_name = f"{first_name} {last_name}".strip() or "LinkedIn User"
        
        email = None
        if email_data.get("elements"):
            email = email_data["elements"][0]["handle~"]["emailAddress"]
        
        if not email:
            return RedirectResponse(url=f"{settings.FRONTEND_URLS[0]}?error=oauth_error&message=Email not available from LinkedIn")
        
        # Create or get user
        user = auth_service.get_or_create_oauth_user(
            db=db,
            email=email,
            name=full_name,
            provider="linkedin",
            provider_id=profile_data["id"]
        )
        
        # Generate tokens
        tokens = auth_service.create_user_tokens(user)
        
        # Redirect to frontend with tokens
        return RedirectResponse(
            url=f"{settings.FRONTEND_URLS[0]}/auth/callback?access_token={tokens['access_token']}&refresh_token={tokens['refresh_token']}"
        )
    
    except Exception as e:
        return RedirectResponse(url=f"{settings.FRONTEND_URLS[0]}?error=oauth_error&message=Authentication failed")