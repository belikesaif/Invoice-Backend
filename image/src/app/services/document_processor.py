import os
import json
from typing import Dict, Optional, List, Tuple, Any
from datetime import date, datetime
import google.genai as genai
from google.genai import types
import fitz  # PyMuPDF
from PIL import Image
from pathlib import Path
import io
from loguru import logger
from pydantic import ValidationError
from ..config import settings
from ..models import (
    ExtractedInvoiceModel,
    ExtractedContractModel,
)
from .constants import (
    UNIVERSAL_SUPPLIER_ITEM_EXTRACTION_PROMPT,
    CONTRACT_ANALYSIS_PROMPT_DETAILED,
    SUPPORTED_DOCUMENT_FILE_TYPES,
    SUPPORTED_INVOICE_FILE_TYPES
)
from ..utils.hyphen_normalizer import normalize_hyphens

# Configure Gemini
client = genai.Client(
        api_key=settings.GEMINI_API_KEY,
    )
model = settings.GEMINI_MODEL
generate_content_config = types.GenerateContentConfig(
        temperature=0.3,
        response_mime_type="text/plain",
    )

class DocumentProcessor:
    """Process and extract data from invoice and contract documents."""
    
    def __init__(self):
        self.model = model
        logger.info("DocumentProcessor initialized with Gemini model")
    
    def process_document(self, file_content: bytes, file_name: str) -> Optional[ExtractedInvoiceModel]:
        """
        Process an invoice document file and extract its data.
        Now primarily uses UNIVERSAL_SUPPLIER_ITEM_EXTRACTION_PROMPT.
        
        Args:
            file_content: The binary content of the file
            file_name: The name of the file
            
        Returns:
            Extracted data as an ExtractedInvoiceModel or None if an error occurs.
        """
        logger.info(f"Processing invoice document: {file_name}")        
        file_ext = Path(file_name).suffix.lower().lstrip('.')
        logger.debug(f"[Invoice] Derived file_ext: '{file_ext}'")
        logger.debug(f"[Invoice] SUPPORTED_DOCUMENT_FILE_TYPES: {SUPPORTED_DOCUMENT_FILE_TYPES}")

        if file_ext not in SUPPORTED_DOCUMENT_FILE_TYPES:
            logger.error(f"Unsupported file format for invoice: {file_name}. (Checked '{file_ext}' against {SUPPORTED_DOCUMENT_FILE_TYPES})")
            return None

        image_bytes_to_process: Optional[bytes] = None
        try:
            if file_ext == 'pdf': # Extension without dot
                logger.info("Converting PDF to image for invoice processing")
                images = self._convert_pdf_to_images(file_content)
                if not images:
                    logger.error("Failed to convert PDF to images for invoice")
                    return None
                stitched_image_bytes = self.stitch_document_content(images)
                if not stitched_image_bytes:
                    logger.error("Failed to stitch PDF pages for invoice processing, falling back to first page")
                    image_bytes_to_process = self._get_image_bytes(images[0])
                else:
                    image_bytes_to_process = stitched_image_bytes
            
            elif file_ext in ['jpg', 'jpeg', 'png']: # Extensions without dot
                logger.info("Using image file directly for invoice processing")
                image_bytes_to_process = file_content
            
            if not image_bytes_to_process:
                logger.error("No image content available for invoice data extraction")
                return None

            return self._extract_invoice_data_from_image_bytes(image_bytes_to_process, file_name)
            
        except Exception as e:
            logger.error(f"Error processing invoice document ({file_name}): {str(e)}")
            return None
    
    def process_contract(self, file_content: bytes, file_name: str) -> Optional[ExtractedContractModel]:
        """
        Process a contract document file and extract services and supplier information.
        Uses UNIVERSAL_SUPPLIER_ITEM_EXTRACTION_PROMPT.
        
        Args:
            file_content: The binary content of the file
            file_name: The name of the file
            
        Returns:
            Extracted contract data as ExtractedContractModel or None if an error occurs.
        """
        logger.info(f"Processing contract document: {file_name}")
        file_ext = Path(file_name).suffix.lower().lstrip('.')
        logger.debug(f"[Contract] Derived file_ext: '{file_ext}'")
        logger.debug(f"[Contract] SUPPORTED_DOCUMENT_FILE_TYPES: {SUPPORTED_DOCUMENT_FILE_TYPES}")

        if file_ext not in SUPPORTED_DOCUMENT_FILE_TYPES:
            logger.error(f"Unsupported contract file format: {file_name}. (Checked '{file_ext}' against {SUPPORTED_DOCUMENT_FILE_TYPES})")
            return None

        image_bytes_to_process: Optional[bytes] = None
        try:
            if file_ext == 'pdf': # Extension without dot
                logger.info("Converting contract PDF to images")
                images = self._convert_pdf_to_images(file_content)
                if not images:
                    logger.error("Failed to convert contract PDF to images")
                    return None

                stitched_image_bytes = self.stitch_document_content(images)
                if not stitched_image_bytes:
                    logger.error("Failed to stitch PDF pages for contract processing")
                    return None
                image_bytes_to_process = stitched_image_bytes

            elif file_ext in ['jpg', 'jpeg', 'png']: # Extensions without dot
                logger.info("Processing contract image file directly")
                image_bytes_to_process = file_content
            
            else: 
                logger.error(f"Logic error or unhandled supported type in process_contract: {file_ext}")
                return None

            if not image_bytes_to_process:
                logger.error("No image content available for contract data extraction. This might be due to an issue in PDF conversion or image handling for supported types.")
                return None

            return self._extract_contract_data_from_image_bytes(image_bytes_to_process, file_name)

        except ValidationError as ve:
            logger.error(f"Pydantic validation error processing contract ({file_name}): {ve}")
            return None
        except Exception as e:
            logger.error(f"Error processing contract document ({file_name}): {str(e)}")
            return None
    
    def _convert_pdf_to_images(self, pdf_bytes: bytes) -> List[Image.Image]:
        """Convert PDF bytes to a list of PIL Images using PyMuPDF."""
        try:
            # Open the PDF from bytes
            pdf_document = fitz.open(stream=pdf_bytes, filetype="pdf")
            images = []
            
            for page_num in range(len(pdf_document)):
                # Get the page
                page = pdf_document.load_page(page_num)
                
                # Convert page to image with high resolution
                mat = fitz.Matrix(2.0, 2.0)  # Scale factor for higher resolution
                pix = page.get_pixmap(matrix=mat)
                
                # Convert to PIL Image
                img_data = pix.tobytes("png")
                img = Image.open(io.BytesIO(img_data))
                images.append(img)
            
            pdf_document.close()
            logger.info(f"Successfully converted PDF to {len(images)} images using PyMuPDF")
            return images
        except Exception as e:
            logger.error(f"PDF conversion error with PyMuPDF: {str(e)}")
            return []
    
    def _get_image_bytes(self, image: Image.Image) -> Optional[bytes]:
        """Convert PIL Image to bytes."""
        try:
            img_byte_arr = io.BytesIO()
            image.save(img_byte_arr, format='PNG')
            return img_byte_arr.getvalue()
        except Exception as e:
            logger.error(f"Image conversion error: {str(e)}")
            return None
    
    def _parse_gemini_json_response(self, response_text: str) -> Optional[Any]:
        """Helper to parse JSON from Gemini's response text."""
        text = response_text.strip()
        logger.debug(f"Original response text: {text[:1000]}...")
        
        if text.startswith("```json"):
            text = text[len("```json"):].strip()
            if text.endswith("```"):
                text = text[:-len("```")].strip()
            logger.debug(f"Extracted from json markdown: {text[:500]}...")
        elif text.startswith("```"):
             text = text[len("```"):].strip()
             if text.endswith("```"):
                text = text[:-len("```")].strip()
             logger.debug(f"Extracted from generic markdown: {text[:500]}...")
        
        parsed_data = None
        if text:
            try:
                first_char = text.lstrip()[0] if text.lstrip() else ''
                logger.debug(f"First character after stripping: '{first_char}'")
                
                if first_char == '{' or first_char == '[':
                    parsed_data = json.loads(text)
                    logger.info(f"Successfully parsed JSON response")
                else:
                    logger.warning(f"Response text after markdown stripping does not start with '{{' or '['. Attempting parse anyway. Content: '{text[:500]}'")
                    parsed_data = json.loads(text)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON directly from response: {e}. Content: '{text[:500]}'")
                
                # Try to extract JSON from within the text
                try:
                    # Look for JSON object starting with {
                    start_idx = text.find('{')
                    if start_idx != -1:
                        # Find the matching closing brace
                        brace_count = 0
                        end_idx = start_idx
                        for i, char in enumerate(text[start_idx:], start_idx):
                            if char == '{':
                                brace_count += 1
                            elif char == '}':
                                brace_count -= 1
                                if brace_count == 0:
                                    end_idx = i + 1
                                    break
                        
                        json_text = text[start_idx:end_idx]
                        logger.info(f"Attempting to parse extracted JSON: {json_text[:200]}...")
                        parsed_data = json.loads(json_text)
                        logger.info(f"Successfully parsed extracted JSON")
                except json.JSONDecodeError as e2:
                    logger.error(f"Failed to parse extracted JSON: {e2}")
                except Exception as e_gen:
                    logger.error(f"Error during JSON extraction: {e_gen}")
            except Exception as e_gen:
                logger.error(f"Unexpected error during JSON parsing: {e_gen}. Content: '{text[:500]}'")

        if parsed_data is None:
             logger.warning(f"Could not parse any valid JSON from response after all attempts. Original content snippet: '{response_text[:500]}'")
        else:
            logger.info(f"Final parsed data: {json.dumps(parsed_data, indent=2)[:500]}...")
        return parsed_data

    def _extract_invoice_data_from_image_bytes(self, image_bytes: bytes, original_filename: str) -> Optional[ExtractedInvoiceModel]:
        """Extract invoice data from image bytes using Gemini and parse with Pydantic."""
        try:
            logger.info(f"Sending invoice image ('{original_filename}') to Gemini for extraction.")
            
            contents = [
                types.Content(
                    role="user",
                    parts=[
                        types.Part.from_bytes(
                            mime_type="image/png",
                            data=image_bytes
                        ),
                        types.Part.from_text(text=UNIVERSAL_SUPPLIER_ITEM_EXTRACTION_PROMPT),
                    ],
                ),
            ]

            response = client.models.generate_content(
                model=self.model,
                contents=contents,
                config=generate_content_config
            )
            
            raw_data = self._parse_gemini_json_response(response.text)
            if raw_data and isinstance(raw_data, dict):
                if "raw_text" not in raw_data:
                     raw_data["raw_text"] = response.text[:1000] 
                
                if "items" not in raw_data or not isinstance(raw_data.get("items"), list):
                    raw_data["items"] = []
                if "supplier_name" not in raw_data:
                    raw_data["supplier_name"] = "Unknown Supplier"

                # Normalize hyphens in all item descriptions
                for item in raw_data["items"]:
                    if isinstance(item, dict) and "description" in item and isinstance(item["description"], str):
                        item["description"] = normalize_hyphens(item["description"])

                return ExtractedInvoiceModel.model_validate(raw_data)
            else:
                logger.warning(f"Could not parse valid dict for invoice from Gemini ('{original_filename}'). Raw: {response.text[:500]}")
                return ExtractedInvoiceModel(raw_text=response.text, supplier_name="Unknown Supplier", items=[])

        except ValidationError as ve:
            logger.error(f"Pydantic validation error for invoice ('{original_filename}'): {ve}")
            return ExtractedInvoiceModel(raw_text=str(ve), supplier_name="Unknown Supplier", items=[])
        except Exception as e:
            logger.error(f"Gemini invoice data extraction error ('{original_filename}'): {str(e)}")
            return ExtractedInvoiceModel(raw_text=f"Extraction error: {str(e)}", supplier_name="Unknown Supplier", items=[])
            
    def _extract_contract_data_from_image_bytes(self, image_bytes: bytes, original_filename: str) -> Optional[ExtractedContractModel]:
        """Extract contract data from image bytes using Gemini with contract-specific prompt, returns Pydantic model."""
        try:
            logger.info(f"Sending contract image ('{original_filename}') to Gemini for contract-specific extraction.")
            
            contents = [
                types.Content(
                    role="user",
                    parts=[
                        types.Part.from_bytes(
                            mime_type="image/png",
                            data=image_bytes
                        ),
                        types.Part.from_text(text=CONTRACT_ANALYSIS_PROMPT_DETAILED),
                    ],
                ),
            ]

            response = client.models.generate_content(
                model=self.model,
                contents=contents,
                config=generate_content_config
            )
            
            logger.info(f"Gemini response for contract '{original_filename}': {response.text}")
            
            raw_data = self._parse_gemini_json_response(response.text)
            logger.info(f"Parsed raw data for contract '{original_filename}': {raw_data}")
            
            if raw_data and isinstance(raw_data, dict):
                # Extract supplier name from contract-specific fields
                supplier_name = raw_data.get("supplier_name")
                logger.info(f"Extracted supplier_name: '{supplier_name}'")
                
                # Extract items from contract data - may come from 'items' field
                items_data = raw_data.get("items", [])
                if not isinstance(items_data, list):
                    items_data = []
                
                logger.info(f"Extracted items from 'items' field: {len(items_data)} items")
                
                # If no items found in 'items' field, try to create items from other contract data
                if not items_data:
                    logger.info("No items in 'items' field, trying to create from other contract data...")
                    # Try to create items from scope of work or contract value
                    scope_summary = raw_data.get("scope_of_work_summary")
                    total_value = raw_data.get("total_contract_value")
                    
                    logger.info(f"scope_of_work_summary: '{scope_summary}'")
                    logger.info(f"total_contract_value: {total_value}")
                    
                    if scope_summary:
                        item = {
                            "description": scope_summary,
                            "quantity": 1.0,
                            "unit_price": total_value if total_value else 0.0,
                            "total": total_value if total_value else 0.0
                        }
                        items_data = [item]
                        logger.info(f"Created item from scope_of_work_summary: {item}")
                
                # Normalize hyphens in all item descriptions
                for item in items_data:
                    if isinstance(item, dict) and "description" in item and isinstance(item["description"], str):
                        item["description"] = normalize_hyphens(item["description"])
                
                # Create the contract model with all extracted data
                contract_data = {
                    "supplier_name": supplier_name,
                    "items": items_data,
                    # Include additional contract fields from extraction
                    "effective_date": raw_data.get("effective_date"),
                    "expiration_date": raw_data.get("expiration_date"),
                    "payment_terms": raw_data.get("payment_terms"),
                    "max_amount": raw_data.get("total_contract_value") or raw_data.get("max_amount")
                }
                
                logger.info(f"Final contract data for '{original_filename}': supplier='{supplier_name}', items_count={len(items_data)}, effective_date={contract_data.get('effective_date')}, payment_terms='{contract_data.get('payment_terms')}'")
                
                try:
                    validated_model = ExtractedContractModel.model_validate(contract_data)
                    logger.info(f"Successfully validated contract model for '{original_filename}'")
                    return validated_model
                except Exception as validation_error:
                    logger.error(f"Validation error for contract '{original_filename}': {validation_error}")
                    return ExtractedContractModel(supplier_name=supplier_name or "Unknown Supplier", items=items_data)
                
            else:
                logger.warning(f"Could not parse valid dict for contract from Gemini ('{original_filename}'). Raw response: {response.text}")
                return ExtractedContractModel(supplier_name="Unknown Supplier", items=[])

        except ValidationError as ve:
            logger.error(f"Pydantic validation error for contract ('{original_filename}'): {ve}")
            return ExtractedContractModel(supplier_name="Unknown Supplier", items=[])
        except Exception as e:
            logger.error(f"Gemini contract data extraction error ('{original_filename}'): {str(e)}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
            return ExtractedContractModel(supplier_name="Unknown Supplier", items=[])
    
    def stitch_document_content(self, images: List[Image.Image]) -> Optional[bytes]:
        """Stitches a list of PIL Images into a single vertically stitched PNG image bytes."""
        if not images:
            logger.warning("No images provided for stitching.")
            return None
        
        if len(images) == 1:
            logger.info("Only one image provided, converting to PNG directly.")
            return self._get_image_bytes(images[0])

        logger.info(f"Stitching {len(images)} image pages.")
        rgb_images = []
        for img in images:
            if img.mode == 'RGBA':
                background = Image.new('RGB', img.size, (255, 255, 255))
                background.paste(img, mask=img.split()[3])
                rgb_images.append(background)
            elif img.mode == 'P' or img.mode != 'RGB':
                rgb_images.append(img.convert('RGB'))
            else:
                rgb_images.append(img)
        
        max_width = max(img.width for img in rgb_images)
        total_height = sum(img.height for img in rgb_images)
        
        stitched_image = Image.new('RGB', (max_width, total_height), (255, 255, 255))
        current_y = 0
        for img in rgb_images:
            stitched_image.paste(img, (0, current_y))
            current_y += img.height
        
        return self._get_image_bytes(stitched_image)
    
    def stitch_document(self, file_content: bytes, file_type: str) -> Optional[bytes]:
        """
        Convert a document (PDF or image) to a single vertically stitched PNG image.
        If it's a PDF, all pages are stitched together.
        If it's an image, it's converted to PNG format (if not already PNG).

        Args:
            file_content: The binary content of the file.
            file_type: The type of the file (e.g., 'pdf', 'jpg', 'png').

        Returns:
            Bytes of the single PNG image, or None if an error occurs.
        """
        logger.info(f"Stitching document of type: {file_type}")
        normalized_file_type = file_type.lower().lstrip('.')

        if normalized_file_type == 'pdf':
            try:
                images = self._convert_pdf_to_images(file_content)
                if not images:
                    logger.error("PDF conversion yielded no images for stitching.")
                    return None
                return self.stitch_document_content(images)
            except Exception as e:
                logger.error(f"Error stitching PDF document: {str(e)}")
                return None
                
        elif normalized_file_type in ['jpg', 'jpeg', 'png']:
            logger.info(f"Converting image file type '{normalized_file_type}' to standardized PNG bytes for consistency.")
            try:
                image = Image.open(io.BytesIO(file_content))
                if image.mode == 'RGBA':
                    background = Image.new('RGB', image.size, (255, 255, 255))
                    background.paste(image, mask=image.split()[3])
                    image = background
                elif image.mode == 'P' or image.mode != 'RGB': 
                    image = image.convert('RGB')
                return self._get_image_bytes(image)
            except Exception as e:
                logger.error(f"Error standardizing image '{normalized_file_type}' to PNG: {str(e)}")
                return None
        else:
            logger.error(f"Unsupported file type for stitching: {normalized_file_type}")
            return None

    # --- Async Methods --- 
    async def process_invoice_async(self, file_content: bytes, file_type: str, file_name: str = "unknown_invoice_async", skip_type_check: bool = False) -> Optional[ExtractedInvoiceModel]:
        """Async process an invoice file and extract relevant information using Pydantic."""
        logger.info(f"Async processing invoice file '{file_name}' of type: {file_type}")
        if not file_content:
            logger.error(f"Empty file content provided for async invoice: {file_name}")
            return None
        
        file_type_lower = file_type.lower().lstrip('.')
        logger.debug(f"[Async Invoice] Normalized file_type_lower: '{file_type_lower}'")
        logger.debug(f"[Async Invoice] SUPPORTED_INVOICE_FILE_TYPES: {SUPPORTED_INVOICE_FILE_TYPES}")
        logger.debug(f"[Async Invoice] skip_type_check: {skip_type_check}")

        if not skip_type_check and file_type_lower not in SUPPORTED_INVOICE_FILE_TYPES:
            logger.error(f"Unsupported file type for async invoice '{file_name}': '{file_type_lower}'. (Checked against {SUPPORTED_INVOICE_FILE_TYPES})")
            return None

        image_bytes_to_process: Optional[bytes] = None
        try:
            # If called with a PDF, it needs conversion. If called with PNG (from stitching), it's processed directly.
            if file_type_lower == 'pdf':
                images = self._convert_pdf_to_images(file_content)
                if not images:
                    logger.error(f"Could not extract images from PDF for async invoice: {file_name}")
                    return None
                stitched_bytes = self.stitch_document_content(images)
                if not stitched_bytes:
                    logger.error(f"Failed to stitch PDF for async invoice {file_name}, falling back to first page.")
                    image_bytes_to_process = self._get_image_bytes(images[0])
                else:
                    image_bytes_to_process = stitched_bytes
            elif file_type_lower in ['jpg', 'jpeg', 'png']:
                # This branch is hit when process_invoice_async is called with a stitched PNG,
                # or if the original upload was an image.
                image_bytes_to_process = file_content
            else:
                # This should ideally not be reached if skip_type_check is True for internal PNGs
                # and the initial check catches unsupported user uploads.
                logger.error(f"Logic error or unhandled supported type in process_invoice_async: {file_type_lower}")
                return None 

            if not image_bytes_to_process:
                logger.error(f"No image could be prepared for Gemini async invoice processing: {file_name}")
                return None

            return self._extract_invoice_data_from_image_bytes(image_bytes_to_process, file_name)

        except ValidationError as ve:
            logger.error(f"Pydantic validation error during async invoice processing ('{file_name}'): {ve}")
            return ExtractedInvoiceModel(raw_text=f"Validation Error: {str(ve)}", supplier_name="Unknown Supplier", items=[])
        except Exception as e:
            logger.error(f"Error processing invoice async ('{file_name}'): {str(e)}")
            return ExtractedInvoiceModel(raw_text=f"Processing Error: {str(e)}", supplier_name="Unknown Supplier", items=[])

    async def process_contract_async(self, file_content: bytes, file_type: str, file_name: str = "unknown_contract_async", skip_type_check: bool = False) -> Optional[ExtractedContractModel]:
        """Async process a contract file and extract relevant information."""
        logger.info(f"Async processing contract file '{file_name}' of type: {file_type}")

        if not file_content:
            logger.error(f"Empty file content for async contract: {file_name}")
            return None
        
        file_type_lower = file_type.lower().lstrip('.')
        logger.debug(f"[Async Contract] Normalized file_type_lower: '{file_type_lower}'")
        logger.debug(f"[Async Contract] SUPPORTED_DOCUMENT_FILE_TYPES: {SUPPORTED_DOCUMENT_FILE_TYPES}")
        logger.debug(f"[Async Contract] skip_type_check: {skip_type_check}")

        if not skip_type_check and file_type_lower not in SUPPORTED_DOCUMENT_FILE_TYPES:
            logger.error(f"Unsupported file type for async contract '{file_name}': '{file_type_lower}'. (Checked against {SUPPORTED_DOCUMENT_FILE_TYPES})")
            return None

        image_bytes_to_process: Optional[bytes] = None
        try:
            if file_type_lower == 'pdf':
                images = self._convert_pdf_to_images(file_content)
                if not images:
                    logger.error(f"Could not extract images from PDF for async contract: {file_name}")
                    return None
                stitched_bytes = self.stitch_document_content(images)
                if not stitched_bytes:
                    logger.error(f"Failed to stitch PDF for async contract {file_name}")
                    return None
                image_bytes_to_process = stitched_bytes
            elif file_type_lower in ['jpg', 'jpeg', 'png']:
                image_bytes_to_process = file_content
            else:
                logger.error(f"Logic error or unhandled supported type in process_contract_async: {file_type_lower}")
                return None

            if not image_bytes_to_process:
                logger.error(f"No image prepared for Gemini async contract processing: {file_name}")
                return None

            return self._extract_contract_data_from_image_bytes(image_bytes_to_process, file_name)

        except ValidationError as ve:
            logger.error(f"Pydantic validation error async contract ('{file_name}'): {ve}")
            return ExtractedContractModel(supplier_name=None, items=[])
        except Exception as e:
            logger.error(f"Error processing contract async ('{file_name}'): {str(e)}")
            return ExtractedContractModel(supplier_name=None, items=[])

    @staticmethod
    async def process_invoice(file_content: bytes, file_type: str, file_name: str = "unknown_invoice_static") -> Optional[ExtractedInvoiceModel]:
        processor = DocumentProcessor()
        # When called as static method, assume it's the original file type, so don't skip check by default
        return await processor.process_invoice_async(file_content, file_type, file_name, skip_type_check=False)
            
    async def process_invoice(self, file_path: str) -> Optional[ExtractedInvoiceModel]:
        try:
            file_name = Path(file_path).name
            logger.info(f"Processing invoice file from path: {file_path} (filename: {file_name})")
            
            if not os.path.exists(file_path):
                logger.error(f"File not found: {file_path}")
                return None
                
            file_extension = Path(file_path).suffix.lower().lstrip('.') 
            # Original file type check happens here for the instance method
            if file_extension not in SUPPORTED_INVOICE_FILE_TYPES:
                logger.error(f"Unsupported file type from path '{file_path}': {file_extension}")
                return None
            
            with open(file_path, 'rb') as file:
                file_content = file.read()
                
            # The content here is from the original file. If it's PDF, process_invoice_async will handle stitching.
            # So, we don't skip the type check here as it's the first entry point for this file type.
            return await self.process_invoice_async(file_content, file_extension, file_name, skip_type_check=False)
            
        except Exception as e:
            logger.error(f"Error processing invoice from file path '{file_path}': {str(e)}")
            return ExtractedInvoiceModel(raw_text=f"File Path Processing Error: {str(e)}", supplier_name="Unknown Supplier", items=[])