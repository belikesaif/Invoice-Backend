"""
Models package for Smart Invoice Validator.

This package contains all data models for the application:
- database: SQLAlchemy database models
- api: Pydantic models for API serialization
- document: Pydantic models for document processing
"""

# Database models (SQLAlchemy)
from .database import User, Contract, Invoice, UserSettings, PasswordResetToken

# API models (Pydantic for request/response)
from .api import (
    ItemResponse, ItemCreate,
    ContractCreate, ContractUpdate, ContractResponse,
    InvoiceCreate, InvoiceUpdate, InvoiceResponse,
    UserResponse, UserCreate, UserLogin,
    TokenResponse, RefreshTokenRequest, RefreshTokenResponse,
    UserUpdateRequest, ChangePasswordRequest, 
    UserSettingsResponse, UserSettingsUpdateRequest,
    DocumentUploadRequest,
    ForgotPasswordRequest, ResetPasswordRequest, MessageResponse
)

# Document processing models (Pydantic for AI/OCR)
from .document import (
    DocumentItemModel, InvoiceItemModel,  # InvoiceItemModel is alias
    ExtractedInvoiceModel, ExtractedContractModel
)

# Export database models as primary exports for backward compatibility
__all__ = [
    # Database models - primary exports
    "User", "Contract", "Invoice", "UserSettings", "PasswordResetToken",
    
    # API models
    "ItemResponse", "ItemCreate",
    "ContractCreate", "ContractUpdate", "ContractResponse",
    "InvoiceCreate", "InvoiceUpdate", "InvoiceResponse", 
    "UserResponse", "UserCreate", "UserLogin",
    "TokenResponse", "RefreshTokenRequest", "RefreshTokenResponse",
    "UserUpdateRequest", "ChangePasswordRequest", 
    "UserSettingsResponse", "UserSettingsUpdateRequest",
    "DocumentUploadRequest",
    "ForgotPasswordRequest", "ResetPasswordRequest", "MessageResponse",
    
    # Document processing models
    "DocumentItemModel", "InvoiceItemModel",
    "ExtractedInvoiceModel", "ExtractedContractModel"
]