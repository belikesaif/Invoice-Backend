"""
Document processing models for AI/ML pipeline.

This module contains Pydantic models used for document processing including:
- Models for extracted invoice data from OCR/AI processing
- Models for extracted contract data from OCR/AI processing
- Validation and transformation logic for AI-extracted data
"""

from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, Field, validator, root_validator


class DocumentItemModel(BaseModel):
    """Model for individual items extracted from documents."""
    description: str = Field(default="Unknown Item", description="Item description")
    quantity: float = Field(default=1.0, ge=0, description="Item quantity")
    unit_price: float = Field(default=0.0, description="Price per unit (can be negative for credits/discounts)")
    total: Optional[float] = Field(default=None, description="Total price for this item (can be negative for discounts/credits)")

    @validator("quantity", "unit_price", pre=True, always=True)
    def ensure_float(cls, value):
        """Ensure numeric values are properly converted to float."""
        if value is None:
            return 0.0
        try:
            return float(value)
        except (ValueError, TypeError):
            return 0.0

    @root_validator(pre=True)
    def calculate_total_if_missing(cls, values: dict) -> dict:
        """Calculate total from quantity and unit_price if not provided."""
        if values.get("total") is None:
            quantity = values.get("quantity", 0.0)
            unit_price = values.get("unit_price", 0.0)
            
            try:
                q = float(quantity) if quantity is not None else 0.0
                up = float(unit_price) if unit_price is not None else 0.0
                values["total"] = q * up
            except (ValueError, TypeError):
                values["total"] = 0.0
        return values

    class Config:
        validate_assignment = True


class ExtractedInvoiceModel(BaseModel):
    """Model for invoice data extracted from documents by AI/OCR."""
    invoice_number: str = Field(default="Unknown", description="Invoice number")
    supplier_name: str = Field(default="Unknown Supplier", description="Supplier name")
    issue_date: Optional[date] = Field(default_factory=date.today, description="Invoice issue date")
    due_date: Optional[date] = Field(default=None, description="Payment due date")
    items: List[DocumentItemModel] = Field(default_factory=list, description="Invoice line items")
    subtotal: Optional[float] = Field(default=0.0, description="Subtotal amount (can be negative for credit notes)")
    tax: Optional[float] = Field(default=0.0, description="Tax amount (can be negative for credit notes)")
    total: float = Field(default=0.0, description="Total amount (can be negative for credit notes)")
    raw_text: Optional[str] = Field(default="", description="Raw extracted text")

    @validator("issue_date", "due_date", pre=True)
    def parse_date_string(cls, value):
        """Parse date strings into date objects."""
        if isinstance(value, str):
            try:
                return datetime.strptime(value, "%Y-%m-%d").date()
            except ValueError:
                try:
                    # Try alternative date formats
                    return datetime.strptime(value, "%m/%d/%Y").date()
                except ValueError:
                    return None
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        return None

    @validator("subtotal", "tax", "total", pre=True, always=True)
    def ensure_float_amounts(cls, value):
        """Ensure monetary amounts are properly converted to float."""
        if value is None:
            return 0.0
        try:
            return float(value)
        except (ValueError, TypeError):
            return 0.0

    @root_validator(pre=True)
    def set_defaults_for_missing_fields(cls, values: dict) -> dict:
        """Set reasonable defaults for missing fields from AI extraction."""
        # Generate invoice number if missing
        if not values.get("invoice_number"):
            values["invoice_number"] = f"INV-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        # Set default supplier name
        if not values.get("supplier_name"):
            values["supplier_name"] = "Unknown Supplier"
        
        # Set default issue date
        if not values.get("issue_date"):
            values["issue_date"] = date.today().isoformat()
        
        # Process items list
        raw_items = values.get("items")
        if not isinstance(raw_items, list):
            values["items"] = []
        else:
            processed_items = []
            for item in raw_items:
                if isinstance(item, dict):
                    # Ensure required fields have defaults
                    item.setdefault("description", "Unknown Item")
                    item.setdefault("quantity", 1.0)
                    item.setdefault("unit_price", 0.0)
                    processed_items.append(item)
            values["items"] = processed_items
            
        return values

    @root_validator(skip_on_failure=True)
    def calculate_total_from_items_if_needed(cls, values: dict) -> dict:
        """Calculate total from items if total is zero or missing."""
        current_total = values.get("total", 0.0)
        items = values.get("items", [])
        
        # If no total provided, calculate from items
        if current_total == 0.0 and items:
            calculated_total = sum(item.total for item in items if item.total is not None)
            if calculated_total > 0:
                values["total"] = calculated_total
        
        # If no items but have total, create a generic item
        if not items and current_total > 0.0:
            values["items"] = [
                DocumentItemModel(
                    description="Invoice Total",
                    quantity=1.0,
                    unit_price=current_total,
                    total=current_total
                )
            ]
        
        return values

    class Config:
        validate_assignment = True


class ExtractedContractModel(BaseModel):
    """Model for contract data extracted from documents by AI/OCR."""
    supplier_name: str = Field(default="Unknown Supplier", description="Supplier name")
    items: List[DocumentItemModel] = Field(default_factory=list, description="Contract line items")
    effective_date: Optional[date] = Field(default=None, description="Contract effective date")
    expiration_date: Optional[date] = Field(default=None, description="Contract expiration date")
    payment_terms: Optional[str] = Field(default=None, description="Payment terms")
    max_amount: Optional[float] = Field(default=None, ge=0, description="Maximum contract amount")

    @validator("supplier_name", pre=True, always=True)
    def ensure_supplier_name(cls, value):
        """Ensure supplier name is never empty."""
        return value or "Unknown Supplier"

    @validator("effective_date", "expiration_date", pre=True)
    def parse_contract_date(cls, value):
        """Parse date strings into date objects."""
        if isinstance(value, str):
            try:
                return datetime.strptime(value, "%Y-%m-%d").date()
            except ValueError:
                try:
                    return datetime.strptime(value, "%m/%d/%Y").date()
                except ValueError:
                    return None
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        return None

    @validator("max_amount", pre=True)
    def parse_max_amount(cls, value):
        """Parse maximum amount string to float."""
        if value is None:
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None

    @root_validator(pre=True)
    def process_contract_fields(cls, values: dict) -> dict:
        """Process and validate contract fields from AI extraction."""
        # Ensure supplier name
        if not values.get("supplier_name"):
            values["supplier_name"] = "Unknown Supplier"
        
        # Process items
        raw_items = values.get("items")
        if not isinstance(raw_items, list):
            values["items"] = []
        else:
            processed_items = []
            for item in raw_items:
                if isinstance(item, dict):
                    item.setdefault("description", "Contract Item")
                    item.setdefault("quantity", 1.0)
                    item.setdefault("unit_price", 0.0)
                    processed_items.append(item)
            values["items"] = processed_items
        
        return values

    class Config:
        validate_assignment = True


# Legacy alias for backward compatibility
InvoiceItemModel = DocumentItemModel

# Export all models for easy imports
__all__ = [
    "DocumentItemModel", "InvoiceItemModel",  # InvoiceItemModel is alias for backward compatibility
    "ExtractedInvoiceModel", "ExtractedContractModel"
]