#!/usr/bin/env python3
"""
Email Configuration Setup Script for Smart Invoice Validator

This script helps you configure real email sending for password reset functionality.
"""

import os
import sys
from pathlib import Path

def main():
    print("🔧 Smart Invoice Validator - Email Setup")
    print("=" * 50)
    print()
    
    env_file = Path(".env")
    
    if not env_file.exists():
        print("❌ .env file not found. Please make sure you're in the backend directory.")
        return
    
    print("📧 To send real password reset emails, you'll need:")
    print("   1. A Gmail account")
    print("   2. A Gmail App Password (not your regular password)")
    print()
    print("📝 How to create a Gmail App Password:")
    print("   1. Go to https://support.google.com/accounts/answer/185833")
    print("   2. Follow the instructions to create an App Password")
    print("   3. Use that App Password below (not your regular Gmail password)")
    print()
    
    setup = input("🚀 Do you want to configure email sending? (y/n): ").lower().strip()
    
    if setup != 'y':
        print("📋 Email setup skipped. Password reset emails will be logged to console.")
        return
    
    print()
    email = input("📧 Enter your Gmail address: ").strip()
    if not email or '@' not in email:
        print("❌ Invalid email address")
        return
    
    app_password = input("🔑 Enter your Gmail App Password: ").strip()
    if not app_password:
        print("❌ App password cannot be empty")
        return
    
    # Read current .env file
    with open(env_file, 'r') as f:
        content = f.read()
    
    # Update email settings
    lines = content.split('\n')
    updated_lines = []
    
    for line in lines:
        if line.startswith('SEND_REAL_EMAILS='):
            updated_lines.append('SEND_REAL_EMAILS=true')
        elif line.startswith('# SMTP_USERNAME='):
            updated_lines.append(f'SMTP_USERNAME={email}')
        elif line.startswith('# SMTP_PASSWORD='):
            updated_lines.append(f'SMTP_PASSWORD={app_password}')
        else:
            updated_lines.append(line)
    
    # Write updated .env file
    with open(env_file, 'w') as f:
        f.write('\n'.join(updated_lines))
    
    print()
    print("✅ Email configuration updated successfully!")
    print("📧 Real emails will now be sent for password reset requests.")
    print()
    print("🔄 Please restart the backend server for changes to take effect:")
    print("   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000")
    print()
    print("🧪 Test the functionality:")
    print("   1. Go to the login page")
    print("   2. Click 'Forgot Password?'")
    print("   3. Enter your email address")
    print("   4. Check your email for the reset link")

if __name__ == "__main__":
    main()