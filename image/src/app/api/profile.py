from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Dict
import uuid

from ..database import get_db
from ..models import (
    User, UserSettings,
    UserResponse, UserUpdateRequest, ChangePasswordRequest,
    UserSettingsResponse, UserSettingsUpdateRequest
)
from ..services.auth_service import auth_service
from ..middleware.auth_middleware import get_current_user
from loguru import logger

router = APIRouter(prefix="/profile", tags=["profile"])


@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(
    current_user: User = Depends(get_current_user)
):
    """Get current user's profile information."""
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        name=current_user.name,
        provider=current_user.provider,
        is_active=current_user.is_active,
        created_at=current_user.created_at
    )


@router.put("/me", response_model=UserResponse)
async def update_user_profile(
    profile_data: UserUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update current user's profile information."""
    try:
        # Update user data
        current_user.name = profile_data.name
        db.commit()
        db.refresh(current_user)
        
        logger.info(f"Profile updated for user {current_user.id}")
        
        return UserResponse(
            id=current_user.id,
            email=current_user.email,
            name=current_user.name,
            provider=current_user.provider,
            is_active=current_user.is_active,
            created_at=current_user.created_at
        )
    except Exception as e:
        logger.error(f"Error updating profile for user {current_user.id}: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update profile"
        )


@router.post("/change-password")
async def change_password(
    password_data: ChangePasswordRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Change user's password."""
    try:
        # Verify current password (only for email users)
        if current_user.provider == "email":
            if not current_user.hashed_password:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="No password set for this account"
                )
            
            if not auth_service.verify_password(password_data.current_password, current_user.hashed_password):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Current password is incorrect"
                )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot change password for OAuth accounts"
            )
        
        # Update password
        current_user.hashed_password = auth_service.get_password_hash(password_data.new_password)
        db.commit()
        
        logger.info(f"Password changed for user {current_user.id}")
        
        return {"message": "Password changed successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error changing password for user {current_user.id}: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to change password"
        )


@router.get("/settings", response_model=UserSettingsResponse)
async def get_user_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get current user's settings and preferences."""
    try:
        # Get or create user settings
        user_settings = db.query(UserSettings).filter(UserSettings.user_id == current_user.id).first()
        
        if not user_settings:
            # Create default settings for new user
            user_settings = UserSettings(
                id=str(uuid.uuid4()),
                user_id=current_user.id
            )
            db.add(user_settings)
            db.commit()
            db.refresh(user_settings)
            logger.info(f"Created default settings for user {current_user.id}")
        
        return UserSettingsResponse(
            theme=user_settings.theme,
            language=user_settings.language,
            timezone=user_settings.timezone,
            sound_enabled=user_settings.sound_enabled,
            auto_save=user_settings.auto_save,
            compact_mode=user_settings.compact_mode,
            ai_model=user_settings.ai_model,
            ocr_accuracy=user_settings.ocr_accuracy,
            auto_processing=user_settings.auto_processing,
            batch_size=user_settings.batch_size,
            retry_attempts=user_settings.retry_attempts,
            timeout_seconds=user_settings.timeout_seconds,
            two_factor_auth=user_settings.two_factor_auth,
            session_timeout=user_settings.session_timeout,
            login_notifications=user_settings.login_notifications,
            ip_whitelist=user_settings.ip_whitelist,
            data_encryption=user_settings.data_encryption,
            audit_log=user_settings.audit_log,
            retention_days=user_settings.retention_days,
            auto_cleanup=user_settings.auto_cleanup,
            compression_enabled=user_settings.compression_enabled,
            backup_frequency=user_settings.backup_frequency,
            email_notifications=user_settings.email_notifications,
            processing_alerts=user_settings.processing_alerts,
            security_alerts=user_settings.security_alerts,
            weekly_reports=user_settings.weekly_reports,
            created_at=user_settings.created_at,
            updated_at=user_settings.updated_at
        )
    except Exception as e:
        logger.error(f"Error getting settings for user {current_user.id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get user settings"
        )


