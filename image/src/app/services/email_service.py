"""
Email service for sending password reset and notification emails.

This service handles all email communication including:
- Password reset emails
- Account notifications
- Security alerts
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional
from loguru import logger

from ..config import settings


class EmailService:
    """Service for sending emails."""
    
    def __init__(self):
        self.smtp_server = settings.SMTP_SERVER
        self.smtp_port = settings.SMTP_PORT
        self.smtp_username = settings.SMTP_USERNAME
        self.smtp_password = settings.SMTP_PASSWORD
        self.from_email = settings.FROM_EMAIL
        self.send_real_emails = settings.SEND_REAL_EMAILS
    
    async def send_password_reset_email(self, email: str, reset_token: str, user_name: str) -> bool:
        """
        Send password reset email to user.
        
        Args:
            email: User's email address
            reset_token: Password reset token
            user_name: User's name
            
        Returns:
            bool: True if email sent successfully, False otherwise
        """
        try:
            # Create reset URL - in production, use your actual frontend domain
            reset_url = f"{settings.FRONTEND_URLS[0]}/reset-password?token={reset_token}"
            
            # Create email content
            subject = "Password Reset Request - Smart Invoice Validator"
            
            html_body = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="utf-8">
                <title>Password Reset</title>
                <style>
                    body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                    .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                    .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
                    .content {{ background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }}
                    .button {{ display: inline-block; background: #667eea; color: white; padding: 12px 30px; text-decoration: none; border-radius: 5px; margin: 20px 0; }}
                    .footer {{ text-align: center; margin-top: 30px; font-size: 12px; color: #666; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h1>🔒 Password Reset Request</h1>
                    </div>
                    <div class="content">
                        <p>Hello {user_name},</p>
                        
                        <p>We received a request to reset your password for your Smart Invoice Validator account.</p>
                        
                        <p>Click the button below to reset your password:</p>
                        
                        <p style="text-align: center;">
                            <a href="{reset_url}" class="button">Reset Password</a>
                        </p>
                        
                        <p>If the button doesn't work, you can copy and paste this link into your browser:</p>
                        <p style="word-break: break-all; background: #eee; padding: 10px; border-radius: 5px;">
                            {reset_url}
                        </p>
                        
                        <p><strong>This link will expire in 1 hour for security reasons.</strong></p>
                        
                        <p>If you didn't request this password reset, please ignore this email. Your password will remain unchanged.</p>
                        
                        <p>Best regards,<br>
                        The Smart Invoice Validator Team</p>
                    </div>
                    <div class="footer">
                        <p>This is an automated message. Please do not reply to this email.</p>
                    </div>
                </div>
            </body>
            </html>
            """
            
            text_body = f"""
            Password Reset Request - Smart Invoice Validator
            
            Hello {user_name},
            
            We received a request to reset your password for your Smart Invoice Validator account.
            
            Please click the following link to reset your password:
            {reset_url}
            
            This link will expire in 1 hour for security reasons.
            
            If you didn't request this password reset, please ignore this email. Your password will remain unchanged.
            
            Best regards,
            The Smart Invoice Validator Team
            
            ---
            This is an automated message. Please do not reply to this email.
            """
            
            # Check if we should send real emails
            if not self.send_real_emails or not self.smtp_username or not self.smtp_password:
                logger.info(f"📧 [EMAIL SIMULATION] Password reset email for {email}")
                logger.info(f"🔗 Reset URL: {reset_url}")
                logger.info(f"🎟️  Token: {reset_token}")
                logger.info(f"👤 User: {user_name}")
                logger.info("📝 To enable real emails, set SEND_REAL_EMAILS=true and configure SMTP settings in .env")
                return True
            
            # Send actual email
            return await self._send_email(email, subject, html_body, text_body)
            
        except Exception as e:
            logger.error(f"Failed to send password reset email to {email}: {str(e)}")
            return False
    
    async def _send_email(self, to_email: str, subject: str, html_body: str, text_body: str) -> bool:
        """
        Send email using SMTP.
        
        Args:
            to_email: Recipient email address
            subject: Email subject
            html_body: HTML email body
            text_body: Plain text email body
            
        Returns:
            bool: True if sent successfully, False otherwise
        """
        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = self.from_email
            msg['To'] = to_email
            
            # Add text and HTML parts
            text_part = MIMEText(text_body, 'plain')
            html_part = MIMEText(html_body, 'html')
            
            msg.attach(text_part)
            msg.attach(html_part)
            
            # Send email
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                if self.smtp_username and self.smtp_password:
                    server.starttls()
                    server.login(self.smtp_username, self.smtp_password)
                
                server.send_message(msg)
            
            logger.info(f"Password reset email sent successfully to {to_email}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {str(e)}")
            return False


# Create singleton instance
email_service = EmailService()