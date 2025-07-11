"""
API models for request/response serialization.

This module contains Pydantic models used for API endpoints including:
- Request models for creating/updating resources
- Response models for returning data
- Validation and serialization logic
"""

from datetime import datetime
from typing import List, Optional, Dict, Any

from pydantic import BaseModel, Field, validator


class ItemResponse(BaseModel):
    """Response model for contract/invoice items."""
    description: str
    quantity: float = Field(ge=0)
    unit_price: float = Field(ge=0)
    total: float = Field(ge=0)

    class Config:
        from_attributes = True


class ItemCreate(BaseModel):
    """Request model for creating contract/invoice items."""
    description: str = Field(min_length=1, max_length=500)
    quantity: float = Field(gt=0)
    unit_price: float = Field(ge=0)
    total: Optional[float] = None

    @validator("total", always=True)
    def calculate_total(cls, v, values):
        """Auto-calculate total if not provided."""
        if v is None:
            quantity = values.get("quantity", 0)
            unit_price = values.get("unit_price", 0)
            return quantity * unit_price
        return v


# Contract Models
class ContractCreate(BaseModel):
    """Request model for creating contracts."""
    supplier_name: str = Field(min_length=1, max_length=255)
    items: List[ItemCreate] = Field(min_items=1)
    document_path: Optional[str] = None
    is_manual: bool = False


class ContractUpdate(BaseModel):
    """Request model for updating contracts."""
    supplier_name: Optional[str] = Field(None, min_length=1, max_length=255)
    items: Optional[List[ItemCreate]] = None
    document_path: Optional[str] = None
    is_manual: Optional[bool] = None


class ContractResponse(BaseModel):
    """Response model for contracts."""
    id: str
    user_id: str
    supplier_name: str
    items: List[Dict[str, Any]]
    document_path: Optional[str]
    is_manual: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Invoice Models
class InvoiceCreate(BaseModel):
    """Request model for creating invoices."""
    contract_id: Optional[str] = None
    supplier_name: str = Field(min_length=1, max_length=255)
    items: List[ItemCreate] = Field(min_items=1)
    document_path: Optional[str] = None


class InvoiceUpdate(BaseModel):
    """Request model for updating invoices."""
    contract_id: Optional[str] = None
    supplier_name: Optional[str] = Field(None, min_length=1, max_length=255)
    items: Optional[List[ItemCreate]] = None
    validation_message: Optional[str] = None
    is_valid: Optional[bool] = None


class InvoiceResponse(BaseModel):
    """Response model for invoices."""
    id: str
    user_id: str
    contract_id: Optional[str]
    supplier_name: str
    items: List[Dict[str, Any]]
    document_path: Optional[str]
    is_valid: bool
    validation_message: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# User Models
class UserResponse(BaseModel):
    """Response model for user data."""
    id: str
    email: str
    name: str
    provider: Optional[str]
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class UserCreate(BaseModel):
    """Request model for creating users."""
    email: str = Field(pattern=r'^[^@]+@[^@]+\.[^@]+$')
    name: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=8)


class UserLogin(BaseModel):
    """Request model for user login."""
    email: str = Field(pattern=r'^[^@]+@[^@]+\.[^@]+$')
    password: str = Field(min_length=1)


class TokenResponse(BaseModel):
    """Response model for authentication tokens."""
    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    user: UserResponse


class RefreshTokenRequest(BaseModel):
    """Request model for token refresh."""
    refresh_token: str


class UserUpdateRequest(BaseModel):
    """Request model for updating user profile."""
    name: str = Field(min_length=1, max_length=255)


class ChangePasswordRequest(BaseModel):
    """Request model for changing user password."""
    current_password: str
    new_password: str = Field(min_length=8)


