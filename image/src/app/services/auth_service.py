from datetime import datetime, timedelta
from typing import Optional, Union
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from ..models import User, PasswordResetToken
from ..config import settings
import uuid
import secrets

class AuthService:
    def __init__(self):
        self.pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        self.SECRET_KEY = getattr(settings, 'SECRET_KEY', 'your-secret-key-here')
        self.ALGORITHM = "HS256"
        self.ACCESS_TOKEN_EXPIRE_MINUTES = 30
        self.REFRESH_TOKEN_EXPIRE_DAYS = 7

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash"""
        return self.pwd_context.verify(plain_password, hashed_password)

    def get_password_hash(self, password: str) -> str:
        """Hash a password"""
        return self.pwd_context.hash(password)

    def create_access_token(self, data: dict, expires_delta: Optional[timedelta] = None) -> str:
        """Create a JWT access token"""
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=self.ACCESS_TOKEN_EXPIRE_MINUTES)
        
        to_encode.update({"exp": expire, "type": "access"})
        encoded_jwt = jwt.encode(to_encode, self.SECRET_KEY, algorithm=self.ALGORITHM)
        return encoded_jwt

    def create_refresh_token(self, data: dict) -> str:
        """Create a JWT refresh token"""
        to_encode = data.copy()
        expire = datetime.utcnow() + timedelta(days=self.REFRESH_TOKEN_EXPIRE_DAYS)
        to_encode.update({"exp": expire, "type": "refresh"})
        
        encoded_jwt = jwt.encode(to_encode, self.SECRET_KEY, algorithm=self.ALGORITHM)
        return encoded_jwt

    def verify_token(self, token: str) -> Optional[dict]:
        """Verify and decode a JWT token"""
        try:
            payload = jwt.decode(token, self.SECRET_KEY, algorithms=[self.ALGORITHM])
            return payload
        except JWTError:
            return None

    def get_user_by_email(self, db: Session, email: str) -> Optional[User]:
        """Get user by email"""
        return db.query(User).filter(User.email == email).first()

    def get_user_by_id(self, db: Session, user_id: str) -> Optional[User]:
        """Get user by ID"""
        return db.query(User).filter(User.id == user_id).first()

    def create_user(self, db: Session, email: str, name: str, password: str = None, 
                   provider: str = "email", provider_id: str = None) -> User:
        """Create a new user"""
        hashed_password = self.get_password_hash(password) if password else None
        
        user = User(
            id=str(uuid.uuid4()),
            email=email,
            name=name,
            hashed_password=hashed_password,
            provider=provider,
            provider_id=provider_id,
            is_active=True
        )
        
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    def authenticate_user(self, db: Session, email: str, password: str) -> Optional[User]:
        """Authenticate user with email and password"""
        user = self.get_user_by_email(db, email)
        if not user:
            return None
        if not user.hashed_password:  # OAuth user trying to login with password
            return None
        if not self.verify_password(password, user.hashed_password):
            return None
        return user

    def create_user_tokens(self, user: User) -> dict:
        """Create access and refresh tokens for user"""
        token_data = {"sub": user.id, "email": user.email}
        
        access_token = self.create_access_token(token_data)
        refresh_token = self.create_refresh_token(token_data)
        
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "Bearer"
        }

    def refresh_access_token(self, refresh_token: str, db: Session) -> Optional[dict]:
        """Create new access token using refresh token"""
        payload = self.verify_token(refresh_token)
        if not payload or payload.get("type") != "refresh":
            return None
        
        user_id = payload.get("sub")
        user = self.get_user_by_id(db, user_id)
        if not user or not user.is_active:
            return None
        
        # Create new access token
        token_data = {"sub": user.id, "email": user.email}
        access_token = self.create_access_token(token_data)
        
        return {
            "access_token": access_token,
            "token_type": "Bearer"
        }

    def get_or_create_oauth_user(self, db: Session, email: str, name: str, 
                                provider: str, provider_id: str) -> User:
        """Get existing OAuth user or create new one"""
        # First check if user exists with this email
        user = self.get_user_by_email(db, email)
        
        if user:
            # Update provider info if different
            if user.provider != provider or user.provider_id != provider_id:
                user.provider = provider
                user.provider_id = provider_id
                db.commit()
                db.refresh(user)
            return user
        
        # Create new user
        return self.create_user(db, email, name, None, provider, provider_id)
    
    def create_reset_token(self, db: Session, email: str) -> Optional[str]:
        """Create a password reset token for user"""
        user = self.get_user_by_email(db, email)
        if not user:
            return None
        
        # Generate secure random token
        token = secrets.token_urlsafe(32)
        
        # Set expiration to 1 hour from now
        expires_at = datetime.utcnow() + timedelta(hours=1)
        
        # Create reset token record
        reset_token = PasswordResetToken(
            id=str(uuid.uuid4()),
            user_id=user.id,
            token=token,
            expires_at=expires_at,
            used=False
        )
        
        db.add(reset_token)
        db.commit()
        db.refresh(reset_token)
        
        return token
    
    def verify_reset_token(self, db: Session, token: str) -> Optional[User]:
        """Verify password reset token and return user if valid"""
        reset_token = db.query(PasswordResetToken).filter(
            PasswordResetToken.token == token,
            PasswordResetToken.used == False,
            PasswordResetToken.expires_at > datetime.utcnow()
        ).first()
        
        if not reset_token:
            return None
        
        return reset_token.user
    
    def use_reset_token(self, db: Session, token: str, new_password: str) -> bool:
        """Use password reset token to set new password"""
        reset_token = db.query(PasswordResetToken).filter(
            PasswordResetToken.token == token,
            PasswordResetToken.used == False,
            PasswordResetToken.expires_at > datetime.utcnow()
        ).first()
        
        if not reset_token:
            return False
        
        # Mark token as used
        reset_token.used = True
        
        # Update user password
        user = reset_token.user
        user.hashed_password = self.get_password_hash(new_password)
        user.updated_at = datetime.utcnow()
        
        db.commit()
        return True
    
    def cleanup_expired_tokens(self, db: Session):
        """Clean up expired password reset tokens"""
        db.query(PasswordResetToken).filter(
            PasswordResetToken.expires_at < datetime.utcnow()
        ).delete()
        db.commit()

# Global instance
auth_service = AuthService()