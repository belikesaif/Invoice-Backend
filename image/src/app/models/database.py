"""
Database models for the Smart Invoice Validator application.

This module contains all SQLAlchemy database models including:
- User: Authentication and user management
- Contract: Contract document storage and management
- Invoice: Invoice document storage and management
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import Column, String, DateTime, ForeignKey, JSON, Boolean, Text, Integer
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from ..database import Base


class User(Base):
    """
    User model for authentication and user management.
    
    Supports both email/password authentication and OAuth providers
    (Google, LinkedIn).
    """
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    name = Column(String(255), nullable=False)
    hashed_password = Column(String(255), nullable=True)  # Nullable for OAuth users
    provider = Column(String(50), nullable=True, default="email")  # 'email', 'google', 'linkedin'
    provider_id = Column(String(255), nullable=True)  # OAuth provider user ID
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    contracts = relationship("Contract", back_populates="user", cascade="all, delete-orphan")
    invoices = relationship("Invoice", back_populates="user", cascade="all, delete-orphan")
    settings = relationship("UserSettings", back_populates="user", uselist=False, cascade="all, delete-orphan")
    reset_tokens = relationship("PasswordResetToken", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email={self.email}, provider={self.provider})>"


class UserSettings(Base):
    """
    User settings and preferences model.
    
    Stores all user preferences for appearance, processing, security, and storage.
    """
    __tablename__ = "user_settings"

    id = Column(String(36), primary_key=True, index=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, unique=True)
    
    # General Settings
    theme = Column(String(20), default="light", nullable=False)  # light, dark, system
    language = Column(String(10), default="en", nullable=False)
    timezone = Column(String(50), default="UTC", nullable=False)
    sound_enabled = Column(Boolean, default=True, nullable=False)
    auto_save = Column(Boolean, default=True, nullable=False)
    compact_mode = Column(Boolean, default=False, nullable=False)
    
    # Processing Settings
    ai_model = Column(String(50), default="gemini-2.0-flash", nullable=False)
    ocr_accuracy = Column(String(20), default="high", nullable=False)  # high, medium, fast
    auto_processing = Column(Boolean, default=True, nullable=False)
    batch_size = Column(Integer, default=10, nullable=False)
    retry_attempts = Column(Integer, default=3, nullable=False)
    timeout_seconds = Column(Integer, default=30, nullable=False)
    
    # Security Settings
    two_factor_auth = Column(Boolean, default=False, nullable=False)
    session_timeout = Column(Integer, default=60, nullable=False)  # minutes
    login_notifications = Column(Boolean, default=True, nullable=False)
    ip_whitelist = Column(Text, nullable=True)  # comma-separated IPs
    data_encryption = Column(Boolean, default=True, nullable=False)
    audit_log = Column(Boolean, default=True, nullable=False)
    
    # Storage Settings
    retention_days = Column(Integer, default=365, nullable=False)
    auto_cleanup = Column(Boolean, default=True, nullable=False)
    compression_enabled = Column(Boolean, default=True, nullable=False)
    backup_frequency = Column(String(20), default="weekly", nullable=False)  # daily, weekly, monthly, never
    
    # Notification Preferences
    email_notifications = Column(Boolean, default=True, nullable=False)
    processing_alerts = Column(Boolean, default=True, nullable=False)
    security_alerts = Column(Boolean, default=True, nullable=False)
    weekly_reports = Column(Boolean, default=False, nullable=False)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("User", back_populates="settings")

    def __repr__(self) -> str:
        return f"<UserSettings(id={self.id}, user_id={self.user_id}, theme={self.theme})>"


class Contract(Base):
    """
    Contract model for storing contract documents and their extracted data.
    
    Contracts can be created manually or by uploading and processing documents.
    Each contract belongs to a specific user.
    """
    __tablename__ = "contracts"

    id = Column(String(36), primary_key=True, index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    supplier_name = Column(String(255), nullable=False, index=True)
    items = Column(JSON, nullable=False)  # Store items as JSON array
    document_path = Column(String(500), nullable=True)  # Path to uploaded document
    is_manual = Column(Boolean, default=False, nullable=False)  # Whether contract was manually entered
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("User", back_populates="contracts")
    invoices = relationship("Invoice", back_populates="contract", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Contract(id={self.id}, supplier={self.supplier_name}, user_id={self.user_id})>"


class Invoice(Base):
    """
    Invoice model for storing invoice documents and their extracted data.
    
    Invoices can be linked to contracts for validation purposes.
    Each invoice belongs to a specific user.
    """
    __tablename__ = "invoices"

    id = Column(String(36), primary_key=True, index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    contract_id = Column(String(36), ForeignKey("contracts.id", ondelete="SET NULL"), nullable=True, index=True)
    supplier_name = Column(String(255), nullable=False, index=True)
    items = Column(JSON, nullable=False)  # Store line items as JSON array
    document_path = Column(String(500), nullable=True)  # Path to uploaded document
    is_valid = Column(Boolean, default=False, nullable=False)  # Whether document is a valid invoice
    validation_message = Column(Text, nullable=True)  # Message from validation
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("User", back_populates="invoices")
    contract = relationship("Contract", back_populates="invoices")

    def __repr__(self) -> str:
        return f"<Invoice(id={self.id}, supplier={self.supplier_name}, user_id={self.user_id})>"


class PasswordResetToken(Base):
    """
    Password reset token model for forgot password functionality.
    
    Stores secure tokens for password reset requests with expiration.
    """
    __tablename__ = "password_reset_tokens"

    id = Column(String(36), primary_key=True, index=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    token = Column(String(255), unique=True, index=True, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    used = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("User", back_populates="reset_tokens")

    def __repr__(self) -> str:
        return f"<PasswordResetToken(id={self.id}, user_id={self.user_id}, used={self.used})>"


# Export all models for easy imports
__all__ = ["User", "UserSettings", "Contract", "Invoice", "PasswordResetToken"]