class UserSettingsResponse(BaseModel):
    """Response model for user settings."""
    # General Settings
    theme: str
    language: str
    timezone: str
    sound_enabled: bool
    auto_save: bool
    compact_mode: bool
    
    # Processing Settings
    ai_model: str
    ocr_accuracy: str
    auto_processing: bool
    batch_size: int
    retry_attempts: int
    timeout_seconds: int
    
    # Security Settings
    two_factor_auth: bool
    session_timeout: int
    login_notifications: bool
    ip_whitelist: Optional[str] = None
    data_encryption: bool
    audit_log: bool
    
    # Storage Settings
    retention_days: int
    auto_cleanup: bool
    compression_enabled: bool
    backup_frequency: str
    
    # Notification Preferences
    email_notifications: bool
    processing_alerts: bool
    security_alerts: bool
    weekly_reports: bool
    
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class UserSettingsUpdateRequest(BaseModel):
    """Request model for updating user settings."""
    # General Settings
    theme: Optional[str] = Field(None, pattern="^(light|dark|system)$")
    language: Optional[str] = Field(None, max_length=10)
    timezone: Optional[str] = Field(None, max_length=50)
    sound_enabled: Optional[bool] = None
    auto_save: Optional[bool] = None
    compact_mode: Optional[bool] = None
    
    # Processing Settings
    ai_model: Optional[str] = Field(None, max_length=50)
    ocr_accuracy: Optional[str] = Field(None, pattern="^(high|medium|fast)$")
    auto_processing: Optional[bool] = None
    batch_size: Optional[int] = Field(None, ge=1, le=50)
    retry_attempts: Optional[int] = Field(None, ge=1, le=10)
    timeout_seconds: Optional[int] = Field(None, ge=10, le=300)
    
    # Security Settings
    two_factor_auth: Optional[bool] = None
    session_timeout: Optional[int] = Field(None, ge=5, le=480)  # 5 min to 8 hours
    login_notifications: Optional[bool] = None
    ip_whitelist: Optional[str] = Field(None, max_length=500)
    data_encryption: Optional[bool] = None
    audit_log: Optional[bool] = None
    
    # Storage Settings
    retention_days: Optional[int] = Field(None, ge=1, le=3650)  # 1 day to 10 years
    auto_cleanup: Optional[bool] = None
    compression_enabled: Optional[bool] = None
    backup_frequency: Optional[str] = Field(None, pattern="^(daily|weekly|monthly|never)$")
    
    # Notification Preferences
    email_notifications: Optional[bool] = None
    processing_alerts: Optional[bool] = None
    security_alerts: Optional[bool] = None
    weekly_reports: Optional[bool] = None


class RefreshTokenResponse(BaseModel):
    """Response model for token refresh."""
    access_token: str
    token_type: str = "Bearer"


# Document Processing Models
class DocumentUploadRequest(BaseModel):
    """Request model for document upload with base64 content."""
    file_content: str = Field(description="Base64 encoded file content")
    file_type: str = Field(description="File extension (pdf, jpg, jpeg, png)")
    file_name: Optional[str] = None


# Password Reset Models
class ForgotPasswordRequest(BaseModel):
    """Request model for forgot password."""
    email: str = Field(min_length=5, max_length=255, description="User email address")

    class Config:
        from_attributes = True


class ResetPasswordRequest(BaseModel):
    """Request model for password reset."""
    token: str = Field(min_length=10, description="Password reset token")
    new_password: str = Field(min_length=8, max_length=100, description="New password")

    class Config:
        from_attributes = True


class MessageResponse(BaseModel):
    """Generic response model with message."""
    message: str
    success: bool = True

    class Config:
        from_attributes = True


# Export all models for easy imports
__all__ = [
    "ItemResponse", "ItemCreate",
    "ContractCreate", "ContractUpdate", "ContractResponse", 
    "InvoiceCreate", "InvoiceUpdate", "InvoiceResponse",
    "UserResponse", "UserCreate", "UserLogin",
    "TokenResponse", "RefreshTokenRequest", "RefreshTokenResponse",
    "DocumentUploadRequest",
    "ForgotPasswordRequest", "ResetPasswordRequest", "MessageResponse"
]