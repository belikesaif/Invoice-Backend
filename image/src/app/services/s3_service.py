import boto3
import os
from typing import Optional
from botocore.exceptions import ClientError
from ..config import settings
from loguru import logger
import uuid
from pathlib import Path

class S3Service:
    """Service for handling file operations with AWS S3."""
    
    def __init__(self):
        self.s3_client = None
        self.bucket_name = settings.AWS_S3_BUCKET
        
        if settings.use_s3_storage:
            try:
                # Initialize S3 client
                if settings.AWS_ACCESS_KEY_ID and settings.AWS_SECRET_ACCESS_KEY:
                    logger.info("Using AWS credentials from settings for S3 client")
                    self.s3_client = boto3.client(
                        's3',
                        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                        region_name=settings.AWS_REGION
                    )
                    logger.info("S3 client initialized with provided credentials")
                else:
                    # Use IAM role if running in Lambda
                    logger.info("Using IAM role for S3 client")
                    self.s3_client = boto3.client('s3', region_name=settings.AWS_REGION)
                
                logger.info(f"S3 service initialized with bucket: {settings.AWS_REGION}")
            except Exception as e:
                logger.error(f"Failed to initialize S3 client: {str(e)}")
                self.s3_client = None
    
    def upload_file(self, file_content: bytes, file_name: str, content_type: str = None) -> Optional[str]:
        """
        Upload a file to S3 and return the S3 key.
        
        Args:
            file_content: The file content as bytes
            file_name: Original filename
            content_type: MIME type of the file
            
        Returns:
            S3 key if successful, None otherwise
        """
        if not self.s3_client or not self.bucket_name:
            logger.error("S3 client not initialized or bucket name not set")
            return None
        
        try:
            # Generate unique filename
            file_extension = Path(file_name).suffix
            unique_filename = f"{uuid.uuid4()}{file_extension}"
            s3_key = f"uploads/{unique_filename}"
            
            # Upload to S3
            extra_args = {}
            if content_type:
                extra_args['ContentType'] = content_type
            
            logger.info(f"{self.bucket_name} Uploading file to S3: {s3_key} with content type: {content_type}")
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=s3_key,
                Body=file_content,
                **extra_args
            )
            
            logger.info(f"File uploaded to S3: {s3_key}")
            return s3_key
            
        except ClientError as e:
            logger.error(f"Failed to upload file to S3: {str(e)}")
            return None
    
    def download_file(self, s3_key: str) -> Optional[bytes]:
        """
        Download a file from S3.
        
        Args:
            s3_key: The S3 key of the file
            
        Returns:
            File content as bytes if successful, None otherwise
        """
        if not self.s3_client or not self.bucket_name:
            logger.error("S3 client not initialized or bucket name not set")
            return None
        
        try:
            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=s3_key)
            return response['Body'].read()
            
        except ClientError as e:
            logger.error(f"Failed to download file from S3: {str(e)}")
            return None
    
    def delete_file(self, s3_key: str) -> bool:
        """
        Delete a file from S3.
        
        Args:
            s3_key: The S3 key of the file
            
        Returns:
            True if successful, False otherwise
        """
        if not self.s3_client or not self.bucket_name:
            logger.error("S3 client not initialized or bucket name not set")
            return False
        
        try:
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=s3_key)
            logger.info(f"File deleted from S3: {s3_key}")
            return True
            
        except ClientError as e:
            logger.error(f"Failed to delete file from S3: {str(e)}")
            return False
    
    def get_file_url(self, s3_key: str, expiration: int = 3600) -> Optional[str]:
        """
        Generate a presigned URL for accessing a file in S3.
        
        Args:
            s3_key: The S3 key of the file
            expiration: URL expiration time in seconds (default: 1 hour)
            
        Returns:
            Presigned URL if successful, None otherwise
        """
        if not self.s3_client or not self.bucket_name:
            logger.error("S3 client not initialized or bucket name not set")
            return None
        
        try:
            url = self.s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.bucket_name, 'Key': s3_key},
                ExpiresIn=expiration
            )
            return url
            
        except ClientError as e:
            logger.error(f"Failed to generate presigned URL: {str(e)}")
            return None

# Create global instance
s3_service = S3Service()