@router.put("/settings", response_model=UserSettingsResponse)
async def update_user_settings(
    settings_data: UserSettingsUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update current user's settings and preferences."""
    try:
        # Get or create user settings
        user_settings = db.query(UserSettings).filter(UserSettings.user_id == current_user.id).first()
        
        if not user_settings:
            # Create new settings if they don't exist
            user_settings = UserSettings(
                id=str(uuid.uuid4()),
                user_id=current_user.id
            )
            db.add(user_settings)
        
        # Update only provided fields
        update_data = settings_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            if hasattr(user_settings, field):
                setattr(user_settings, field, value)
        
        db.commit()
        db.refresh(user_settings)
        
        logger.info(f"Settings updated for user {current_user.id}")
        
        return UserSettingsResponse(
            theme=user_settings.theme,
            language=user_settings.language,
            timezone=user_settings.timezone,
            sound_enabled=user_settings.sound_enabled,
            auto_save=user_settings.auto_save,
            compact_mode=user_settings.compact_mode,
            ai_model=user_settings.ai_model,
            ocr_accuracy=user_settings.ocr_accuracy,
            auto_processing=user_settings.auto_processing,
            batch_size=user_settings.batch_size,
            retry_attempts=user_settings.retry_attempts,
            timeout_seconds=user_settings.timeout_seconds,
            two_factor_auth=user_settings.two_factor_auth,
            session_timeout=user_settings.session_timeout,
            login_notifications=user_settings.login_notifications,
            ip_whitelist=user_settings.ip_whitelist,
            data_encryption=user_settings.data_encryption,
            audit_log=user_settings.audit_log,
            retention_days=user_settings.retention_days,
            auto_cleanup=user_settings.auto_cleanup,
            compression_enabled=user_settings.compression_enabled,
            backup_frequency=user_settings.backup_frequency,
            email_notifications=user_settings.email_notifications,
            processing_alerts=user_settings.processing_alerts,
            security_alerts=user_settings.security_alerts,
            weekly_reports=user_settings.weekly_reports,
            created_at=user_settings.created_at,
            updated_at=user_settings.updated_at
        )
    except Exception as e:
        logger.error(f"Error updating settings for user {current_user.id}: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update user settings"
        )


@router.delete("/me")
async def delete_user_account(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete current user's account and all associated data."""
    try:
        # Delete user (cascades to contracts, invoices, and settings)
        db.delete(current_user)
        db.commit()
        
        logger.info(f"Account deleted for user {current_user.id}")
        
        return {"message": "Account deleted successfully"}
    except Exception as e:
        logger.error(f"Error deleting account for user {current_user.id}: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete account"
        )


@router.post("/export-data")
async def export_user_data(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Export all user data for GDPR compliance."""
    try:
        # Get all user data
        contracts = db.query(current_user.contracts).all()
        invoices = db.query(current_user.invoices).all()
        settings = db.query(UserSettings).filter(UserSettings.user_id == current_user.id).first()
        
        user_data = {
            "user": {
                "id": current_user.id,
                "email": current_user.email,
                "name": current_user.name,
                "provider": current_user.provider,
                "created_at": current_user.created_at.isoformat(),
                "updated_at": current_user.updated_at.isoformat()
            },
            "contracts": [
                {
                    "id": contract.id,
                    "supplier_name": contract.supplier_name,
                    "items": contract.items,
                    "created_at": contract.created_at.isoformat()
                } for contract in contracts
            ],
            "invoices": [
                {
                    "id": invoice.id,
                    "supplier_name": invoice.supplier_name,
                    "items": invoice.items,
                    "created_at": invoice.created_at.isoformat()
                } for invoice in invoices
            ],
            "settings": {
                "theme": settings.theme if settings else "light",
                "language": settings.language if settings else "en",
                # ... other settings
            } if settings else {}
        }
        
        logger.info(f"Data export requested for user {current_user.id}")
        
        # In a real implementation, you would:
        # 1. Generate a downloadable file (JSON/CSV)
        # 2. Send it via email or provide download link
        # 3. Log the export for audit purposes
        
        return {
            "message": "Data export initiated. You will receive an email with your data shortly.",
            "export_id": str(uuid.uuid4()),
            "data": user_data  # For demo purposes, return data directly
        }
    except Exception as e:
        logger.error(f"Error exporting data for user {current_user.id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to export user data"
        )