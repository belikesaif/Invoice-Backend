from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime

from ..database import get_db
from ..services.auth_service import auth_service
from ..services.email_service import email_service
from ..models import User, UserCreate, UserLogin, TokenResponse, RefreshTokenRequest, UserResponse, ForgotPasswordRequest, ResetPasswordRequest, MessageResponse

router = APIRouter()
security = HTTPBearer()

# Dependency to get current user
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    token = credentials.credentials
    payload = auth_service.verify_token(token)
    
    if not payload or payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user_id = payload.get("sub")
    user = auth_service.get_user_by_id(db, user_id)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is disabled",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return user

@router.post("/register", response_model=TokenResponse)
async def register(user_data: UserCreate, db: Session = Depends(get_db)):
    # Check if user already exists
    existing_user = auth_service.get_user_by_email(db, user_data.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Create new user
    user = auth_service.create_user(
        db=db,
        email=user_data.email,
        name=user_data.name,
        password=user_data.password,
        provider="email"
    )
    
    # Generate tokens
    tokens = auth_service.create_user_tokens(user)
    
    return TokenResponse(
        access_token=tokens["access_token"],
        refresh_token=tokens["refresh_token"],
        token_type=tokens["token_type"],
        user={
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "provider": user.provider,
            "is_active": user.is_active,
            "created_at": user.created_at.isoformat()
        }
    )

@router.post("/login", response_model=TokenResponse)
async def login(user_credentials: UserLogin, db: Session = Depends(get_db)):
    # Authenticate user
    user = auth_service.authenticate_user(
        db=db,
        email=user_credentials.email,
        password=user_credentials.password
    )
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is disabled",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Generate tokens
    tokens = auth_service.create_user_tokens(user)
    
    return TokenResponse(
        access_token=tokens["access_token"],
        refresh_token=tokens["refresh_token"],
        token_type=tokens["token_type"],
        user={
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "provider": user.provider,
            "is_active": user.is_active,
            "created_at": user.created_at.isoformat()
        }
    )

@router.post("/refresh", response_model=dict)
async def refresh_token(token_data: RefreshTokenRequest, db: Session = Depends(get_db)):
    result = auth_service.refresh_access_token(token_data.refresh_token, db)
    
    if not result:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return result

@router.post("/logout")
async def logout(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Logout user and invalidate tokens.
    
    In a production environment, you would add the token to a blacklist
    or use a token store to track revoked tokens.
    """
    try:
        # Log the logout activity
        current_user.updated_at = datetime.utcnow()
        db.commit()
        
        return MessageResponse(
            message="Successfully logged out. Please clear your tokens.",
            success=True
        )
    except Exception as e:
        return MessageResponse(
            message="Logged out successfully",
            success=True
        )

@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        name=current_user.name,
        provider=current_user.provider,
        is_active=current_user.is_active,
        created_at=current_user.created_at.isoformat()
    )

@router.post("/forgot-password", response_model=MessageResponse)
async def forgot_password(request: ForgotPasswordRequest, db: Session = Depends(get_db)):
    """
    Send password reset email to user.
    
    Always returns success message for security (don't reveal if email exists).
    """
    try:
        # Create reset token
        reset_token = auth_service.create_reset_token(db, request.email)
        
        if reset_token:
            # Get user for name
            user = auth_service.get_user_by_email(db, request.email)
            if user:
                # Send reset email
                email_sent = await email_service.send_password_reset_email(
                    request.email, 
                    reset_token, 
                    user.name
                )
                
                if not email_sent:
                    # Log error but don't reveal to user
                    pass
        
        # Always return success message for security
        return MessageResponse(
            message="If the email address exists in our system, you will receive a password reset link shortly.",
            success=True
        )
        
    except Exception as e:
        # Log error but return success message for security
        return MessageResponse(
            message="If the email address exists in our system, you will receive a password reset link shortly.",
            success=True
        )

@router.post("/reset-password", response_model=MessageResponse)
async def reset_password(request: ResetPasswordRequest, db: Session = Depends(get_db)):
    """
    Reset user password using token.
    """
    try:
        # Verify token and reset password
        success = auth_service.use_reset_token(db, request.token, request.new_password)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired reset token"
            )
        
        # Clean up expired tokens
        auth_service.cleanup_expired_tokens(db)
        
        return MessageResponse(
            message="Password has been reset successfully. You can now log in with your new password.",
            success=True
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reset password"
        )

@router.get("/verify-reset-token/{token}")
async def verify_reset_token(token: str, db: Session = Depends(get_db)):
    """
    Verify if a password reset token is valid.
    """
    user = auth_service.verify_reset_token(db, token)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token"
        )
    
    return MessageResponse(
        message="Token is valid",
        success=True
    )