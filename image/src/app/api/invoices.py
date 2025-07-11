from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from typing import List, Optional, Union
from datetime import datetime
import uuid
import os
import base64

from ..database import get_db
from ..models import Invoice, Contract, User, InvoiceResponse
from pydantic import BaseModel
from ..services.document_processor import DocumentProcessor
from ..middleware.auth_middleware import get_current_user
from ..config import settings

from loguru import logger

router = APIRouter(prefix="/invoices", tags=["invoices"])

class InvoiceItem(BaseModel):
    file_content: str  # Base64 encoded file content
    file_type: str  # File extension (pdf, jpg, jpeg, png, doc, docx)
    description: Optional[str] = None
    quantity: Optional[float] = None
    unit_price: Optional[float] = None
    total: Optional[float] = None

@router.post("/process")
async def process_invoice(
    invoice_item: InvoiceItem,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Process an invoice from encoded file content."""
    try:
        # Validate input
        if not invoice_item.file_content:
            raise HTTPException(status_code=400, detail="File content is required")
        
        if not invoice_item.file_type:
            raise HTTPException(status_code=400, detail="File type is required")
            
        # Process invoice with file content
        try:
            file_content = base64.b64decode(invoice_item.file_content)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid base64 encoded file content")
        
        # Process invoice to extract data using the DocumentProcessor
        processor = DocumentProcessor()
        stitched_content_bytes = processor.stitch_document(file_content, invoice_item.file_type)
        
        if stitched_content_bytes is None:
            logger.error(f"Failed to stitch document for file type: {invoice_item.file_type}")
            raise HTTPException(status_code=500, detail=f"Failed to process document: Could not convert or stitch file type '{invoice_item.file_type}'")

        # Now, process the stitched PNG image content
        # The file_type for process_invoice_async should now be 'png'
        extracted_invoice_model = await processor.process_invoice_async(stitched_content_bytes, 'png', skip_type_check=True)
        
        if extracted_invoice_model is None:
            logger.error(f"Processing the stitched PNG image returned no data.")
            raise HTTPException(status_code=500, detail="Failed to extract data from the processed document.")
        
        try:
            items_for_db = [item.model_dump() for item in extracted_invoice_model.items]

            db_invoice = Invoice(
                id=str(uuid.uuid4()),
                user_id=current_user.id,
                supplier_name=extracted_invoice_model.supplier_name,
                items=items_for_db,
                document_path=None,
                is_valid=False,
                validation_message=None,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            db.add(db_invoice)
            db.commit()
            db.refresh(db_invoice)
            logger.info(f"Processed invoice data saved to DB with ID: {db_invoice.id}")
            
            return InvoiceResponse(
                id=db_invoice.id,
                user_id=db_invoice.user_id,
                contract_id=db_invoice.contract_id,
                supplier_name=db_invoice.supplier_name,
                items=db_invoice.items,
                document_path=db_invoice.document_path,
                is_valid=db_invoice.is_valid,
                validation_message=db_invoice.validation_message,
                created_at=db_invoice.created_at,
                updated_at=db_invoice.updated_at
            )
            
        except Exception as db_error:
            logger.error(f"Error saving processed invoice to database: {db_error}")
            db.rollback()
            raise HTTPException(status_code=500, detail="Failed to save processed invoice data.")
        
    except ValueError as e:
        logger.error(f"Validation error in process_invoice: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error processing invoice: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/", response_model=dict)
@router.post("", response_model=InvoiceResponse)
async def create_invoice(
    contract_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create and process a new invoice for a specific contract."""
    try:
        # Verify contract exists and belongs to user
        contract = db.query(Contract).filter(Contract.id == contract_id, Contract.user_id == current_user.id).first()
        if not contract:
            raise HTTPException(status_code=404, detail="Contract not found")
        
        # Read file content
        content = await file.read()
        
        # Save file
        file_path = os.path.join(settings.UPLOAD_DIR, file.filename)
        os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
        
        with open(file_path, "wb") as buffer:
            buffer.write(content)
        
        # Process invoice using DocumentProcessor
        processor = DocumentProcessor()
        logger.info(f"Processing invoice file: {file.filename}")
        
        try:
            extracted_data = processor.process_document(content, file.filename)
            
            if extracted_data is None:
                logger.error(f"Failed to extract data from invoice: {file.filename}")
                # Create invoice with default values if extraction fails
                extracted_data_dict = {
                    "supplier_name": "Unknown Supplier",
                    "items": [],
                    "invoice_number": "Unknown",
                    "total": 0.0
                }
            else:
                # Convert extracted data to dict
                extracted_data_dict = {
                    "supplier_name": extracted_data.supplier_name,
                    "items": [item.model_dump() for item in extracted_data.items],
                    "invoice_number": extracted_data.invoice_number,
                    "issue_date": extracted_data.issue_date.isoformat() if extracted_data.issue_date else None,
                    "due_date": extracted_data.due_date.isoformat() if extracted_data.due_date else None,
                    "subtotal": extracted_data.subtotal,
                    "tax": extracted_data.tax,
                    "total": extracted_data.total
                }
                logger.info(f"Successfully extracted invoice data: supplier='{extracted_data.supplier_name}', items={len(extracted_data.items)}, total={extracted_data.total}")
        
        except Exception as processing_error:
            logger.error(f"Error processing invoice {file.filename}: {processing_error}")
            # Create invoice with default values if processing fails
            extracted_data_dict = {
                "supplier_name": "Processing Failed",
                "items": [],
                "invoice_number": "Unknown",
                "total": 0.0
            }
        
        # Create invoice record with extracted data
        invoice = Invoice(
            id=str(uuid.uuid4()),
            user_id=current_user.id,
            contract_id=contract_id,
            supplier_name=extracted_data_dict["supplier_name"],
            document_path=file_path,
            items=extracted_data_dict["items"],
            is_valid=False,  # User needs to validate the extracted data
            validation_message="Please review and validate the extracted data",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        db.add(invoice)
        db.commit()
        db.refresh(invoice)
        
        logger.info(f"Created invoice with ID: {invoice.id}")
        
        # Return full invoice response with extracted data
        return InvoiceResponse(
            id=invoice.id,
            user_id=invoice.user_id,
            contract_id=invoice.contract_id,
            supplier_name=invoice.supplier_name,
            items=invoice.items,
            document_path=invoice.document_path,
            is_valid=invoice.is_valid,
            validation_message=invoice.validation_message,
            created_at=invoice.created_at,
            updated_at=invoice.updated_at
        )
        
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error creating invoice: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create invoice: {str(e)}")

@router.get("/", response_model=List[InvoiceResponse])
@router.get("", response_model=List[InvoiceResponse])
async def get_invoices(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Get all invoices for the current user with their processed data."""
    invoices = db.query(Invoice).filter(Invoice.user_id == current_user.id).order_by(Invoice.created_at.desc()).all()
    
    results = []
    for invoice in invoices:
        results.append(
            InvoiceResponse(
                id=invoice.id,
                user_id=invoice.user_id,
                contract_id=invoice.contract_id,
                supplier_name=invoice.supplier_name,
                items=invoice.items,
                document_path=invoice.document_path,
                is_valid=invoice.is_valid,
                validation_message=invoice.validation_message,
                created_at=invoice.created_at,
                updated_at=invoice.updated_at
            )
        )
    return results

@router.delete("/clear-all")
async def clear_all_invoices(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Clear all invoices for the current user."""
    try:
        # Get all invoices for the user
        invoices = db.query(Invoice).filter(Invoice.user_id == current_user.id).all()
        
        # Delete all invoices
        for invoice in invoices:
            # Clean up any associated files if they exist
            if invoice.document_path and os.path.exists(invoice.document_path):
                try:
                    os.remove(invoice.document_path)
                    logger.info(f"Deleted associated file: {invoice.document_path} for invoice ID: {invoice.id}")
                except Exception as file_error:
                    logger.warning(f"Could not delete file {invoice.document_path}: {str(file_error)}")
            
            db.delete(invoice)
        
        db.commit()
        
        logger.info(f"Cleared {len(invoices)} invoices for user {current_user.id}")
        return {"message": f"Successfully cleared {len(invoices)} invoices"}
        
    except Exception as e:
        logger.error(f"Error clearing all invoices for user {current_user.id}: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to clear invoices")

@router.get("/{invoice_id}", response_model=InvoiceResponse)
async def get_invoice(invoice_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Get a specific invoice by ID for the current user."""
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id, Invoice.user_id == current_user.id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    
    return InvoiceResponse(
        id=invoice.id,
        user_id=invoice.user_id,
        contract_id=invoice.contract_id,
        supplier_name=invoice.supplier_name,
        items=invoice.items,
        document_path=invoice.document_path,
        is_valid=invoice.is_valid,
        validation_message=invoice.validation_message,
        created_at=invoice.created_at,
        updated_at=invoice.updated_at
    )

@router.delete("/{invoice_id}")
async def delete_invoice(invoice_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Delete an invoice by ID for the current user."""
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id, Invoice.user_id == current_user.id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    
    try:
        if invoice.document_path and os.path.exists(invoice.document_path):
            os.remove(invoice.document_path)
            logger.info(f"Deleted associated file: {invoice.document_path} for invoice ID: {invoice_id}")
        elif invoice.document_path:
            logger.warning(f"File path {invoice.document_path} for invoice ID: {invoice_id} was set but file not found.")
        else:
            logger.info(f"No file path associated with invoice ID: {invoice_id}. No file to delete.")
        
        db.delete(invoice)
        db.commit()
        
        return {"message": "Invoice deleted successfully"}
    except Exception as e:
        logger.error(f"Error deleting invoice: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/process-example")
async def process_invoice_example():
    """
    Example endpoint demonstrating how to process an invoice with base64 encoding.
    """
    return {
        "expected_request_format": {
            "file_content": "base64_encoded_file_content",
            "file_type": "pdf"
        },
        "note": "For actual processing, send this format to the /process endpoint"
    }