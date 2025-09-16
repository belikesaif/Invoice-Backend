from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from pathlib import Path
import uuid
import os
import json
from pydantic import ValidationError

from ..database import get_db
from ..models import Contract, User, ContractCreate, ContractResponse, InvoiceItemModel
from ..services.document_processor import DocumentProcessor
from ..services.s3_service import s3_service
from ..middleware.auth_middleware import get_current_user
from ..config import settings

from loguru import logger

router = APIRouter(prefix="/contracts", tags=["contracts"])

@router.get("/", response_model=List[ContractResponse])
@router.get("", response_model=List[ContractResponse])
async def get_contracts(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Get all contracts for the current user."""
    try:
        contracts = db.query(Contract).filter(Contract.user_id == current_user.id).all()
        return contracts
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to retrieve contracts")

@router.delete("/clear-all")
async def clear_all_contracts(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Clear all contracts for the current user."""
    try:
        # Get all contracts for the user
        contracts = db.query(Contract).filter(Contract.user_id == current_user.id).all()
        
        # Delete all contracts
        for contract in contracts:
            # Clean up any associated files if they exist
            if contract.document_path:
                try:
                    if contract.document_path.startswith('s3://') or contract.document_path.startswith('uploads/'):
                        # S3 file path
                        s3_key = contract.document_path.replace('s3://', '').split('/', 1)[-1] if contract.document_path.startswith('s3://') else contract.document_path
                        success = s3_service.delete_file(s3_key)
                        if not success:
                            pass
                    else:
                        # Local file path
                        local_path = Path(contract.document_path)
                        if local_path.exists():
                            local_path.unlink()
                except Exception as file_error:
                    pass
            
            db.delete(contract)
        
        db.commit()
        
        return {"message": f"Successfully cleared {len(contracts)} contracts"}
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to clear contracts")

@router.get("/{contract_id}", response_model=ContractResponse)
async def get_contract(contract_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Get a specific contract by ID for the current user."""
    contract = db.query(Contract).filter(Contract.id == contract_id, Contract.user_id == current_user.id).first()
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")
    return contract

@router.post("/", response_model=ContractResponse, status_code=201)
@router.post("", response_model=ContractResponse)
async def create_contract(
    contract_data: ContractCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new contract."""
    try:
        # Convert Pydantic items to dict for JSON storage
        items_for_db = [item.model_dump() for item in contract_data.items]

        contract = Contract(
            id=str(uuid.uuid4()),
            user_id=current_user.id,
            supplier_name=contract_data.supplier_name,
            items=items_for_db, # Store as list of dicts
            document_path=contract_data.document_path,
            is_manual=contract_data.is_manual,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        db.add(contract)
        db.commit()
        db.refresh(contract)
        
        return contract
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/upload", response_model=ContractResponse, status_code=201)
async def upload_contract(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Upload a contract file and process it."""
    try:
        logger.info(f"Starting contract upload for user {current_user.id}")
        
        # Validate file exists and has name
        if not file or not file.filename:
            raise HTTPException(status_code=400, detail="No file provided or file has no name")
        
        original_file_name = file.filename
        logger.info(f"Processing contract file: {original_file_name}")
        
        # Normalize file extension check (remove dot, lowercase)
        file_ext_from_upload = os.path.splitext(original_file_name)[1].lower().lstrip('.')
        logger.info(f"File extension: {file_ext_from_upload}")
        
        # Validate file size (max 500KB for invoice validation projects)
        content = await file.read()
        file_size = len(content)
        logger.info(f"File size: {file_size} bytes")
        
        max_size = 500 * 1024  # 500KB
        if file_size > max_size:
            raise HTTPException(
                status_code=400,
                detail=f"File size ({file_size/1024:.1f}KB) exceeds maximum allowed size of 500KB. Please compress your PDF or use a smaller file."
            )
        
        # Use settings.ALLOWED_EXTENSIONS which is now a list of strings without dots
        logger.info(f"Checking file extension '{file_ext_from_upload}' against allowed: {settings.ALLOWED_EXTENSIONS}")
        if file_ext_from_upload not in settings.ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400, 
                detail=f"File type '{file_ext_from_upload}' not allowed. Allowed types: {', '.join(settings.ALLOWED_EXTENSIONS)}"
            )
        
        # Handle file storage based on configuration
        try:
            logger.info(f"Storage configuration: use_s3_storage={settings.use_s3_storage}")
            
            if settings.use_s3_storage:
                logger.info("Uploading file to S3...")
                # Check if S3 service is properly configured
                if not hasattr(s3_service, 'upload_file'):
                    logger.error("S3 service not properly initialized")
                    raise HTTPException(
                        status_code=500, 
                        detail="S3 storage is configured but service is not available. Please check AWS credentials."
                    )
                
                # Upload to S3
                s3_key = s3_service.upload_file(content, original_file_name, file.content_type)
                if not s3_key:
                    raise HTTPException(status_code=500, detail="Failed to upload file to S3")
                file_path = s3_key  # Store S3 key as file path
                logger.info(f"File uploaded to S3: {s3_key}")
            else:
                # Save locally
                logger.info(f"Saving file locally to: {settings.UPLOAD_DIR}")
                os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
                file_path = os.path.join(settings.UPLOAD_DIR, original_file_name)
                with open(file_path, "wb") as f:
                    f.write(content)
                logger.info(f"File saved locally: {file_path}")
        except HTTPException:
            # Re-raise HTTP exceptions as-is
            raise
        except Exception as storage_error:
            logger.error(f"File storage error: {str(storage_error)}")
            error_msg = str(storage_error)
            
            # Provide more helpful error messages for common issues
            if "credentials" in error_msg.lower():
                error_msg = "AWS credentials not found. For local development, files will be stored locally instead of S3."
                logger.info("Falling back to local storage due to missing AWS credentials")
                
                # Try local storage as fallback
                try:
                    logger.info(f"Attempting local storage fallback to: {settings.UPLOAD_DIR}")
                    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
                    file_path = os.path.join(settings.UPLOAD_DIR, original_file_name)
                    with open(file_path, "wb") as f:
                        f.write(content)
                    logger.info(f"File saved locally as fallback: {file_path}")
                except Exception as fallback_error:
                    logger.error(f"Local storage fallback also failed: {str(fallback_error)}")
                    raise HTTPException(
                        status_code=500, 
                        detail=f"Both S3 and local storage failed. S3 error: {error_msg}, Local error: {str(fallback_error)}"
                    )
            else:
                raise HTTPException(status_code=500, detail=f"Failed to store file: {error_msg}")
        
        # Process the document
        try:
            logger.info("Initializing DocumentProcessor...")
            processor = DocumentProcessor()
            
            logger.info(f"Processing contract document: {original_file_name}")
            extracted_data_model = processor.process_contract(content, original_file_name)
            
            if extracted_data_model is None:
                logger.error(f"Document processing returned None for file: {original_file_name}")
                raise HTTPException(
                    status_code=400, 
                    detail=f"Failed to process contract file '{original_file_name}'. Document processing returned no data. Please check if the file is valid and contains contract information."
                )
            
            logger.info(f"Successfully processed contract, extracted supplier: {extracted_data_model.supplier_name}")
            
        except ValidationError as validation_error:
            logger.error(f"Validation error during document processing: {str(validation_error)}")
            raise HTTPException(
                status_code=400,
                detail=f"Document validation failed: {str(validation_error)}"
            )
        except Exception as processing_error:
            logger.error(f"Document processing error: {str(processing_error)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to process document: {str(processing_error)}"
            )
        
        # Extract data and prepare for database
        supplier_name = extracted_data_model.supplier_name or "Unknown Supplier"
        extracted_items = extracted_data_model.items
        
        # Convert List[InvoiceItemModel from Pydantic model] to List[dict for DB]
        items_for_db = [item.model_dump() for item in extracted_items]
        logger.info(f"Extracted {len(items_for_db)} items from contract")

        if not items_for_db:
            logger.warning("No items extracted from contract, but proceeding with empty items list")
        
        # Save to database
        try:
            contract_id_val = str(uuid.uuid4())
            logger.info(f"Creating contract with ID: {contract_id_val}")
            
            db_contract = Contract(
                id=contract_id_val,
                user_id=current_user.id,
                supplier_name=supplier_name,
                items=items_for_db,
                document_path=file_path, # Save the path where the file is stored
                is_manual=False, # This contract is from an upload
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            
            db.add(db_contract)
            db.commit()
            db.refresh(db_contract)
            
            logger.info(f"Successfully created contract {contract_id_val} for user {current_user.id}")
            return db_contract
            
        except Exception as db_error:
            logger.error(f"Database error: {str(db_error)}")
            db.rollback()
            raise HTTPException(
                status_code=500,
                detail=f"Failed to save contract to database: {str(db_error)}"
            )
        
    except HTTPException as http_exc:
        # Re-raise HTTPException to ensure FastAPI handles it correctly
        logger.error(f"HTTP Exception during contract upload: {http_exc.detail}")
        raise http_exc
    except Exception as e:
        logger.error(f"Unexpected error during contract upload: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error during contract upload: {str(e)}")

@router.delete("/{contract_id}")
async def delete_contract(contract_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Delete a contract by ID for the current user."""
    contract = db.query(Contract).filter(Contract.id == contract_id, Contract.user_id == current_user.id).first()
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")
    
    try:
        # Delete the associated file
        if contract.document_path:
            try:
                if settings.use_s3_storage:
                    # Delete from S3
                    s3_service.delete_file(contract.document_path)
                else:
                    # Delete local file
                    if os.path.exists(contract.document_path):
                        os.remove(contract.document_path)
            except Exception as e_file_delete:
                # Log error but don't prevent contract deletion
                pass

        db.delete(contract)
        db.commit()
        return {"message": "Contract deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.put("/{contract_id}", response_model=ContractResponse)
async def update_contract(
    contract_id: str,
    contract_data: ContractCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update an existing contract for the current user."""
    contract = db.query(Contract).filter(Contract.id == contract_id, Contract.user_id == current_user.id).first()
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")
    
    try:
        contract.supplier_name = contract_data.supplier_name
        contract.items = [item.model_dump() for item in contract_data.items] # Ensure items are dicts for JSON
        contract.document_path = contract_data.document_path # Allow updating path
        contract.is_manual = contract_data.is_manual # Allow updating manual flag
        contract.updated_at = datetime.utcnow()
        
        db.commit()
        db.refresh(contract)
        
        return contract
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))