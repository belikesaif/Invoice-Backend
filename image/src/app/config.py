import json
import os
from pathlib import Path
from typing import Optional, List
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "Smart Invoice Validator"
    API_V1_STR: str = "/api/v1"
    
    # Environment detection
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    IS_AWS_LAMBDA: bool = os.getenv("AWS_LAMBDA_FUNCTION_NAME") is not None
    
    # Database settings
    # DATABASE_URL: str = "sqlite:///./invoice_validator.db"
    DATABASE_URL: str = "postgresql+psycopg2://postgres:zj#NC7UXLX2$P~;@database-1.cryageqwgln3.eu-north-1.rds.amazonaws.com:5432/invoice"
    
    # Gemini AI settings
    GEMINI_API_KEY: str
    GEMINI_MODEL: str = "gemini-2.5-flash"
    CONFIDENCE_THRESHOLD: float = 0.7
    
    # AWS settings
    AWS_REGION: str = "eu-north-1"
    AWS_S3_BUCKET: Optional[str] = "invoice-bucket"
    AWS_ACCESS_KEY_ID: Optional[str] = None
    AWS_SECRET_ACCESS_KEY: Optional[str] = None
    
    # Logging settings
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "logs/app.log" if not os.getenv("AWS_LAMBDA_FUNCTION_NAME") else "/tmp/app.log"
    
    # File upload settings
    UPLOAD_DIR: str = "uploads" if not os.getenv("AWS_LAMBDA_FUNCTION_NAME") else "/tmp/uploads"
    MAX_FILE_SIZE: int = 10 * 1024 * 1024  # 10MB
    ALLOWED_EXTENSIONS: set = {"pdf", "doc", "docx"}
    
    # Authentication settings
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # OAuth settings
    GOOGLE_CLIENT_ID: Optional[str] = None
    GOOGLE_CLIENT_SECRET: Optional[str] = None
    LINKEDIN_CLIENT_ID: Optional[str] = None
    LINKEDIN_CLIENT_SECRET: Optional[str] = None
    
    # Frontend URLs for OAuth redirects
    FRONTEND_URLS: List[str] = ["https://invoice-frontend-five.vercel.app", "http://localhost:3001", "http://localhost:3000", "http://localhost:5173"]
    
    # Email settings
    SMTP_SERVER: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USERNAME: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    FROM_EMAIL: str = "noreply@smartinvoicevalidator.com"
    SEND_REAL_EMAILS: bool = False
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Parse FRONTEND_URLS from environment if it's a JSON string
        if isinstance(self.FRONTEND_URLS, str):
            try:
                self.FRONTEND_URLS = json.loads(self.FRONTEND_URLS)
            except json.JSONDecodeError:
                # Fallback to single URL as list
                self.FRONTEND_URLS = [self.FRONTEND_URLS]
    
    @property
    def use_s3_storage(self) -> bool:
        """Determine if we should use S3 for file storage."""
        return self.IS_AWS_LAMBDA or self.AWS_S3_BUCKET is not None
    
    class Config:
        env_file = ".env"
        case_sensitive = True

# Create necessary directories
def create_directories():
    Path(settings.UPLOAD_DIR).mkdir(parents=True, exist_ok=True)
    Path(settings.LOG_FILE).parent.mkdir(parents=True, exist_ok=True)

settings = Settings()
create_directories() 